"""
PRAQTOR DATΔ — Synthetic Data Generator v4
===========================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090
Run: /isaac-sim/python.sh test_replicator.py
Output: /workspace/output/

v4: Real NVIDIA warehouse USD + forklift assets from Nucleus/NVIDIA CDN.
Photorealistic RTX rendering with randomized forklifts, lighting, camera.
"""

from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": 1024,
    "height": 1024,
})

print("[PRAQTOR DATΔ] SimulationApp launched.")

import os
import omni.replicator.core as rep
import omni.usd
from pxr import UsdGeom, Sdf

OUTPUT_DIR = "/workspace/output"
NUM_FRAMES = 10
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# NVIDIA Omniverse Asset URLs (publicly accessible via HTTPS)
# ============================================================
WAREHOUSE_URL = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/ArchVis/Industrial/Warehouses/Warehouse01.usd"
FORKLIFT_URL  = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/ArchVis/Industrial/Forklifts/Forklift_A/Forklift_A01_PR_NVD_01.usd"
PALLET_URL    = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/ArchVis/Industrial/Pallets/Pallet_A/Pallet_A01_PR_NVD_01.usd"

print(f"[PRAQTOR DATΔ] Loading warehouse scene from NVIDIA CDN...")

with rep.new_layer():

    # ── WAREHOUSE ENVIRONMENT ──────────────────────────────
    warehouse = rep.create.from_usd(
        WAREHOUSE_URL,
        semantics=[("class", "warehouse")],
    )
    print("[PRAQTOR DATΔ] Warehouse USD loaded.")

    # ── FORKLIFTS (3 instances) ────────────────────────────
    forklift_positions = [
        (0.0,   0.0,  0.0),
        (5.0,   3.0,  0.0),
        (-4.0,  6.0,  0.0),
    ]

    forklifts = []
    for i, pos in enumerate(forklift_positions):
        fl = rep.create.from_usd(
            FORKLIFT_URL,
            semantics=[("class", "forklift")],
        )
        with fl:
            rep.modify.pose(position=pos, rotation=(0, 0, 0))
        forklifts.append(fl)
        print(f"[PRAQTOR DATΔ] Forklift {i+1}/3 loaded.")

    # ── PALLETS (5 instances) ──────────────────────────────
    pallet_positions = [
        ( 2.0,  2.0, 0.0),
        (-2.0,  4.0, 0.0),
        ( 6.0, -1.0, 0.0),
        (-5.0,  1.0, 0.0),
        ( 1.0,  7.0, 0.0),
    ]

    pallets = []
    for i, pos in enumerate(pallet_positions):
        pl = rep.create.from_usd(
            PALLET_URL,
            semantics=[("class", "pallet")],
        )
        with pl:
            rep.modify.pose(position=pos)
        pallets.append(pl)

    print("[PRAQTOR DATΔ] All assets loaded. Setting up lights & camera...")

    # ── LIGHTING ───────────────────────────────────────────
    # Dome for ambient fill
    dome = rep.create.light(
        light_type="Dome",
        intensity=800,
        rotation=(270, 0, 0),
    )

    # Overhead industrial lights (simulate warehouse ceiling lights)
    light1 = rep.create.light(
        light_type="Rect",
        intensity=8000,
        color=(1.0, 0.97, 0.90),
        position=(0, 5, 8),
        rotation=(-90, 0, 0),
        scale=(3, 3, 1),
    )

    light2 = rep.create.light(
        light_type="Rect",
        intensity=8000,
        color=(1.0, 0.97, 0.90),
        position=(8, 5, 8),
        rotation=(-90, 0, 0),
        scale=(3, 3, 1),
    )

    light3 = rep.create.light(
        light_type="Rect",
        intensity=6000,
        color=(0.95, 0.95, 1.0),
        position=(-6, 3, 8),
        rotation=(-90, 0, 0),
        scale=(2, 2, 1),
    )

    # ── CAMERA ─────────────────────────────────────────────
    camera = rep.create.camera(
        position=(12.0, -8.0, 5.0),
        look_at=(0, 3, 0),
        focal_length=28.0,
        clipping_range=(0.1, 500.0),
        f_stop=2.8,
    )

    render_product = rep.create.render_product(camera, (1024, 1024))

    # ── WRITER ─────────────────────────────────────────────
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=OUTPUT_DIR,
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True,
    )
    writer.attach([render_product])

    # ── RANDOMIZATION ──────────────────────────────────────
    with rep.trigger.on_frame(max_execs=NUM_FRAMES):

        # Randomize forklift positions & headings within warehouse floor
        for fl in forklifts:
            with fl:
                rep.modify.pose(
                    position=rep.distribution.uniform((-8, -4, 0), (8, 10, 0)),
                    rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
                )

        # Randomize pallet positions
        for pl in pallets:
            with pl:
                rep.modify.pose(
                    position=rep.distribution.uniform((-7, -3, 0), (7, 9, 0)),
                    rotation=rep.distribution.uniform((0, 0, -90), (0, 0, 90)),
                )

        # Randomize camera position for varied viewpoints
        with camera:
            rep.modify.pose(
                position=rep.distribution.uniform((8, -10, 3), (16, -4, 7)),
                look_at=rep.distribution.uniform((-2, 2, 0), (2, 5, 1)),
            )

        # Randomize lighting intensity to simulate time-of-day / shift changes
        with light1:
            rep.modify.attribute("intensity", rep.distribution.uniform(5000, 12000))
        with light2:
            rep.modify.attribute("intensity", rep.distribution.uniform(5000, 12000))
        with dome:
            rep.modify.attribute("intensity", rep.distribution.uniform(400, 1200))

# ============================================================
# WARM-UP
# ============================================================
print("[PRAQTOR DATΔ] Warming up renderer (25 frames)...")
for i in range(25):
    simulation_app.update()
print("[PRAQTOR DATΔ] Warm-up complete. Starting capture...")

# ============================================================
# RUN
# ============================================================
rep.orchestrator.run_until_complete()

print(f"[PRAQTOR DATΔ] Capture complete! Output: {OUTPUT_DIR}")
print(f"[PRAQTOR DATΔ] Generated {NUM_FRAMES} frames with real NVIDIA assets.")

simulation_app.close()
