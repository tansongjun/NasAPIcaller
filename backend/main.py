# backend/main.py
from time import time
import requests, json, time, os, uvicorn

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uuid
import json
from pathlib import Path

# To run comfyui server locally, uncomment this:
# SERVER_ADDRESS = "http://127.0.0.1:8188"

# To run comfyui server anywhere else, set its local IP here:
SERVER_ADDRESS = "http://192.168.1.156:8888"

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

def generate_media(prompt, workflow_file, server_address=SERVER_ADDRESS, reference_filename: str | None = None, 
                   width: int | None = None, height: int | None = None, fps: int | None = None, frame_count: int | None = None, 
                   steps: int | None = None, shift: float | None = None, cfg: float | None = None):
    workflow = load_workflow(workflow_file)

    # Override primitive nodes (very common in LTX-2 workflows)
    for node_id, node in workflow.items():
        cls = node.get("class_type", "")

        # Frame count
        if cls == "PrimitiveInt" and "_meta" in node and "Frame Count" in node["_meta"].get("title", ""):
            if frame_count is not None:
                node["inputs"]["value"] = frame_count

        # FPS (both int and float versions exist)
        if cls in ["PrimitiveInt", "PrimitiveFloat"] and "Frame Rate" in node["_meta"].get("title", ""):
            if fps is not None:
                node["inputs"]["value"] = fps
        
        #CFG
        if cls == "KSampler" and cfg is not None:
            if "cfg" in node["inputs"]:
                node["inputs"]["cfg"] = cfg
                print(f"Overrode KSampler CFG to {cfg}")
            else:
                print("Warning: No 'cfg' input found in KSampler node – cannot override")
        
        # Steps
        if cls == "KSampler":
            if steps is not None:
                node["inputs"]["steps"] = steps
                print(f"Overrode KSampler steps to {steps}")

        # Shift amount
        if cls == "ModelSamplingAuraFlow":
            if shift is not None:
                node["inputs"]["shift"] = shift
                print(f"Overrode ModelSamplingAuraFlow shift to {shift}")
                
        # Resolution on EmptyImage / latent nodes (LTX-2 uses 1280×720 base usually)
        if cls == "EmptyImage" or "EmptyLTXVLatentVideo" in cls:
            if width is not None:
                node["inputs"]["width"] = width
            if height is not None:
                node["inputs"]["height"] = height
    uploaded_filename = reference_filename
    # 1. Try to find & upload reference image
    if not uploaded_filename:
        ref_path = find_reference_image_for_workflow(os.path.basename(workflow_file))
        if ref_path:
            uploaded_filename = upload_image(ref_path, server_address)
        else:
            print("   No reference image found for this workflow")

    def snap_to_64(x: int) -> int:
        return max(256, (x // 64) * 64)

    if width or height:
        for node in workflow.values():
            if node.get("class_type") == "EmptySD3LatentImage":
                if width is not None:
                    node["inputs"]["width"] = snap_to_64(width)
                if height is not None:
                    node["inputs"]["height"] = snap_to_64(height)
    
    # 2. Replace placeholders
    replace_prompt_and_image_ref(workflow, prompt, uploaded_filename)

    payload = {"prompt": workflow}

    response = requests.post(f"{server_address}/prompt", json=payload)
    if response.status_code != 200:
        print(f"Queue error: {response.status_code}\n{response.text}")
        return []

    prompt_id = response.json()["prompt_id"]
    print(f"   Job queued: {prompt_id}")
    media_urls = []
    print("   Generating", end="", flush=True)
    while True:
        history_resp = requests.get(f"{server_address}/history/{prompt_id}")
        if history_resp.status_code != 200:
            time.sleep(1)
            continue

        history = history_resp.json()
        if prompt_id in history:
            outputs = history[prompt_id]["outputs"]
            media_urls = []

            print("DEBUG - All output nodes and their keys:")
            for node_id, node_output in outputs.items():
                print(f"  Node {node_id} ({node_output.get('class_type', 'unknown')}): {list(node_output.keys())}")
                
                # Images (your current working case)
                if "images" in node_output:
                    for item in node_output["images"]:
                        filename = item.get("filename")
                        if filename:
                            url = f"{server_address}/view?filename={filename}&subfolder={item.get('subfolder','')}&type={item.get('type','output')}"
                            media_urls.append(url)
                            print(f"     → Added image: {filename}")

                # Videos – make it case-insensitive and check alternatives
                video_keys = ["videos", "video", "files"]  # sometimes custom nodes use singular
                for vk in video_keys:
                    if vk in node_output:
                        items = node_output[vk]
                        if not isinstance(items, list):
                            items = [items]
                        for item in items:
                            filename = item.get("filename") or item.get("file")
                            if filename:
                                subfolder = item.get("subfolder", "")
                                type_ = item.get("type", "output")
                                url = f"{server_address}/view?filename={filename}"
                                if subfolder:
                                    url += f"&subfolder={subfolder}"
                                url += f"&type={type_}"
                                media_urls.append(url)
                                print(f"     → Added VIDEO: {filename}")

                # Fallback: any node with "filename" directly
                if "filename" in node_output and filename.endswith(('.mp4', '.webm', '.gif')):
                    filename = node_output["filename"]
                    url = f"{server_address}/view?filename={filename}&type=output"
                    media_urls.append(url)
                    print(f"     → Added direct video fallback: {filename}")

            # Final result
            if media_urls:
                print(f" → Success! Collected {len(media_urls)} media URLs")
                return media_urls
            else:
                print(" → No media detected. Check if SaveVideo node ran and registered output.")
                return []

        print(".", end="", flush=True)
        time.sleep(2)

app = FastAPI(title="NAS ComfyUI Runner API")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Optional: expose_headers=["Content-Disposition"] if you return files
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
    width: int | None = Form(None),
    height: int | None = Form(None),
    fps: int = Form(24),
    frame_count: int = Form(121),
    steps: int | None = Form(9),
    shift: float | None = Form(3.0),
    cfg: float | None = Form(None),
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
        urls = generate_media(prompt, str(workflow_path), reference_filename=uploaded_filename, width=width,
            height=height, fps=fps, frame_count=frame_count,steps=steps, shift=shift,cfg=cfg,)
        return {
            "status": "success",
            "images": urls,
            "workflow": workflow_name,
            "prompt": prompt,
            "reference_image": uploaded_filename,
             "width": width,
            "height": height,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================= MAIN =============================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Past prompts
    # default_prompt = (
    #     "Create an adorable 3D animated toddler boy, around 2-3 years old, "
    #     "with large expressive black eyes, short tousled brown hair, soft rosy cheeks, "
    #     "and a subtle happy smile, standing confidently with arms relaxed. "
    #     "He wears a bright yellow onesie pajamas with a small embroidered teddy bear on the chest, "
    #     "white ribbed socks, and simple white shoes. "
    #     "Hyper-realistic Pixar/DreamWorks CGI style, exaggerated cute proportions, "
    #     "vibrant colors, detailed fabric and skin textures, full-body frontal view, "
    #     "minimalist neutral beige gradient background with subtle floor shadow, "
    #     "soft warm natural daylight lighting, highly detailed, clean composition."
    # )

    # Use this prompt to test reference image functionality
    # default_prompt = (
    #     "Create a female version of the exact same adorable toddler character from the reference image:  "
    #     "transform the boy into a cute 2-3 year old girl, "
    #     "keep the same large expressive black eyes, same short tousled brown hair but slightly softer/feminine styling, "
    #     "same soft rosy chubby cheeks, same subtle happy smile, same bright yellow onesie pajamas with small embroidered teddy bear,"
    #     "same confident standing pose with arms relaxed, identical proportions and body shape just gendered female, "
    #     "hyper-realistic Pixar/DreamWorks CGI style, vibrant colors, full-body frontal view, minimalist neutral background"
    # )