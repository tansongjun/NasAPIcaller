import requests, json, time, os, sys

# Default ComfyUI server
SERVER_ADDRESS = "http://127.0.0.1:8188"

def load_workflow(workflow_file):
    if not os.path.exists(workflow_file):
        raise FileNotFoundError(f"\nWorkflow file not found: {workflow_file}\n")
    with open(workflow_file, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    print(f"Loaded workflow → {os.path.basename(workflow_file)}")
    return workflow

def generate_image(prompt, workflow_file, server_address=SERVER_ADDRESS):
    workflow = load_workflow(workflow_file)
    
    # Replace {{prompt}} everywhere
    def replace_placeholder(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "{{prompt}}" in value:
                    data[key] = value.replace("{{prompt}}", prompt)
                else:
                    replace_placeholder(value)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                replace_placeholder(item)
    
    replace_placeholder(workflow)
    
    payload = {"prompt": workflow}
    
    response = requests.post(f"{server_address}/prompt", json=payload)
    if response.status_code != 200:
        print(f"Queue error for {workflow_file}: {response.status_code}")
        print(response.text)
        return None
    
    prompt_id = response.json()["prompt_id"]
    print(f"   Job queued: {prompt_id}")
    
    # Poll until done
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
    
    # Your default prompt (the toddler boy one you love)
    default_prompt = (
        "Create an adorable 3D animated toddler boy, around 2-3 years old, "
        "with large expressive black eyes, short tousled brown hair, soft rosy cheeks, "
        "and a subtle happy smile, standing confidently with arms relaxed. "
        "He wears a bright yellow onesie pajamas with a small embroidered teddy bear on the chest, "
        "white ribbed socks, and simple white shoes. "
        "Hyper-realistic Pixar/DreamWorks CGI style, exaggerated cute proportions, "
        "vibrant colors, detailed fabric and skin textures, full-body frontal view, "
        "minimalist neutral beige gradient background with subtle floor shadow, "
        "soft warm natural daylight lighting, highly detailed, clean composition."
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
        # Default behavior: run ALL workflows
        workflows_to_run = sorted(workflow_files)
        prompt_to_use = default_prompt
        print(f"No workflow specified → running ALL {len(workflows_to_run)} workflows with default prompt\n")

    print(f"Prompt:\n{prompt_to_use}\n")
    print("-" * 60)

    # Run each workflow one by one
    results = []
    for wf in workflows_to_run:
        print(f"[{workflows_to_run.index(wf) + 1}/{len(workflows_to_run)}] {wf}")
        url = generate_image(prompt_to_use, wf)
        if url:
            results.append((wf, url))
            print(f"   Image: {url}\n")
        else:
            results.append((wf, None))
            print(f"   Failed to generate.\n")
        print("-" * 60)

    # Final summary
    print("ALL DONE! Summary:")
    for wf, url in results:
        status = url if url else "(failed)"
        print(f"   • {wf} → {status}")

    if any(url for _, url in results):
        print("\nCheck your ComfyUI output folder or open the URLs above.")
    print("\nYour NAS models are working great! 🚀")