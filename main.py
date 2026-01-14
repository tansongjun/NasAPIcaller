import requests, json, time, os, sys
from pathlib import Path

# Default ComfyUI server
SERVER_ADDRESS = "http://127.0.0.1:8188"

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

    return None
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

def queue_prompt(workflow, client_id):
    payload = {
        "prompt": workflow,
        "client_id": client_id
    }
    response = requests.post(f"{SERVER_ADDRESS}/prompt", json=payload)
    if response.status_code != 200:
        print(f"Queue error: {response.status_code} - {response.text}")
        return None
    return response.json()["prompt_id"]

def generate_image(prompt, workflow_file, server_address=SERVER_ADDRESS):
    workflow = load_workflow(workflow_file)

    # 1. Try to find & upload reference image
    ref_path = find_reference_image_for_workflow(os.path.basename(workflow_file))
    uploaded_filename = None

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
        return None

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
            for node_id in outputs:
                if "images" in outputs[node_id]:
                    images = outputs[node_id]["images"]
                    if images:
                        filename = images[0]["filename"]
                        url = f"{server_address}/view?filename={filename}&type=output"
                        print(" → Done!")
                        return url

        print(".", end="", flush=True)
        time.sleep(2)

# ============================= MAIN =============================
if __name__ == "__main__":
    # Find all JSON workflow files
    workflow_files = [f for f in os.listdir(".") if f.lower().endswith(".json")]
    
    if not workflow_files:
        print("No .json workflow files found in this folder!")
        print("Place your workflow files (e.g., qwen.json, hidream.json) here and try again.")
        sys.exit(1)
    
    # Your default prompt
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
    default_prompt = (
        "Create a female version of the exact same adorable toddler character from the reference image:  "
        "transform the boy into a cute 2-3 year old girl, "
        "keep the same large expressive black eyes, same short tousled brown hair but slightly softer/feminine styling, "
        "same soft rosy chubby cheeks, same subtle happy smile, same bright yellow onesie pajamas with small embroidered teddy bear,"
        "same confident standing pose with arms relaxed, identical proportions and body shape just gendered female, "
        "hyper-realistic Pixar/DreamWorks CGI style, vibrant colors, full-body frontal view, minimalist neutral background"
    )
    
    # Check if user wants to run only one specific workflow
    if len(sys.argv) >= 2:
        specific_workflow = sys.argv[1]
        if not specific_workflow.endswith(".json"):
            specific_workflow += ".json"
        
        if specific_workflow not in workflow_files:
            print(f"Specified workflow '{specific_workflow}' not found.")
            print("Available:", ", ".join(workflow_files))
            sys.exit(1)
        
        workflows_to_run = [specific_workflow]
        prompt_to_use = " ".join(sys.argv[2:]) if len(sys.argv) >= 3 else default_prompt
        print(f"Running single workflow: {specific_workflow}\n")
    else:
        workflows_to_run = sorted(workflow_files)
        prompt_to_use = default_prompt
        print(f"No workflow specified → running ALL {len(workflows_to_run)} workflows with default prompt\n")

    print(f"Prompt:\n{prompt_to_use}\n")
    print("-" * 60)

    # Run each workflow one by one
    results = []
    for wf in workflows_to_run:
        print(f"[{workflows_to_run.index(wf) + 1}/{len(workflows_to_run)}] {wf}")
        urls = generate_image(prompt_to_use, wf)
        if urls:
            for i, url in enumerate(urls, 1):
                print(f"   Image {i}: {url}")
            results.append((wf, urls))
        else:
            results.append((wf, None))
            print(f"   Failed to generate.\n")
        print("-" * 60)

    # Final summary
    print("ALL DONE! Summary:")
    for wf, urls in results:
        status = f"{len(urls)} image(s)" if urls else "(failed)"
        print(f"   • {wf} → {status}")

    if any(urls for _, urls in results):
        print("\nCheck your ComfyUI output folder or open the URLs above.")
    print("\nYour NAS models are working great! 🚀")