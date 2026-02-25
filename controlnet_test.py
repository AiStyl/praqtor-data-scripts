import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from PIL import Image
import requests
from io import BytesIO
import cv2
import numpy as np
import os

os.makedirs("/workspace/outputs", exist_ok=True)

print("Downloading warehouse image...")
url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/48/Warehouse_with_pallets.jpg/1280px-Warehouse_with_pallets.jpg"
response = requests.get(url)
img = Image.open(BytesIO(response.content)).convert("RGB").resize((512, 512))
img.save("/workspace/outputs/input_warehouse.png")
print("Saved input image")

print("Loading models (first run downloads ~4GB to /workspace/models)...")
controlnet = ControlNetModel.from_pretrained(
    "lllyasviel/sd-controlnet-canny",
    torch_dtype=torch.float16,
    cache_dir="/workspace/models"
)
pipe = StableDiffusionControlNetPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    controlnet=controlnet,
    torch_dtype=torch.float16,
    cache_dir="/workspace/models"
).to("cuda")
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)

img_np = np.array(img)
edges = cv2.Canny(img_np, 100, 200)
canny_img = Image.fromarray(edges)
canny_img.save("/workspace/outputs/canny_edges.png")
print("Canny edges saved")

print("Generating forklift variant...")
result = pipe(
    prompt="warehouse interior with yellow forklift, industrial lighting, photorealistic, 8k",
    negative_prompt="blurry, cartoon, painting, unrealistic",
    image=canny_img,
    num_inference_steps=20,
    guidance_scale=7.5
).images[0]
result.save("/workspace/outputs/forklift_variant.png")
print("SUCCESS - /workspace/outputs/forklift_variant.png")
