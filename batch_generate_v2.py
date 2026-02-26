import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import cv2
import numpy as np
import json
import os
from datetime import datetime

os.makedirs("/workspace/outputs/batch_v2", exist_ok=True)
os.makedirs("/workspace/outputs/batch_v2/images", exist_ok=True)
os.makedirs("/workspace/outputs/batch_v2/annotations", exist_ok=True)
os.makedirs("/workspace/outputs/batch_v2/visualized", exist_ok=True)

SCENARIOS = [
    {
        "id": 1,
        "name": "near_miss",
        "label": "Near Miss — Forklift + Worker",
        "prompt": "warehouse interior with yellow forklift dangerously close to worker in safety vest, industrial lighting, photorealistic, 8k, high detail",
        "negative": "blurry, cartoon, painting, unrealistic, empty",
        "category_id": 1
    },
    {
        "id": 2,
        "name": "pedestrian_crossing",
        "label": "Pedestrian Crossing Active Lane",
        "prompt": "warehouse worker in orange safety vest crossing forklift lane, yellow floor markings, industrial warehouse interior, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, unrealistic",
        "category_id": 2
    },
    {
        "id": 3,
        "name": "robot_human",
        "label": "Robot + Human Mixed Operations",
        "prompt": "autonomous mobile robot and warehouse worker sharing aisle, modern warehouse interior, industrial lighting, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, unrealistic",
        "category_id": 3
    },
    {
        "id": 4,
        "name": "night_shift",
        "label": "Night Shift Low Visibility",
        "prompt": "warehouse interior at night with dim overhead lighting, forklift operating, dark atmosphere, industrial, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, bright daylight",
        "category_id": 1
    },
    {
        "id": 5,
        "name": "normal_operations",
        "label": "Normal Operations — Baseline",
        "prompt": "warehouse interior with yellow forklift moving pallets, clear aisles, bright industrial lighting, photorealistic, 8k",
        "negative": "blurry, cartoon, painting, unrealistic, people",
        "category_id": 1
    }
]

# Install ultralytics if needed
import subprocess
subprocess.run(["pip", "install", "ultralytics", "--quiet"], capture_output=True)
from ultralytics import YOLO

print("Loading YOLOv8 model...")
yolo = YOLO("yolov8n.pt")  # downloads automatically, cached after first run
print("YOLOv8 loaded")

print("Loading input image...")
input_path = "/workspace/outputs/input_warehouse.png"
if not os.path.exists(input_path):
    url = "https://images.pexels.com/photos/1267338/pexels-photo-1267338.jpeg"
    response = requests.get(url)
    img = Image.open(BytesIO(response.content)).convert("RGB").resize((512, 512))
    img.save(input_path)
else:
    img = Image.open(input_path).convert("RGB")
print("Input image ready")

print("Extracting canny edges...")
img_np = np.array(img)
edges = cv2.Canny(img_np, 100, 200)
canny_img = Image.fromarray(edges)

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
        "description": "PRAQTOR DATA Synthetic Warehouse Safety Dataset v2",
        "version": "2.0",
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

# YOLO class mapping to our categories
# YOLO classes: 0=person, 1=bicycle, 2=car, 3=motorcycle, 5=bus, 7=truck
YOLO_TO_CATEGORY = {
    0: 2,   # person -> worker
    7: 1,   # truck -> forklift (closest match)
    2: 1,   # car -> forklift
    3: 1,   # motorcycle -> forklift
}

print("\n=== GENERATING 5 SCENARIOS ===\n")

for scenario in SCENARIOS:
    print(f"Generating {scenario['id']}/5: {scenario['label']}...")

    result = pipe(
        prompt=scenario["prompt"],
        negative_prompt=scenario["negative"],
        image=canny_img,
        num_inference_steps=25,
        guidance_scale=8.0,
        generator=torch.Generator(device="cuda").manual_seed(scenario["id"] * 42)
    ).images[0]

    filename = f"scenario_{scenario['id']:02d}_{scenario['name']}.png"
    filepath = f"/workspace/outputs/batch_v2/images/{filename}"
    result.save(filepath)

    # Run YOLOv8 detection
    yolo_results = yolo(filepath, verbose=False)
    detections = yolo_results[0].boxes

    coco["images"].append({
        "id": scenario["id"],
        "file_name": filename,
        "width": 512,
        "height": 512,
        "scenario": scenario["label"]
    })

    # Draw visualization
    vis_img = result.copy()
    draw = ImageDraw.Draw(vis_img)

    found_boxes = 0
    if detections is not None and len(detections) > 0:
        for box in detections:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            if conf < 0.25:
                continue

            x, y, w, h = int(x1), int(y1), int(x2-x1), int(y2-y1)
            area = w * h

            # Map YOLO class to our category
            cat_id = YOLO_TO_CATEGORY.get(cls, scenario["category_id"])

            coco["annotations"].append({
                "id": annotation_id,
                "image_id": scenario["id"],
                "category_id": cat_id,
                "bbox": [x, y, w, h],
                "area": area,
                "iscrowd": 0,
                "confidence": round(conf, 3),
                "yolo_class": int(cls)
            })

            # Draw box on visualization
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            cat_name = ["", "forklift", "worker", "robot"][cat_id]
            draw.text((x1, y1-12), f"{cat_name} {conf:.2f}", fill="red")

            annotation_id += 1
            found_boxes += 1

    vis_img.save(f"/workspace/outputs/batch_v2/visualized/{filename}")

    if found_boxes > 0:
        print(f"  PASS — {found_boxes} object(s) detected with YOLOv8")
    else:
        print(f"  WARN — No YOLO detections above threshold, using scenario fallback bbox")
        # Fallback: use center region as bbox
        coco["annotations"].append({
            "id": annotation_id,
            "image_id": scenario["id"],
            "category_id": scenario["category_id"],
            "bbox": [128, 128, 256, 256],
            "area": 65536,
            "iscrowd": 0,
            "confidence": 0.0,
            "source": "fallback"
        })
        annotation_id += 1

print("\nSaving COCO annotations...")
with open("/workspace/outputs/batch_v2/annotations/coco_annotations.json", "w") as f:
    json.dump(coco, f, indent=2)

with open("/workspace/outputs/batch_v2/metadata.json", "w") as f:
    json.dump({
        "generated": datetime.now().isoformat(),
        "pipeline": "ControlNet Canny + SD v1.5 + YOLOv8n",
        "version": "2.0",
        "scenarios": len(SCENARIOS),
        "annotation_method": "YOLOv8n object detection",
        "gpu": "RTX 4090",
        "inference_steps": 25,
        "guidance_scale": 8.0
    }, f, indent=2)

print("\n=== COMPLETE ===")
print(f"Images:      /workspace/outputs/batch_v2/images/")
print(f"Visualized:  /workspace/outputs/batch_v2/visualized/  (bboxes drawn)")
print(f"Annotations: /workspace/outputs/batch_v2/annotations/coco_annotations.json")
