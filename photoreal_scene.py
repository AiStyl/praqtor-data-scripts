"""
PRAQTOR DATΔ — Photorealistic Scene SDG
========================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090
Run: ./python.sh /workspace/photoreal_scene.py
Output: /workspace/output/

Loads the NVIDIA warehouse environment + real USD assets:
  - Forklift (vehicle)
  - Human characters (pedestrian) — if discovered
  - Traffic cones, pallets, boxes (props)
  - Dome + Distant lighting

Generates 10 annotated images at 1024x1024.
"""

import os
import sys
import time

from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": 1024,
    "height": 1024,
})

print("[PRAQTOR DATΔ] SimulationApp launched.")

import omni.usd
import omni.replicator.core as rep
from omni.isaac.core.utils.stage import open_stage
from omni.isaac.nucleus import get_assets_root_path

OUTPUT_DIR = "/workspace/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 1. Resolve asset root
# ============================================================
assets_root = get_assets_root_path()
if assets_root is None:
    print("[PRAQTOR DATΔ] ERROR: Could not resolve asset root path")
    simulation_app.close()
    sys.exit(1)
print(f"[PRAQTOR DATΔ] Asset root: {assets_root}")

# ============================================================
# 2. Asset paths (confirmed from NVIDIA docs + discovery)
# ============================================================
ENV_URL = assets_root + "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd"
FORKLIFT_URL = assets_root + "/Isaac/Props/Forklift/forklift.usd"
CONE_URL = assets_root + "/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd"
PALLET_URL = assets_root + "/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd"
BOX_URL = assets_root + "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd"

# People — may or may not exist in 4.2. Try loading, fallback to capsule.
PERSON_URL = assets_root + "/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd"

# ============================================================
# 3. Load warehouse environment
# ============================================================
print(f"[PRAQTOR DATΔ] Loading warehouse from S3 (may take 3-5 min first time)...")
if not open_stage(ENV_URL):
    print("[PRAQTOR DATΔ] WARNING: open_stage returned False. Continuing...")

# Give S3 streaming time to complete
print("[PRAQTOR DATΔ] Waiting for stage to stream...")
for i in range(40):
    simulation_app.update()
    if i % 10 == 0:
        print(f"  Loading... {i}/40")
    time.sleep(0.3)

print("[PRAQTOR DATΔ] Stage loaded.")

# ============================================================
# 4. Build Replicator scene on top of warehouse
# ============================================================
with rep.new_layer():

    # ----------------------------------------------------------
    # LIGHTING — warehouse has some internal lights, but we
    # add dome + distant to guarantee headless visibility
    # ----------------------------------------------------------
    dome = rep.create.light(
        light_type="Dome",
        intensity=1500,
        color=(0.9, 0.92, 1.0),
    )

    sun = rep.create.light(
        light_type="Distant",
        intensity=4000,
        color=(1.0, 0.97, 0.90),
        rotation=(60, 30, 0),
    )

    # ----------------------------------------------------------
    # VEHICLES — forklifts with semantic labels
    # ----------------------------------------------------------
    print("[PRAQTOR DATΔ] Spawning forklifts...")
    vehicles = rep.create.from_usd(
        FORKLIFT_URL,
        semantics=[("class", "vehicle")],
        count=3,
    )

    # ----------------------------------------------------------
    # PEDESTRIANS — try real human model, fallback to capsule
    # ----------------------------------------------------------
    print("[PRAQTOR DATΔ] Spawning pedestrians...")
    try:
        from pxr import Sdf
        layer = Sdf.Layer.FindOrOpen(PERSON_URL)
        if layer is not None:
            print("  Using real human character model")
            pedestrians = rep.create.from_usd(
                PERSON_URL,
                semantics=[("class", "pedestrian")],
                count=2,
            )
        else:
            raise Exception("Layer not found")
    except Exception:
        print("  Human model not available, using capsule proxy")
        pedestrians = rep.create.capsule(
            count=3,
            scale=(0.35, 0.35, 1.7),
            semantics=[("class", "pedestrian")],
        )

    # ----------------------------------------------------------
    # PROPS — cones, pallets, boxes for scene richness
    # ----------------------------------------------------------
    print("[PRAQTOR DATΔ] Spawning props...")
    cones = rep.create.from_usd(
        CONE_URL,
        semantics=[("class", "obstacle")],
        count=4,
    )

    pallets = rep.create.from_usd(
        PALLET_URL,
        semantics=[("class", "pallet")],
        count=3,
    )

    boxes = rep.create.from_usd(
        BOX_URL,
        semantics=[("class", "cargo")],
        count=5,
    )

    # ----------------------------------------------------------
    # CAMERA — inside warehouse, looking down aisle
    # Warehouse is ~40m x 40m. Start mid-range, wide angle.
    # ----------------------------------------------------------
    camera = rep.create.camera(
        position=(10, 3, 5),
        look_at=(0, 1, 0),
        focal_length=18.0,
        clipping_range=(0.05, 500.0),
    )

    rp = rep.create.render_product(camera, (1024, 1024))

    # ----------------------------------------------------------
    # WRITER — RGB + bounding boxes + semantic segmentation
    # ----------------------------------------------------------
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=OUTPUT_DIR,
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True,
    )
    writer.attach([rp])

    # ----------------------------------------------------------
    # RANDOMIZATION — objects + camera vary each frame
    # Warehouse floor coords: roughly X: -15 to 15, Z: -15 to 15
    # Y is height (0 = floor)
    # ----------------------------------------------------------
    with rep.trigger.on_frame(max_execs=10):
        with vehicles:
            rep.modify.pose(
                position=rep.distribution.uniform((-12, 0, -12), (12, 0, 12)),
                rotation=rep.distribution.uniform((0, 0, 0), (0, 360, 0)),
            )
        with pedestrians:
            rep.modify.pose(
                position=rep.distribution.uniform((-10, 0, -10), (10, 0, 10)),
            )
        with cones:
            rep.modify.pose(
                position=rep.distribution.uniform((-12, 0, -12), (12, 0, 12)),
            )
        with boxes:
            rep.modify.pose(
                position=rep.distribution.uniform((-14, 0, -14), (14, 0, 14)),
                rotation=rep.distribution.uniform((0, 0, 0), (0, 360, 0)),
            )
        with camera:
            rep.modify.pose(
                position=rep.distribution.uniform((5, 2, 3), (15, 5, 8)),
                look_at=rep.distribution.uniform((-10, 0, -5), (5, 1, 5)),
            )
        with sun:
            rep.modify.attribute(
                "intensity",
                rep.distribution.uniform(2000, 6000),
            )

# ============================================================
# 5. Warm-up — renderer needs frames to initialize with real assets
# ============================================================
print("[PRAQTOR DATΔ] Warming up renderer (25 frames)...")
for i in range(25):
    simulation_app.update()
    if i % 5 == 0:
        print(f"  Warm-up {i}/25")

print("[PRAQTOR DATΔ] Warm-up complete. Starting capture...")

# ============================================================
# 6. Capture
# ============================================================
rep.orchestrator.run_until_complete()

print(f"[PRAQTOR DATΔ] Capture complete! Output: {OUTPUT_DIR}")

# List what we generated
for f in sorted(os.listdir(OUTPUT_DIR)):
    size_kb = os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024
    print(f"  {f} ({size_kb:.0f} KB)")

simulation_app.close()
