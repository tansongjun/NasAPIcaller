# backend/main.py
from time import time
import requests, json, time, os, sys

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uuid
import json
from pathlib import Path
from typing import Dict, List, Optional

SERVER_ADDRESS = "http://127.0.0.1:8188"

def upload_uploadfile_to_comfyui(upload: UploadFile, server_address: str = SERVER_ADDRESS, overwrite: bool = True) -> str | None:
    filename = upload.filename or f"reference_{uuid.uuid4().hex}.png"
    content_type = upload.content_type or "application/octet-stream"

    files = {"image": (filename, upload.file, content_type)}
    data = {"overwrite": str(overwrite).lower()}

    r = requests.post(f"{server_address}/upload/image", files=files, data=data)
    if r.status_code != 200:
        print(f"Upload failed: {r.status_code} - {r.text}")
        return None
    return filename

def upload_image(image_path: str, server_address: str = SERVER_ADDRESS, overwrite: bool = True) -> str | None:
    """Upload image to ComfyUI/input and return the filename used by ComfyUI"""
    if not os.path.exists(image_path):
        print(f"Reference image not found: {image_path}")
        return None

    filename = os.path.basename(image_path)

    with open(image_path, "rb") as f:
        files = {"image": (filename, f, "image/jpeg" if filename.lower().endswith(".jpg") else "image/png")}
        data = {"overwrite": str(overwrite).lower()}

        response = requests.post(
            f"{server_address}/upload/image",
            files=files,
            data=data
        )

    if response.status_code != 200:
        print(f"Upload failed: {response.status_code} - {response.text}")
        return None

    print(f"Uploaded reference image as: {filename}")
    return filename

# Reuse your existing functions
def replace_prompt_and_image_ref(workflow, prompt: str, image_filename: str | None = None):
    """Replace {{prompt}} and {{reference_image}} if present"""

    def recurse(data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    if "{{prompt}}" in v:
                        data[k] = v.replace("{{prompt}}", prompt)
                    if image_filename and "{{reference_image}}" in v:
                        data[k] = v.replace("{{reference_image}}", image_filename)
                else:
                    recurse(v)
        elif isinstance(data, list):
            for item in data:
                recurse(item)

    recurse(workflow)

def load_workflow(workflow_file):
        if not os.path.exists(workflow_file):
            raise FileNotFoundError(f"\nWorkflow file not found: {workflow_file}\n")
        with open(workflow_file, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        print(f"Loaded workflow → {os.path.basename(workflow_file)}")
        return workflow

def find_reference_image_for_workflow(wf_name: str) -> str | None:
    """Heuristic: try to find matching reference image"""
    base = os.path.splitext(wf_name)[0]
    folder = Path(".")

    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        candidate = folder / (base + ext)
        if candidate.is_file():
            return str(candidate)

    # Fallback: any *_ref.jpg / reference.jpg etc...
    for file in folder.glob("*ref*.jpg"):
        return str(file)
    for file in folder.glob("*reference*.png"):
        return str(file)

def generate_image(prompt, workflow_file, server_address=SERVER_ADDRESS, reference_filename: str | None = None):
    workflow = load_workflow(workflow_file)

    uploaded_filename = reference_filename
    # 1. Try to find & upload reference image
    if not uploaded_filename:
        ref_path = find_reference_image_for_workflow(os.path.basename(workflow_file))
        if ref_path:
            uploaded_filename = upload_image(ref_path, server_address)
        else:
            print("   No reference image found for this workflow")

    # 2. Replace placeholders
    replace_prompt_and_image_ref(workflow, prompt, uploaded_filename)

    payload = {"prompt": workflow}

    response = requests.post(f"{server_address}/prompt", json=payload)
    if response.status_code != 200:
        print(f"Queue error: {response.status_code}\n{response.text}")
        return []

    prompt_id = response.json()["prompt_id"]
    print(f"   Job queued: {prompt_id}")

    print("   Generating", end="", flush=True)
    while True:
        history_resp = requests.get(f"{server_address}/history/{prompt_id}")
        if history_resp.status_code != 200:
            time.sleep(1)
            continue

        history = history_resp.json()
        if prompt_id in history:
            outputs = history[prompt_id]["outputs"]
            urls = []

            for node_id in outputs:
                if "images" in outputs[node_id]:
                    for img_data in outputs[node_id]["images"]:
                        filename = img_data["filename"]
                        url = f"{server_address}/view?filename={filename}&type=output"
                        urls.append(url)

            if urls:
                print(f" → Done! ({len(urls)} image(s) generated)")
                return urls
            else:
                print(" → Done, but no images found in outputs")
                return []

        print(".", end="", flush=True)
        time.sleep(2)

app = FastAPI(title="NAS ComfyUI Runner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default + Next.js
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/workflows")
def list_workflows():
    """List all available .json workflows in current directory"""
    workflow_files = [f for f in os.listdir(".") if f.lower().endswith(".json")]
    return {"workflows": sorted(workflow_files)}

@app.post("/generate")
async def generate(
    workflow_name: str = Form(...),
    prompt: str = Form(...),
    reference_image: UploadFile | None = File(None),
):
    if not workflow_name.endswith(".json"):
        workflow_name += ".json"

    workflow_path = Path(workflow_name)
    if not workflow_path.is_file():
        raise HTTPException(status_code=404, detail="Workflow not found")

    uploaded_filename = None
    if reference_image is not None:
        uploaded_filename = upload_uploadfile_to_comfyui(reference_image)
        if uploaded_filename is None:
            raise HTTPException(status_code=400, detail="Failed to upload reference image")

    try:
        urls = generate_image(prompt, str(workflow_path), reference_filename=uploaded_filename)
        return {
            "status": "success",
            "images": urls,
            "workflow": workflow_name,
            "prompt": prompt,
            "reference_image": uploaded_filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================= MAIN =============================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)