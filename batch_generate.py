import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from PIL import Image
import requests
from io import BytesIO
import cv2
import numpy as np
import json
import os
from datetime import datetime

os.makedirs("/workspace/outputs/batch", exist_ok=True)
os.makedirs("/workspace/outputs/batch/images", exist_ok=True)
os.makedirs("/workspace/outputs/batch/annotations", exist_ok=True)

SCENARIOS = [
    {
        "id": 1,
        "name": "near_miss",
        "label": "Near Miss — Forklift + Worker",
        "prompt": "warehouse interior with yellow forklift dangerously close to worker in safety vest, industrial lighting, photorealistic, 8k, high detail",
        "negative": "blurry, cartoon, painting, unrealistic, empty"
    },
    {
        "id": 2,
        "name": "pedestrian_crossing",
        "label": "Pedestrian Crossing Active Lane",
        "prompt": "warehouse worker in orange safety vest crossing forklift lane, yellow floor markings, industrial warehouse interior, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, unrealistic"
    },
    {
        "id": 3,
        "name": "robot_human",
        "label": "Robot + Human Mixed Operations",
        "prompt": "autonomous mobile robot and warehouse worker sharing aisle, modern warehouse interior, industrial lighting, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, unrealistic"
    },
    {
        "id": 4,
        "name": "night_shift",
        "label": "Night Shift Low Visibility",
        "prompt": "warehouse interior at night with dim overhead lighting, forklift operating, dark atmosphere, industrial, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, bright daylight"
    },
    {
        "id": 5,
        "name": "normal_operations",
        "label": "Normal Operations — Baseline",
        "prompt": "warehouse interior with yellow forklift moving pallets, clear aisles, bright industrial lighting, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, unrealistic, people"
    }
]

print("Loading input image...")
input_path = "/workspace/outputs/input_warehouse.png"
if not os.path.exists(input_path):
    url = "https://images.pexels.com/photos/1267338/pexels-photo-1267338.jpeg"
    response = requests.get(url)
    img = Image.open(BytesIO(response.content)).convert("RGB").resize((512, 512))
    img.save(input_path)
    print("Downloaded fresh input image")
else:
    img = Image.open(input_path).convert("RGB")
    print("Using cached input image")

print("Extracting canny edges...")
img_np = np.array(img)
edges = cv2.Canny(img_np, 100, 200)
canny_img = Image.fromarray(edges)
canny_img.save("/workspace/outputs/batch/canny_edges.png")

print("Loading ControlNet pipeline...")
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
print("Pipeline loaded")

# COCO structure
coco = {
    "info": {
        "description": "PRAQTOR DATA Synthetic Warehouse Safety Dataset",
        "version": "1.0",
        "date_created": datetime.now().isoformat()
    },
    "images": [],
    "annotations": [],
    "categories": [
        {"id": 1, "name": "forklift", "supercategory": "vehicle"},
        {"id": 2, "name": "worker", "supercategory": "person"},
        {"id": 3, "name": "robot", "supercategory": "vehicle"}
    ]
}

annotation_id = 1

print("\n=== GENERATING 5 SCENARIOS ===\n")

for scenario in SCENARIOS:
    print(f"Generating scenario {scenario['id']}/5: {scenario['label']}...")

    result = pipe(
        prompt=scenario["prompt"],
        negative_prompt=scenario["negative"],
        image=canny_img,
        num_inference_steps=25,
        guidance_scale=8.0,
        generator=torch.Generator(device="cuda").manual_seed(scenario["id"] * 42)
    ).images[0]

    filename = f"scenario_{scenario['id']:02d}_{scenario['name']}.png"
    filepath = f"/workspace/outputs/batch/images/{filename}"
    result.save(filepath)
    print(f"  Saved: {filename}")

    # Add to COCO images
    coco["images"].append({
        "id": scenario["id"],
        "file_name": filename,
        "width": 512,
        "height": 512,
        "scenario": scenario["label"]
    })

    # Simple bounding box via edge detection on output
    result_np = np.array(result.convert("RGB"))
    result_gray = cv2.cvtColor(result_np, cv2.COLOR_RGB2GRAY)

    # Find the dominant object region (simplified bbox via contours)
    _, thresh = cv2.threshold(result_gray, 80, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Get largest contour as primary object
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        area = w * h

        # Only add if reasonable size
        if area > 1000:
            cat_id = 1  # default forklift
            if "worker" in scenario["name"] or "pedestrian" in scenario["name"]:
                cat_id = 2
            elif "robot" in scenario["name"]:
                cat_id = 3

            coco["annotations"].append({
                "id": annotation_id,
                "image_id": scenario["id"],
                "category_id": cat_id,
                "bbox": [int(x), int(y), int(w), int(h)],
                "area": int(area),
                "iscrowd": 0
            })
            annotation_id += 1
            print(f"  Bbox: [{x}, {y}, {w}, {h}] area={area}")

print("\nSaving COCO annotations...")
with open("/workspace/outputs/batch/annotations/coco_annotations.json", "w") as f:
    json.dump(coco, f, indent=2)

# Save metadata
metadata = {
    "generated": datetime.now().isoformat(),
    "pipeline": "ControlNet Canny + SD v1.5",
    "input_image": "pexels warehouse photo",
    "scenarios": len(SCENARIOS),
    "gpu": "RTX 4090",
    "inference_steps": 25,
    "guidance_scale": 8.0
}
with open("/workspace/outputs/batch/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("\n=== COMPLETE ===")
print(f"Images: /workspace/outputs/batch/images/")
print(f"Annotations: /workspace/outputs/batch/annotations/coco_annotations.json")
print(f"Metadata: /workspace/outputs/batch/metadata.json")
