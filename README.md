# FieldGuide Agent - AI-Powered Real-Time Equipment Repair Supervisor

[![Gemini Live Agent Challenge 2026](https://img.shields.io/badge/Gemini_Live_Agent_Challenge-2026-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/competition)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

> **Real-time AI repair supervisor** that sees through your camera, listens to your voice, and guides you step-by-step through equipment repairs — with safety-first interrupts.

---

## The Problem

When critical equipment breaks in remote areas — irrigation pumps, generators, electrical panels — calling a technician takes days. Local people don't know how to fix it, or are afraid to try. Downtime costs money, crops, and livelihoods.

## The Solution

FieldGuide Agent is a **multimodal AI repair supervisor** powered by the **Gemini 2.5 Flash Native Audio** model via the Live API. Point your phone camera at broken equipment and the AI:

1. **SEES** the equipment through your camera (real-time video streaming)
2. **IDENTIFIES** equipment type, brand, model, and components
3. **LISTENS** to you describe the problem (bidirectional audio with transcription)
4. **RETRIEVES** relevant repair manuals from a vector knowledge base (RAG)
5. **GUIDES** you step-by-step with voice instructions
6. **INTERRUPTS** immediately if you reach for a dangerous component

---

## Architecture

```
+------------------+         WebSocket (JSON)        +-------------------+
|                  | <-----------------------------> |                   |
|   React Frontend |    audio/video/text streams     |  FastAPI Backend   |
|   (Vite + TW)    |                                 |  (Python 3.11)    |
|                  |                                 |                   |
+------------------+                                 +--------+----------+
   |  Camera Stream                                           |
   |  Audio Capture                                           |
   |  Status Panel                                   +--------v----------+
   |  Transcript UI                                  |                   |
                                                     | Gemini 2.5 Flash  |
                                                     | Live API (Native  |
                                                     | Audio + Vision)   |
                                                     +--------+----------+
                                                              |
                                                     +--------v----------+
                                                     |   RAG Engine V2   |
                                                     |                   |
                                                     | - Gemini Embedding|
                                                     |   2 Preview       |
                                                     | - ChromaDB Vector |
                                                     |   Store           |
                                                     | - Safety Monitor  |
                                                     +-------------------+
```

## Key Features

### Gemini Live API — Native Audio Streaming
- **Model**: `gemini-2.5-flash-native-audio-latest` — direct audio-in, audio-out (no STT/TTS pipeline)
- **Bidirectional WebSocket**: Real-time audio + video frames sent simultaneously
- **Voice Activity Detection (VAD)**: Automatic speech detection with configurable sensitivity
- **Input Transcription**: Live transcription of user speech via `AudioTranscriptionConfig`
- **Auto-Reconnect**: Handles Gemini's 1011 timeout with seamless session refresh (proactive reconnect at 8 min)

### RAG Engine V2 — Gemini Embedding 2 + ChromaDB
- **Embedding Model**: `gemini-embedding-2-preview` (768-dim vectors, task-aware)
- **Vector Database**: ChromaDB with persistent storage and cosine similarity
- **Dual Collections**: Structured equipment knowledge + text chunks indexed separately
- **Task-Aware Embeddings**: `RETRIEVAL_DOCUMENT` for indexing, `RETRIEVAL_QUERY` for search
- **Batch Embedding**: Efficient batch processing (100 texts per API call)
- **Keyword Fallback**: Graceful degradation if embedding API is unavailable
- **Force Re-index API**: `POST /reindex` endpoint for live knowledge base updates

### Safety Monitor
- **Real-time keyword detection** for hazardous contexts (fuel, electrical, exhaust, battery, etc.)
- **Safety-first prompting**: AI automatically warns about dangers before giving repair steps
- **Interrupt capability**: AI can interrupt the user mid-action if it detects unsafe behavior

### Frontend — React + Vite
- **CameraStream**: Real-time camera capture with frame-by-frame streaming to backend
- **AudioHandler**: PCM audio capture at 16kHz, playback at 24kHz with AudioWorklet
- **StatusPanel**: Live connection status, knowledge base info, transcript display
- **useWebSocket Hook**: Manages WebSocket lifecycle, message routing, and reconnection

---

## Project Structure

```
fieldguide-agent/
|
|-- backend/
|   |-- gemini_live.py          # Main server: FastAPI + WebSocket + Gemini Live API
|   |-- rag_engine_v2.py        # RAG with Gemini Embedding 2 + ChromaDB
|   |-- embedding_service.py    # Gemini Embedding 2 client wrapper
|   |-- safety_monitor.py       # Real-time safety keyword detection
|   |-- config.py               # Environment config and system prompt
|   |-- rag_engine.py           # Legacy RAG (sentence-transformers, deprecated)
|   |-- requirements.txt        # Python dependencies
|   |-- Dockerfile              # Container image (python:3.11-slim)
|   |-- knowledge/              # Knowledge base files (JSONL + chunks)
|   |-- static/                 # Built frontend assets served by FastAPI
|
|-- frontend/
|   |-- src/
|   |   |-- App.jsx              # Main app: WebSocket orchestration
|   |   |-- components/
|   |   |   |-- CameraStream.jsx  # Camera capture + video streaming
|   |   |   |-- AudioHandler.jsx  # Audio capture/playback (PCM 16k/24k)
|   |   |   |-- StatusPanel.jsx   # Connection status + transcript UI
|   |   |-- hooks/
|   |       |-- useWebSocket.js   # WebSocket lifecycle management
|
|-- structured_knowledge/        # Equipment manuals (structured JSON)
|   |-- knowledge_base.jsonl     # Combined knowledge entries
|   |-- *_knowledge.json         # Per-equipment structured data
|
|-- extracted/                   # Raw extracted text from service manuals
|-- deploy/
|   |-- cloudbuild.yaml          # Google Cloud Build config
|   |-- setup.sh                 # Deployment automation script
|
|-- README.md
```

## Knowledge Base

The RAG system includes real industrial equipment manuals:

| Equipment | Brand | Type |
|---|---|---|
| Standby Generator 25kW | Generac | Generator |
| Portable Generator 750W | Generic | Generator |
| Service Manual Generator | Baldor | Generator |
| ServiceNet Manual | Generic | Generator |
| Water Pump WB20T/WB30T | Honda | Water Pump |
| Circuit Breaker MCB | Generic | Electrical Panel |

Each entry contains: components, symptoms, diagnostic steps, repair procedures, safety warnings, torque specs, maintenance schedules, and troubleshooting tables.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| AI Model | Gemini 2.5 Flash (Native Audio) | Real-time multimodal conversation |
| Embedding | Gemini Embedding 2 Preview | Semantic vector search (768-dim) |
| Vector DB | ChromaDB | Persistent vector storage + cosine search |
| Backend | FastAPI + Uvicorn | Async WebSocket server |
| Frontend | React 18 + Vite + Tailwind CSS | Real-time camera/audio UI |
| Container | Docker (python:3.11-slim) | Reproducible deployment |
| Cloud | Google Cloud Run + Cloud Build | Serverless container hosting |
| Audio | Web Audio API + AudioWorklet | Browser audio capture/playback |

### Python Dependencies
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
websockets>=12.0
google-genai>=1.0.0
python-dotenv>=1.0.0
chromadb>=0.6.0
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Gemini API Key ([Get one here](https://aistudio.google.com/apikey))

### Backend
```bash
cd backend
cp .env.example .env
# Add your GEMINI_API_KEY to .env

pip install -r requirements.txt
python gemini_live.py
# Server runs on http://localhost:8080
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Dev server runs on http://localhost:5173
```

### Build Frontend for Production
```bash
cd frontend
npm run build
# Output goes to backend/static/ for FastAPI to serve
```

### Deploy to Google Cloud Run
```bash
export GEMINI_API_KEY=your_key
cd deploy
chmod +x setup.sh
./setup.sh
```

Or with Cloud Build:
```bash
gcloud builds submit --config deploy/cloudbuild.yaml
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Serves frontend (index.html) |
| GET | `/health` | Basic health check + equipment list |
| GET | `/health/v2` | Extended health: ChromaDB stats, embedding model info |
| POST | `/reindex` | Force re-index knowledge base with Gemini Embedding 2 |
| WS | `/ws` | Main WebSocket: bidirectional audio/video/text streaming |

### WebSocket Message Types

**Client -> Server:**
- `{"type": "audio", "data": "<base64 PCM>"}` — Audio chunk
- `{"type": "video", "data": "<base64 JPEG>"}` — Video frame
- `{"type": "text", "text": "..."}` — Text query (triggers RAG + safety check)

**Server -> Client:**
- `{"type": "audio", "data": "<base64 PCM>"}` — AI audio response
- `{"type": "transcript", "text": "...", "role": "user|assistant"}` — Transcription
- `{"type": "ai_speaking", "speaking": true|false}` — Mic mute control
- `{"type": "turn_complete"}` — Turn finished, mic re-enabled
- `{"type": "status", "message": "connected|reconnecting|reconnected"}` — Session status

---

## How It Works

1. **User opens the app** -> Camera + microphone permissions requested
2. **WebSocket connects** -> Backend creates Gemini Live session
3. **Audio streams bidirectionally** -> User speaks, AI responds with voice
4. **Video frames stream** -> Camera frames sent as JPEG to Gemini for visual understanding
5. **Text queries trigger RAG** -> Query embedded with Gemini Embedding 2, searched in ChromaDB, context injected into Gemini conversation
6. **Safety monitor runs** -> Keywords checked against safety rules, warnings prepended to context
7. **Session auto-reconnects** -> At 8-minute mark or on 1011 timeout, session refreshes transparently

---

## Contributing

This is an open-source project for educational purposes. Contributions are welcome:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## Author

**Muhamad Rizal Fahlepi**
- 10+ years hardware troubleshooting experience
- Surabaya, Indonesia
- GitHub: [@Mrizalfahlepi](https://github.com/Mrizalfahlepi)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

> Built for the **Gemini Live Agent Challenge 2026** — Demonstrating real-world AI application for field technicians in underserved communities.
