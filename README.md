# NAS API Caller – ComfyUI Local Runner

Load and run open-source models stored on NAS (Suntec) directly on your local GPU using ComfyUI.

## Architecture
Frontend (React + Vite) 
→ FastAPI Backend (main.py) 
→ Local ComfyUI Server (GPU)

## Prerequisites
Python 3.10, Node.js 18+, A working ComfyUI installation, GPU properly set up for ComfyUI

## Quick Start
Make sure **ComfyUI server** is already running on your machine (usually at `http://127.0.0.1:8188`)
   
**Backend Setup**:
1. Navigate to the backend folder
2. Install dependencies (pip install fastapi uvicorn requests)
3. Run python main.py

**Frontend Setup**:
1. Navigate to the frontend folder
2. Install dependencies (npm install)
3. Run npm run dev
