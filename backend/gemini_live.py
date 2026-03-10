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

from rag_engine import get_context_for_query, get_equipment_list, load_knowledge_base
from safety_monitor import check_safety_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FieldGuide-Live")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash-native-audio-latest"

client = genai.Client(api_key=GEMINI_API_KEY)

STATIC_DIR = Path(__file__).resolve().parent / "static"

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
    return {"status": "ok", "model": MODEL, "knowledge_base": {"equipment_count": len(equipment), "equipment": equipment}}


STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket client connected")

    system_prompt = build_system_prompt()
    config = get_live_config(system_prompt)

    try:
        logger.info(f"Connecting to Gemini: {MODEL}")
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            logger.info("Gemini Live session established!")

            try:
                await ws.send_json({"type": "status", "message": "connected", "knowledge_base": len(get_equipment_list())})
            except Exception as e:
                logger.error(f"Failed to send status: {e}")
                return

            stop_event = asyncio.Event()

            async def receive_from_client():
                try:
                    while not stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.receive_text(), timeout=60)
                        except asyncio.TimeoutError:
                            continue
                        except WebSocketDisconnect:
                            logger.info("Client disconnected (receive)")
                            stop_event.set()
                            return

                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        msg_type = data.get("type", "")

                        if msg_type == "audio" and data.get("data"):
                            audio_bytes = base64.b64decode(data["data"])
                            await session.send_realtime_input(
                                audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                            )

                        elif msg_type in ("video", "image") and data.get("data"):
                            img_bytes = base64.b64decode(data["data"])
                            await session.send_realtime_input(
                                video=types.Blob(data=img_bytes, mime_type="image/jpeg")
                            )

                        elif msg_type == "text" and data.get("text"):
                            text = data["text"]

                            # FIX: safety monitor integrated — inject alert into context
                            safety_alert = check_safety_context(text)

                            context = get_context_for_query(text)

                            # FIX: RAG context and safety injected as system context, not appended to user text
                            parts = [types.Part(text=text)]
                            context_parts = []
                            if safety_alert:
                                context_parts.append(safety_alert)
                            if context:
                                context_parts.append(context)
                            if context_parts:
                                combined_context = "\n\n".join(context_parts)
                                await session.send_client_content(
                                    turns=[
                                        types.Content(role="user", parts=[types.Part(text=f"[CONTEXT FOR THIS QUERY]\n{combined_context}")]),
                                        types.Content(role="user", parts=parts),
                                    ]
                                )
                            else:
                                await session.send_client_content(
                                    turns=types.Content(role="user", parts=parts)
                                )

                except Exception as e:
                    logger.error(f"Receive loop error: {e}", exc_info=True)
                    stop_event.set()

            async def send_to_client():
                try:
                    async for response in session.receive():
                        if stop_event.is_set():
                            break

                        try:
                            audio_data = None
                            text_data = None

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

                            # FIX BUG 1: notify frontend AI is speaking before sending audio
                            if audio_data:
                                await ws.send_json({"type": "ai_speaking", "speaking": True})
                                audio_b64 = base64.b64encode(audio_data).decode()
                                await ws.send_json({"type": "audio", "data": audio_b64})
                                logger.info(f">>> Sent audio to client: {len(audio_data)} bytes")

                            if text_data:
                                await ws.send_json({"type": "transcript", "text": text_data, "role": "assistant"})
                                logger.info(f">>> Transcript: {text_data[:80]}")

                            # Notify frontend when turn is complete (AI done speaking)
                            if hasattr(response, 'server_content') and response.server_content:
                                sc = response.server_content
                                if hasattr(sc, 'turn_complete') and sc.turn_complete:
                                    await ws.send_json({"type": "ai_speaking", "speaking": False})
                                    await ws.send_json({"type": "turn_complete"})

                        except WebSocketDisconnect:
                            logger.info("Client disconnected (send)")
                            stop_event.set()
                            break
                        except Exception as e:
                            logger.error(f"Error processing response: {e}", exc_info=True)

                except Exception as e:
                    logger.error(f"Send loop error: {e}", exc_info=True)
                    stop_event.set()

            await asyncio.gather(
                receive_from_client(),
                send_to_client(),
                return_exceptions=True,
            )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Session error: {e}", exc_info=True)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
