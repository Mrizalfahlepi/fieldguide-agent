import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

from rag_engine_v2 import get_context_for_query, get_equipment_list, load_knowledge_base
from safety_monitor import check_safety_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FieldGuide-Live")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash-native-audio-latest"

client = genai.Client(api_key=GEMINI_API_KEY)

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Session timeout config - Gemini Live API has ~10-15 min limit
SESSION_MAX_DURATION = 8 * 60  # Reconnect every 8 minutes (before API timeout)
SESSION_RECONNECT_DELAY = 0.5

BASE_SYSTEM_PROMPT = """
You are FieldGuide AI, an expert industrial field technician assistant with 20+ years of experience.
You help technicians diagnose, repair, and maintain industrial equipment in real-time.

You can SEE through the user's camera and HEAR their voice in real-time.
Give step-by-step repair instructions, one step at a time.
ALWAYS prioritize safety. If you see something dangerous, INTERRUPT immediately.

SAFETY PRIORITIES:
1. Electrical hazards - shock, arc flash
2. Gas/fuel hazards - explosion, fire
3. Mechanical hazards - moving parts, pressure

COMMUNICATION STYLE:
- Speak clearly and concisely
- Number your steps
- Confirm understanding before moving to next step

When the session starts, introduce yourself briefly and ask what the user needs help with.
"""


def build_system_prompt() -> str:
    prompt = BASE_SYSTEM_PROMPT
    equipment = get_equipment_list()
    if equipment:
        eq_summary = ", ".join(
            f"{e['brand']} {e['model']} ({e['equipment_type']})"
            for e in equipment if e.get('brand')
        )
        if eq_summary:
            prompt += f"\n\nYou have repair manuals for: {eq_summary}."
    return prompt


def get_live_config(system_prompt: str) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_prompt)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FieldGuide AI starting up...")
    logger.info(f"Gemini API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
    logger.info(f"Model: {MODEL}")
    logger.info(f"Static dir: {STATIC_DIR} (exists: {STATIC_DIR.exists()})")
    logger.info(f"index.html: {(STATIC_DIR / 'index.html').exists()}")
    load_knowledge_base()
    equipment = get_equipment_list()
    logger.info(f"Knowledge base: {len(equipment)} equipment loaded")
    for eq in equipment:
        logger.info(f"  - {eq['brand']} {eq['model']} ({eq['equipment_type']})")
    yield
    logger.info("FieldGuide AI shutting down...")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return JSONResponse({"message": "FieldGuide AI Backend running", "status": "running"})


@app.get("/health")
async def health():
    equipment = get_equipment_list()
    return {
        "status": "ok",
        "model": MODEL,
        "knowledge_base": {
            "equipment_count": len(equipment),
            "equipment": equipment,
        },
    }


@app.get("/health/v2")
async def health_v2():
    """Health check dengan info ChromaDB."""
    from rag_engine_v2 import _get_collections
    knowledge_col, chunks_col = _get_collections()
    equipment = get_equipment_list()
    return {
        "status": "ok",
        "model": MODEL,
        "embedding_model": "gemini-embedding-2-preview",
        "vector_db": "ChromaDB",
        "knowledge_base": {
            "equipment_count": len(equipment),
            "equipment": equipment,
            "indexed_knowledge": knowledge_col.count(),
            "indexed_chunks": chunks_col.count(),
        },
    }


@app.post("/reindex")
async def reindex_knowledge():
    """Force re-index semua knowledge. Panggil setelah update data."""
    from rag_engine_v2 import force_reindex
    try:
        force_reindex()
        equipment = get_equipment_list()
        return {
            "status": "success",
            "message": "Knowledge base re-indexed with Gemini Embedding 2",
            "equipment_count": len(equipment),
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "assets").mkdir(exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static")


class GeminiSession:
    """Manages a Gemini Live session with auto-reconnect on 1011 timeout."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.session = None
        self.stop_event = asyncio.Event()
        self.session_lock = asyncio.Lock()
        self.audio_send_count = 0
        self.turn_count = 0
        self.session_start_time = 0.0
        self.reconnect_count = 0
        self._session_context = None
        self.system_prompt = build_system_prompt()
        self.config = get_live_config(self.system_prompt)

    async def connect(self) -> bool:
        """Create a new Gemini Live session."""
        async with self.session_lock:
            try:
                await self._close_session_internal()
                logger.info(f"Connecting to Gemini: {MODEL} (attempt #{self.reconnect_count + 1})")
                self._session_context = client.aio.live.connect(model=MODEL, config=self.config)
                self.session = await self._session_context.__aenter__()
                self.session_start_time = asyncio.get_event_loop().time()
                self.reconnect_count += 1
                logger.info(f"Gemini Live session established! (session #{self.reconnect_count})")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to Gemini: {e}", exc_info=True)
                self.session = None
                self._session_context = None
                return False

    async def _close_session_internal(self):
        """Close current session (must hold session_lock)."""
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing previous session: {e}")
            self._session_context = None
            self.session = None

    async def close(self):
        """Close session safely."""
        async with self.session_lock:
            await self._close_session_internal()

    def is_session_expired(self) -> bool:
        """Check if session is approaching API timeout."""
        if self.session_start_time == 0:
            return False
        elapsed = asyncio.get_event_loop().time() - self.session_start_time
        return elapsed >= SESSION_MAX_DURATION

    def is_1011_error(self, error: Exception) -> bool:
        """Check if error is the Gemini 1011 deadline/timeout error."""
        err_str = str(error)
        return "1011" in err_str or "Deadline expired" in err_str

    async def reconnect(self, reason: str = "timeout") -> bool:
        """Reconnect to Gemini with notification to client."""
        logger.warning(f"Reconnecting Gemini session (reason: {reason})...")
        try:
            await self.ws.send_json({
                "type": "status",
                "message": "reconnecting",
                "reason": reason,
            })
        except Exception:
            pass

        await asyncio.sleep(SESSION_RECONNECT_DELAY)

        success = await self.connect()
        if success:
            try:
                await self.ws.send_json({
                    "type": "status",
                    "message": "reconnected",
                    "session_number": self.reconnect_count,
                })
            except Exception:
                pass
            logger.info(f"Reconnected successfully (session #{self.reconnect_count})")
        else:
            logger.error("Reconnect failed!")
        return success

    async def send_audio(self, audio_bytes: bytes) -> bool:
        """Send audio to Gemini with error handling."""
        if not self.session or self.stop_event.is_set():
            return False
        try:
            await self.session.send_realtime_input(
                audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
            )
            self.audio_send_count += 1
            if self.audio_send_count % 50 == 0:
                logger.info(f"<<< Audio chunks sent to Gemini: {self.audio_send_count}")
            return True
        except Exception as e:
            logger.error(f"!!! Failed to send audio to Gemini: {e}")
            return False

    async def send_video(self, img_bytes: bytes) -> bool:
        """Send video frame to Gemini with error handling."""
        if not self.session or self.stop_event.is_set():
            return False
        try:
            await self.session.send_realtime_input(
                video=types.Blob(data=img_bytes, mime_type="image/jpeg")
            )
            return True
        except Exception as e:
            if not self.is_1011_error(e):
                logger.error(f"Failed to send video to Gemini: {e}")
            return False

    async def send_text(self, text: str) -> bool:
        """Send text with RAG context to Gemini."""
        if not self.session or self.stop_event.is_set():
            return False
        try:
            safety_alert = check_safety_context(text)
            context = get_context_for_query(text)

            parts = [types.Part(text=text)]
            context_parts = []
            if safety_alert:
                context_parts.append(safety_alert)
            if context:
                context_parts.append(context)

            if context_parts:
                combined_context = "\n\n".join(context_parts)
                await self.session.send_client_content(
                    turns=[
                        types.Content(role="user", parts=[types.Part(text=f"[CONTEXT]\n{combined_context}")]),
                        types.Content(role="user", parts=parts),
                    ]
                )
            else:
                await self.session.send_client_content(
                    turns=types.Content(role="user", parts=parts)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to send text to Gemini: {e}")
            return False

    async def send_audio_stream_end(self):
        """Signal end of audio stream after turn completes."""
        if not self.session:
            return
        try:
            await self.session.send_realtime_input(audio_stream_end=True)
            logger.info(">>> Sent audio_stream_end to Gemini")
        except Exception as e:
            logger.warning(f"audio_stream_end failed (ok to ignore): {e}")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket client connected")

    gemini = GeminiSession(ws)

    try:
        if not await gemini.connect():
            await ws.send_json({"type": "error", "message": "Failed to connect to Gemini"})
            await ws.close()
            return

        try:
            await ws.send_json({
                "type": "status",
                "message": "connected",
                "knowledge_base": len(get_equipment_list()),
            })
        except Exception as e:
            logger.error(f"Failed to send status: {e}")
            return

        async def receive_from_client():
            """Receive data from browser and forward to Gemini."""
            try:
                while not gemini.stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.receive_text(), timeout=60)
                    except asyncio.TimeoutError:
                        continue
                    except WebSocketDisconnect:
                        logger.info("Client disconnected (receive)")
                        gemini.stop_event.set()
                        return

                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg_type = data.get("type", "")

                    if msg_type == "audio" and data.get("data"):
                        audio_bytes = base64.b64decode(data["data"])
                        success = await gemini.send_audio(audio_bytes)
                        if not success and not gemini.stop_event.is_set():
                            reconnected = await gemini.reconnect(reason="audio_send_failed")
                            if not reconnected:
                                logger.error("Reconnect failed after audio send error")
                                gemini.stop_event.set()
                                return
                            await gemini.send_audio(audio_bytes)

                    elif msg_type in ("video", "image") and data.get("data"):
                        img_bytes = base64.b64decode(data["data"])
                        await gemini.send_video(img_bytes)

                    elif msg_type == "text" and data.get("text"):
                        success = await gemini.send_text(data["text"])
                        if not success and not gemini.stop_event.is_set():
                            reconnected = await gemini.reconnect(reason="text_send_failed")
                            if not reconnected:
                                gemini.stop_event.set()
                                return

            except Exception as e:
                logger.error(f"Receive loop error: {e}", exc_info=True)
                gemini.stop_event.set()

        async def send_to_client():
            """Receive responses from Gemini and forward to frontend.

            Handles:
            - turn_complete restart loop
            - 1011 timeout auto-reconnect
            - Proactive session refresh before timeout
            """
            ai_is_speaking = False
            response_count = 0
            consecutive_errors = 0
            MAX_CONSECUTIVE_ERRORS = 3

            try:
                while not gemini.stop_event.is_set():
                    # Proactive reconnect before API timeout hits
                    if gemini.is_session_expired():
                        logger.warning("Session approaching timeout, proactive reconnect...")
                        if ai_is_speaking:
                            ai_is_speaking = False
                            try:
                                await ws.send_json({"type": "ai_speaking", "speaking": False})
                                await ws.send_json({"type": "turn_complete"})
                            except Exception:
                                pass
                        reconnected = await gemini.reconnect(reason="proactive_refresh")
                        if not reconnected:
                            logger.error("Proactive reconnect failed")
                            gemini.stop_event.set()
                            return
                        consecutive_errors = 0
                        response_count = 0
                        continue

                    if not gemini.session:
                        await asyncio.sleep(0.5)
                        continue

                    try:
                        async for response in gemini.session.receive():
                            if gemini.stop_event.is_set():
                                break

                            consecutive_errors = 0
                            response_count += 1

                            try:
                                audio_data = None
                                text_data = None
                                input_transcript = None

                                # Check for input transcription (user speech)
                                if hasattr(response, 'server_content') and response.server_content:
                                    sc = response.server_content
                                    if hasattr(sc, 'input_transcription') and sc.input_transcription:
                                        if hasattr(sc.input_transcription, 'text') and sc.input_transcription.text:
                                            input_transcript = sc.input_transcription.text
                                            logger.info(f">>> User said: {input_transcript}")

                                # Debug log
                                resp_attrs = []
                                if hasattr(response, 'data') and response.data:
                                    resp_attrs.append(f"data({len(response.data)}b)")
                                if hasattr(response, 'text') and response.text:
                                    resp_attrs.append(f"text({len(response.text)}c)")
                                if hasattr(response, 'server_content') and response.server_content:
                                    sc = response.server_content
                                    if hasattr(sc, 'model_turn') and sc.model_turn:
                                        resp_attrs.append("model_turn")
                                    if hasattr(sc, 'turn_complete') and sc.turn_complete:
                                        resp_attrs.append("turn_complete")
                                    if hasattr(sc, 'interrupted') and sc.interrupted:
                                        resp_attrs.append("interrupted")
                                    if hasattr(sc, 'input_transcription') and sc.input_transcription:
                                        resp_attrs.append("input_transcription")

                                if (
                                    response_count <= 5
                                    or response_count % 50 == 0
                                    or 'turn_complete' in resp_attrs
                                    or 'interrupted' in resp_attrs
                                    or 'input_transcription' in resp_attrs
                                ):
                                    logger.info(
                                        f">>> Gemini response #{response_count}: "
                                        f"[{', '.join(resp_attrs) if resp_attrs else 'EMPTY'}]"
                                    )

                                # Method 1: direct .data attribute
                                if hasattr(response, 'data') and response.data:
                                    audio_data = response.data

                                # Method 2: server_content.model_turn.parts
                                if hasattr(response, 'server_content') and response.server_content:
                                    sc = response.server_content
                                    if hasattr(sc, 'model_turn') and sc.model_turn:
                                        for part in sc.model_turn.parts:
                                            if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                                                audio_data = part.inline_data.data
                                            if hasattr(part, 'text') and part.text:
                                                text_data = part.text

                                # Method 3: direct .text attribute
                                if hasattr(response, 'text') and response.text:
                                    text_data = response.text

                                # Send ai_speaking=true ONCE when AI starts
                                if audio_data and not ai_is_speaking:
                                    ai_is_speaking = True
                                    await ws.send_json({"type": "ai_speaking", "speaking": True})
                                    logger.info(">>> AI started speaking - mic muted")

                                if audio_data:
                                    audio_b64 = base64.b64encode(audio_data).decode()
                                    await ws.send_json({"type": "audio", "data": audio_b64})
                                    if response_count % 20 == 0:
                                        logger.info(f">>> Sent audio chunk (response #{response_count})")

                                if text_data:
                                    await ws.send_json({"type": "transcript", "text": text_data, "role": "assistant"})
                                    logger.info(f">>> Transcript: {text_data[:80]}")

                                if input_transcript:
                                    await ws.send_json({"type": "transcript", "text": input_transcript, "role": "user"})

                                # Check turn_complete or interrupted
                                turn_done = False
                                if hasattr(response, 'server_content') and response.server_content:
                                    sc = response.server_content
                                    if hasattr(sc, 'turn_complete') and sc.turn_complete:
                                        turn_done = True
                                        logger.info(">>> turn_complete from Gemini")
                                    if hasattr(sc, 'interrupted') and sc.interrupted:
                                        turn_done = True
                                        logger.info(">>> interrupted by user")

                                if turn_done:
                                    gemini.turn_count += 1
                                    ai_is_speaking = False
                                    await ws.send_json({"type": "ai_speaking", "speaking": False})
                                    await ws.send_json({"type": "turn_complete"})
                                    logger.info(f">>> Turn #{gemini.turn_count} complete - mic re-enabled")
                                    await gemini.send_audio_stream_end()

                            except WebSocketDisconnect:
                                logger.info("Client disconnected (send)")
                                gemini.stop_event.set()
                                break
                            except Exception as e:
                                logger.error(f"Error processing response: {e}", exc_info=True)

                    except StopAsyncIteration:
                        logger.info(">>> session.receive() ended - restarting for next turn")
                        continue

                    except Exception as e:
                        if gemini.stop_event.is_set():
                            break

                        consecutive_errors += 1
                        logger.error(f"Receive iterator error (#{consecutive_errors}): {e}")

                        if gemini.is_1011_error(e):
                            logger.warning("Detected 1011 timeout - attempting auto-reconnect...")
                            if ai_is_speaking:
                                ai_is_speaking = False
                                try:
                                    await ws.send_json({"type": "ai_speaking", "speaking": False})
                                    await ws.send_json({"type": "turn_complete"})
                                except Exception:
                                    pass
                            reconnected = await gemini.reconnect(reason="1011_timeout")
                            if reconnected:
                                consecutive_errors = 0
                                response_count = 0
                                logger.info("Auto-reconnect successful, resuming...")
                                continue
                            else:
                                logger.error("Auto-reconnect failed after 1011")
                                gemini.stop_event.set()
                                return

                        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            logger.error(f"Too many consecutive errors ({consecutive_errors}), reconnecting...")
                            reconnected = await gemini.reconnect(reason="too_many_errors")
                            if reconnected:
                                consecutive_errors = 0
                                response_count = 0
                                continue
                            else:
                                gemini.stop_event.set()
                                return

                        await asyncio.sleep(0.2 * consecutive_errors)
                        continue

            except Exception as e:
                logger.error(f"Send loop fatal error: {e}", exc_info=True)
                gemini.stop_event.set()

        # Run both tasks concurrently
        try:
            await asyncio.gather(
                receive_from_client(),
                send_to_client(),
                return_exceptions=True,
            )
        finally:
            await gemini.close()
            logger.info("Gemini session cleaned up")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Session error: {e}", exc_info=True)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await gemini.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
