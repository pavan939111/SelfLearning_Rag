# Self-Learning and Self-Healing RAG Frontend

Vite + React frontend for the Self-Learning and Self-Healing RAG system.

## Pages

### /chat — Conversational Interface
Main research interface. Ask biomedical questions
and receive grounded answers with inline citations.

Features:
- Session management with localStorage persistence
- Inline citation tags with paper metadata popup
- Calibrated confidence bar (green/yellow/red)
- Cache hit indicator (⚡) for instant responses
- Repair cycle badge (🔄) when agents fixed retrieval
- Gap acknowledgment and contradiction surfacing

### /transparency — Live Agent Feed
Watch the nine agents work in real time via
Server-Sent Events (SSE) streaming.

Three panels:
- Left: Mini chat interface
- Center: Live agent activity feed (animated cards)
- Right: System state (corpus size, insights, gaps)

### /admin — Operations Dashboard
System health and operations monitoring.

Sections:
- Database health indicators (4 services)
- Corpus statistics (4 metric cards)
- Agent 6 coverage gap insights
- Pending Agent 4B repair approvals
- Benchmark trend chart (weekly improvement)

## Setup

npm install
npm run dev

Requires backend running on port 8000.

## Tech Stack
- Vite 5 + React 18
- React Router 6
- Framer Motion (animations)
- Recharts (benchmark chart)
- Lucide React (icons)
- Axios (API client)
- JetBrains Mono + Syne (fonts)
