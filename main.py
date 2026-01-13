import requests, json, os, sys, uuid, websocket

# Default ComfyUI server
SERVER_ADDRESS = "http://127.0.0.1:8188"
WS_ADDRESS = f"ws://{SERVER_ADDRESS.split('://')[1]}/ws"

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
    
    client_id = str(uuid.uuid4())
    
    prompt_id = queue_prompt(workflow, client_id)
    if not prompt_id:
        return None
    
    print(f"   Job queued: {prompt_id}")
    print("   Generating ", end="", flush=True)
    
    ws_url = f"{WS_ADDRESS}?clientId={client_id}"
    try:
        ws = websocket.WebSocket()
        ws.connect(ws_url)
        print(f" (connected as {client_id[:8]}...)")
    except Exception as e:
        print(f"\n   Failed to connect WebSocket: {e}")
        return None
    
    try:
        while True:
            message = ws.recv()
            if not message:
                continue
                
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "progress":
                p = data["data"]
                print(f"\r   Progress: {p['value']}/{p['max']} ({p.get('percent', 0):.1f}%)   ", end="", flush=True)
            
            elif msg_type == "executing":
                node = data.get("data", {}).get("node")
                if node:
                    print(f"\r   Executing node: {node}                  ", end="", flush=True)
            
            elif msg_type in ["execution_success", "execution_cached"]:
                print("\r   Generation finished!                       ")
                
                # Now fetch images
                history_resp = requests.get(f"{server_address}/history/{prompt_id}")
                if history_resp.status_code == 200:
                    history = history_resp.json().get(prompt_id, {})
                    outputs = history.get("outputs", {})
                    
                    image_urls = []
                    for node_id in outputs:
                        if "images" in outputs[node_id]:
                            for img in outputs[node_id]["images"]:
                                filename = img["filename"]
                                subfolder = img.get("subfolder", "")
                                type_ = img.get("type", "output")
                                params = f"filename={filename}&type={type_}"
                                if subfolder:
                                    params += f"&subfolder={subfolder}"
                                url = f"{server_address}/view?{params}"
                                image_urls.append(url)
                    
                    if image_urls:
                        print(f" → {len(image_urls)} image(s) ready!")
                        return image_urls
                    else:
                        print(" → No images found")
                        return None
            
            elif msg_type == "execution_error":
                print("\n   ERROR during execution:")
                print(json.dumps(data.get("data", {}), indent=2))
                return None
                
    except Exception as e:
        print(f"\n   WebSocket error: {e}")
    finally:
        ws.close()
    
    return None

# ============================= MAIN =============================
if __name__ == "__main__":
    # Find all JSON workflow files
    workflow_files = [f for f in os.listdir(".") if f.lower().endswith(".json")]
    
    if not workflow_files:
        print("No .json workflow files found in this folder!")
        print("Place your workflow files (e.g., qwen.json, hidream.json) here and try again.")
        sys.exit(1)
    
    # Your default prompt
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