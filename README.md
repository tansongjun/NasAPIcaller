# NAS API Caller – ComfyUI Local Runner

Load and run open-source models stored on NAS (Suntec) directly on your local GPU using ComfyUI.

## Quick Start

1. Make sure **ComfyUI server is already running** on your machine  
   (usually at `http://127.0.0.1:8188`)

2. Place your workflow files (`.json`) in the same folder as `main.py`

3. (Optional) Add reference/control images:
   - Put the image in the same folder as `main.py`
   - Name it exactly the same as your workflow file (but with image extension)


4. Run the script:

```bash
python main.py
