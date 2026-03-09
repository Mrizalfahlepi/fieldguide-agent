# FieldGuide - AI-Powered Visual Repair Supervisor

> Gemini Live Agent Challenge 2026 Submission

## Problem

When critical equipment breaks in remote areas (irrigation pumps, generators,
electrical panels), calling a technician takes days. Local people don't know
how to fix it — or are afraid to try.

## Solution

FieldGuide is a real-time AI repair supervisor powered by Gemini Live API.
Point your phone camera at broken equipment and the AI:

1. SEES the equipment through camera (real-time video)
2. IDENTIFIES type, brand, and components
3. LISTENS to you describe the problem (bidirectional audio)
4. GUIDES repair step-by-step with voice
5. INTERRUPTS if you reach for a dangerous component

## Tech Stack

- AI: Gemini 2.0 Flash Live API
- Backend: Python, FastAPI, WebSocket
- Frontend: React, Vite, Tailwind CSS
- Database: Firestore (repair manuals RAG)
- Hosting: Google Cloud Run

## Quick Start

### Backend
    cd backend
    cp .env.example .env
    pip install -r requirements.txt
    python rag_engine.py
    python main.py

### Frontend
    cd frontend
    npm install
    npm run dev

### Deploy
    export GEMINI_API_KEY=your_key
    cd deploy && chmod +x setup.sh && ./setup.sh

## Author

Muhamad Rizal Fahlepi — 10+ years hardware troubleshooting experience
Surabaya, Indonesia | github.com/Mrizalfahlepi
