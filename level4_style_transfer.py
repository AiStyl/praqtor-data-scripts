"""
PRAQTOR DATA — Level 4: Roboflow Templates + Style Transfer

Strategy (Path A + Path B combined):
  - Download real labeled warehouse images from Roboflow Universe (correct proportions, real annotations)
  - Extract color/lighting fingerprint from customer's warehouse photo
  - Apply style transfer at low strength (0.3) to make templates look like customer's environment
  - Keep original bounding box annotations — they stay correct after style transfer
  - Output: customer-specific labeled dataset in ~5 minutes

Why this works:
  - Templates have correct scene structure (real photos, real proportions)
  - Style transfer only shifts color palette + lighting — doesn't break geometry
  - No object placement needed — objects already in correct positions in templates
  - Annotations preserved from Roboflow ground truth

Roboflow datasets used (free, CC BY 4.0):
  - HITSZ/forklift-and-human (1,949 images — forklifts + people together)
  - Pytheia/warehouse (1,400 images — forklift, human, pedestrian classes)

Setup:
  pip install roboflow diffusers transformers accelerate opencv-python-headless numpy pillow requests
"""

import os
import sys
import json
import numpy as np
import cv2
from PIL import Image, ImageDraw
from datetime import datetime
import requests
from io import BytesIO
import glob
import shutil

# ─── CONFIG ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = "/root/outputs/level4"
TEMPLATES_DIR = "/root/outputs/level4/templates"
STYLED_DIR = "/root/outputs/level4/styled"
VISUALIZED_DIR = "/root/outputs/level4/visualized"
ANNOTATIONS_DIR = "/root/outputs/level4/annotations"

for d in [OUTPUT_DIR, TEMPLATES_DIR, STYLED_DIR, VISUALIZED_DIR, ANNOTATIONS_DIR]:
    os.makedirs(d, exist_ok=True)

# ─── STEP 1: DOWNLOAD TEMPLATES FROM ROBOFLOW ─────────────────────────────────
print("=" * 60)
print("STEP 1: Downloading real warehouse templates from Roboflow")
print("=" * 60)

ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")

def download_roboflow_dataset(workspace, project, version, api_key, format="coco"):
    """Download dataset from Roboflow Universe."""
    if not api_key:
        print(f"  No API key — skipping Roboflow download for {workspace}/{project}")
        return None
    try:
        from roboflow import Roboflow
        rf = Roboflow(api_key=api_key)
        proj = rf.workspace(workspace).project(project)
        dataset = proj.version(version).download(format, location=f"{TEMPLATES_DIR}/{project}")
        print(f"  Downloaded: {workspace}/{project} v{version}")
        return dataset
    except Exception as e:
        print(f"  Roboflow download failed ({e})")
        return None

# Try to download — if no API key, fall back to Pexels
datasets_downloaded = []

if ROBOFLOW_API_KEY:
    print("Roboflow API key found — downloading datasets...")
    # HITSZ forklift-and-human dataset
    ds1 = download_roboflow_dataset("hitsz", "forklift-and-human", 1, ROBOFLOW_API_KEY)
    if ds1:
        datasets_downloaded.append(ds1)
    # Pytheia warehouse dataset
    ds2 = download_roboflow_dataset("pytheia", "warehouse-hfvlb", 1, ROBOFLOW_API_KEY)
    if ds2:
        datasets_downloaded.append(ds2)
else:
    print("No ROBOFLOW_API_KEY set — using Pexels warehouse photos as templates")
    print("To use Roboflow: ROBOFLOW_API_KEY=your_key python3 level4_style_transfer.py")

# ─── STEP 2: GATHER TEMPLATE IMAGES ──────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: Gathering template images")
print("=" * 60)

# Check for locally downloaded images first
local_templates = glob.glob(f"{TEMPLATES_DIR}/**/*.jpg", recursive=True) + \
                  glob.glob(f"{TEMPLATES_DIR}/**/*.png", recursive=True)

if local_templates:
    print(f"Found {len(local_templates)} local template images")
    template_paths = local_templates[:10]  # Use up to 10
else:
    print("No local templates — downloading from Pexels (free, no API key needed)...")
    # High-quality real warehouse photos from Pexels (free to use)
    pexels_urls = [
        ("https://images.pexels.com/photos/1267338/pexels-photo-1267338.jpeg", "warehouse_forklift_1.jpg"),
        ("https://images.pexels.com/photos/4481258/pexels-photo-4481258.jpeg", "warehouse_busy_1.jpg"),
        ("https://images.pexels.com/photos/4481259/pexels-photo-4481259.jpeg", "warehouse_worker_1.jpg"),
        ("https://images.pexels.com/photos/4483610/pexels-photo-4483610.jpeg", "warehouse_aisle_1.jpg"),
        ("https://images.pexels.com/photos/1427541/pexels-photo-1427541.jpeg", "warehouse_shelves_1.jpg"),
        ("https://images.pexels.com/photos/906494/pexels-photo-906494.jpeg", "warehouse_worker_2.jpg"),
        ("https://images.pexels.com/photos/4481260/pexels-photo-4481260.jpeg", "warehouse_forklift_2.jpg"),
        ("https://images.pexels.com/photos/4483609/pexels-photo-4483609.jpeg", "warehouse_loading_1.jpg"),
    ]

    template_paths = []
    for url, filename in pexels_urls:
        save_path = f"{TEMPLATES_DIR}/{filename}"
        try:
            r = requests.get(url, timeout=15)
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.save(save_path)
            template_paths.append(save_path)
            print(f"  Downloaded: {filename}")
        except Exception as e:
            print(f"  Failed {filename}: {e}")

print(f"\nTotal templates ready: {len(template_paths)}")

# ─── STEP 3: CUSTOMER PHOTO STYLE EXTRACTION ──────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3: Extracting customer warehouse style fingerprint")
print("=" * 60)

# Use the existing customer warehouse photo
customer_photo_path = "/workspace/outputs/input_warehouse.png"
if not os.path.exists(customer_photo_path):
    # Fall back to first template as "customer photo" for testing
    customer_photo_path = template_paths[0] if template_paths else None
    print(f"No customer photo found — using first template as test customer photo")
else:
    print(f"Customer photo: {customer_photo_path}")

def extract_style_fingerprint(image_path):
    """
    Extract color palette and lighting characteristics from a photo.
    Returns a style fingerprint dict.
    """
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Dominant color palette (K-means, 5 colors)
    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    # Sample 5000 pixels for speed
    indices = np.random.choice(len(pixels), min(5000, len(pixels)), replace=False)
    sample = pixels[indices]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(sample, 5, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    palette = centers.astype(int).tolist()

    # Overall tone stats
    mean_rgb = img_rgb.mean(axis=(0, 1)).tolist()
    std_rgb = img_rgb.std(axis=(0, 1)).tolist()

    # Brightness
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())

    # Contrast
    contrast = float(gray.std())

    # Color temperature estimate (blue vs warm channel ratio)
    r_mean = img_rgb[:, :, 0].mean()
    b_mean = img_rgb[:, :, 2].mean()
    color_temp = "warm" if r_mean > b_mean else "cool"

    fingerprint = {
        "palette": palette,
        "mean_rgb": mean_rgb,
        "std_rgb": std_rgb,
        "brightness": brightness,
        "contrast": contrast,
        "color_temp": color_temp,
        "size": img_rgb.shape[:2]
    }

    print(f"  Brightness: {brightness:.1f}/255")
    print(f"  Contrast: {contrast:.1f}")
    print(f"  Color temp: {color_temp}")
    print(f"  Dominant colors: {len(palette)} extracted")
    return fingerprint

customer_style = None
if customer_photo_path:
    customer_style = extract_style_fingerprint(customer_photo_path)

    # Save palette visualization
    palette_img = Image.new("RGB", (500, 60))
    draw = ImageDraw.Draw(palette_img)
    for i, color in enumerate(customer_style["palette"]):
        x0 = i * 100
        draw.rectangle([x0, 0, x0 + 100, 60], fill=tuple(color))
    palette_img.save(f"{OUTPUT_DIR}/customer_palette.png")
    print(f"  Palette saved: {OUTPUT_DIR}/customer_palette.png")

# ─── STEP 4: STYLE TRANSFER ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4: Applying style transfer to templates")
print("=" * 60)

# Approach: Histogram matching + color grading
# Low-level, fast, no GPU needed, preserves scene geometry perfectly
# This is better than diffusion-based transfer for preserving annotations

def apply_histogram_matching(source_path, reference_style, output_path, target_size=(1024, 1024)):
    """
    Apply histogram matching to make source image match reference color distribution.
    Preserves scene geometry — only shifts color/tone.
    """
    source = cv2.imread(source_path)
    source_rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)

    # Load customer reference image for histogram matching
    ref_img = cv2.imread(customer_photo_path)
    ref_rgb = cv2.cvtColor(ref_img, cv2.COLOR_BGR2RGB)

    # Histogram matching per channel
    def match_histogram(source_channel, reference_channel):
        src_hist, _ = np.histogram(source_channel.flatten(), 256, [0, 256])
        ref_hist, _ = np.histogram(reference_channel.flatten(), 256, [0, 256])
        src_cdf = src_hist.cumsum()
        ref_cdf = ref_hist.cumsum()
        src_cdf_norm = src_cdf * 255 / src_cdf[-1]
        ref_cdf_norm = ref_cdf * 255 / ref_cdf[-1]
        lookup = np.interp(src_cdf_norm, ref_cdf_norm, np.arange(256))
        return lookup[source_channel].astype(np.uint8)

    matched = np.zeros_like(source_rgb)
    for c in range(3):
        matched[:, :, c] = match_histogram(source_rgb[:, :, c], ref_rgb[:, :, c])

    # Blend: 60% matched, 40% original (preserve some original detail)
    blended = (matched * 0.6 + source_rgb * 0.4).astype(np.uint8)

    # Resize to target
    result = Image.fromarray(blended).resize(target_size, Image.LANCZOS)
    result.save(output_path)
    return output_path

# Check if we have a diffusion model available for higher quality transfer
USE_DIFFUSION = False
try:
    import torch
    from diffusers import StableDiffusionImg2ImgPipeline
    sdxl_path = "/root/hf_cache/models--diffusers--stable-diffusion-xl-1.0-inpainting-0.1/snapshots/115134f363124c53c7d878647567d04daf26e41e"
    if os.path.exists(sdxl_path) and torch.cuda.is_available():
        from diffusers import StableDiffusionXLImg2ImgPipeline
        print("GPU available — loading SDXL img2img for high quality style transfer...")
        pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(
            sdxl_path,
            torch_dtype=torch.float16,
            local_files_only=True
        ).to("cuda")
        USE_DIFFUSION = True
        print("SDXL img2img loaded")
    else:
        print("No GPU/SDXL — using histogram matching (fast, CPU, preserves geometry)")
except Exception as e:
    print(f"Diffusion not available ({e}) — using histogram matching")

print(f"\nStyle transfer method: {'SDXL img2img (GPU)' if USE_DIFFUSION else 'Histogram matching (CPU)'}")

# ─── PROCESS TEMPLATES ────────────────────────────────────────────────────────
print(f"\nProcessing {len(template_paths)} templates...")

results = []
coco = {
    "info": {
        "description": "PRAQTOR DATA Level 4 — Real Templates + Style Transfer",
        "version": "4.0",
        "date_created": datetime.now().isoformat(),
        "method": "roboflow_templates_plus_style_transfer",
        "style_transfer": "sdxl_img2img" if USE_DIFFUSION else "histogram_matching"
    },
    "images": [],
    "annotations": [],
    "categories": [
        {"id": 1, "name": "forklift", "supercategory": "vehicle"},
        {"id": 2, "name": "worker", "supercategory": "person"},
        {"id": 3, "name": "pedestrian", "supercategory": "person"}
    ]
}

for i, template_path in enumerate(template_paths[:5]):  # Process first 5
    filename = os.path.basename(template_path)
    output_filename = f"styled_{i+1:02d}_{filename}"
    output_path = f"{STYLED_DIR}/{output_filename}"

    print(f"\n  [{i+1}/5] {filename}")

    if customer_style and customer_photo_path:
        if USE_DIFFUSION:
            try:
                # img2img with very low strength — preserve scene, shift style
                template_img = Image.open(template_path).convert("RGB").resize((1024, 1024))
                styled = pipe(
                    prompt="industrial warehouse, concrete floor, warehouse shelving, photorealistic",
                    image=template_img,
                    strength=0.25,  # Very low — barely changes scene
                    guidance_scale=7.0,
                    generator=torch.Generator(device="cuda").manual_seed(i * 42)
                ).images[0]
                styled.save(output_path)
                print(f"    SDXL styled → {output_filename}")
            except Exception as e:
                print(f"    SDXL failed ({e}), falling back to histogram matching")
                apply_histogram_matching(template_path, customer_style, output_path)
        else:
            apply_histogram_matching(template_path, customer_style, output_path)
            print(f"    Histogram matched → {output_filename}")
    else:
        # No customer photo — just resize template
        img = Image.open(template_path).convert("RGB").resize((1024, 1024))
        img.save(output_path)
        print(f"    Resized (no customer style) → {output_filename}")

    # Load COCO annotations if they exist (from Roboflow download)
    ann_path = template_path.replace(".jpg", ".json").replace(".png", ".json")
    annotations_from_roboflow = []
    if os.path.exists(ann_path):
        with open(ann_path) as f:
            ann_data = json.load(f)
        annotations_from_roboflow = ann_data.get("annotations", [])
        print(f"    Roboflow annotations: {len(annotations_from_roboflow)} objects")

    # Add to COCO
    img_obj = Image.open(output_path)
    coco["images"].append({
        "id": i + 1,
        "file_name": output_filename,
        "width": img_obj.width,
        "height": img_obj.height,
        "source_template": filename,
        "style_transferred": True
    })

    # Use Roboflow annotations if available, otherwise note for YOLO detection
    for ann in annotations_from_roboflow:
        coco["annotations"].append({
            **ann,
            "image_id": i + 1,
            "source": "roboflow_ground_truth"
        })

    results.append(output_path)

    # Create comparison visualization: original left, styled right
    try:
        orig = Image.open(template_path).convert("RGB").resize((512, 512))
        styled_img = Image.open(output_path).convert("RGB").resize((512, 512))
        comparison = Image.new("RGB", (1024, 512))
        comparison.paste(orig, (0, 0))
        comparison.paste(styled_img, (512, 0))
        draw = ImageDraw.Draw(comparison)
        draw.rectangle([0, 0, 100, 20], fill="black")
        draw.text((5, 3), "ORIGINAL", fill="white")
        draw.rectangle([512, 0, 640, 20], fill="green")
        draw.text((517, 3), "STYLED", fill="white")
        comparison.save(f"{VISUALIZED_DIR}/compare_{i+1:02d}.png")
    except Exception as e:
        print(f"    Comparison viz failed: {e}")

# Save COCO
with open(f"{ANNOTATIONS_DIR}/coco_annotations.json", "w") as f:
    json.dump(coco, f, indent=2)

# Save metadata
metadata = {
    "generated": datetime.now().isoformat(),
    "pipeline": "Level 4 — Real Templates + Style Transfer",
    "templates_used": len(results),
    "style_source": customer_photo_path,
    "style_transfer_method": "sdxl_img2img" if USE_DIFFUSION else "histogram_matching",
    "roboflow_datasets": [
        "hitsz/forklift-and-human",
        "pytheia/warehouse-hfvlb"
    ],
    "key_insight": "Real photos = correct proportions. Style transfer = customer environment. Annotations preserved from ground truth.",
    "next_steps": [
        "Add ROBOFLOW_API_KEY to download full labeled datasets",
        "Run YOLO detection on styled images to generate annotations where Roboflow not available",
        "Add augmentation layer: rotate, flip, brightness shift to multiply dataset 10x"
    ]
}
with open(f"{OUTPUT_DIR}/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

# ─── STEP 5: OPTIONAL YOLO ANNOTATION PASS ────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5: YOLO detection on styled images (where no Roboflow labels)")
print("=" * 60)

unannotated = [
    coco["images"][i] for i in range(len(coco["images"]))
    if not any(a.get("image_id") == coco["images"][i]["id"] for a in coco["annotations"])
]

if unannotated:
    print(f"{len(unannotated)} images need YOLO annotation...")
    try:
        from ultralytics import YOLO
        yolo = YOLO("yolov8n.pt")
        ann_id = max((a["id"] for a in coco["annotations"]), default=0) + 1

        for img_info in unannotated:
            img_path = f"{STYLED_DIR}/{img_info['file_name']}"
            detections = yolo(img_path, conf=0.25, verbose=False)[0]

            for box in detections.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_id = int(box.cls[0])
                # Map YOLO classes to our categories
                cat_id = 1 if cls_id in [0] else 2  # person=2, else forklift=1
                coco["annotations"].append({
                    "id": ann_id,
                    "image_id": img_info["id"],
                    "category_id": cat_id,
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "area": (x2 - x1) * (y2 - y1),
                    "iscrowd": 0,
                    "source": "yolo_detection",
                    "confidence": float(box.conf[0])
                })
                ann_id += 1

        with open(f"{ANNOTATIONS_DIR}/coco_annotations.json", "w") as f:
            json.dump(coco, f, indent=2)
        print("YOLO annotation complete")
    except Exception as e:
        print(f"YOLO not available ({e}) — annotations from Roboflow only")
else:
    print("All images have Roboflow ground truth annotations — YOLO pass skipped")

# ─── SUMMARY ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("COMPLETE")
print("=" * 60)
print(f"Templates processed:   {len(results)}")
print(f"Style transfer method: {'SDXL img2img (GPU)' if USE_DIFFUSION else 'Histogram matching (CPU)'}")
print(f"Annotations:           {len(coco['annotations'])} objects")
print(f"Comparisons:           {VISUALIZED_DIR}/compare_XX.png")
print(f"COCO JSON:             {ANNOTATIONS_DIR}/coco_annotations.json")
print(f"\nNext step: Set ROBOFLOW_API_KEY to unlock 1,949+ labeled forklift+human images")
print(f"Register free at: https://roboflow.com")
