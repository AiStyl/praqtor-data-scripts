"""
PRAQTOR DATΔ — Synthetic Data Generator v3
===========================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090
Run: ./python.sh /workspace/test_replicator.py
Output: /workspace/output/

v3 fixes: Removed OmniPBR material binding (broke Replicator graph in v2).
Using primvars:displayColor for object visibility instead.
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

OUTPUT_DIR = "/workspace/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# Build the scene — NO material binding (it breaks the graph)
# ============================================================
with rep.new_layer():

    # LIGHTING — Dome + Distant (headless has NO default lights)
    dome = rep.create.light(
        light_type="Dome",
        intensity=1500,
        rotation=(270, 0, 0),
    )

    sun = rep.create.light(
        light_type="Distant",
        intensity=5000,
        color=(1.0, 0.95, 0.85),
        rotation=(-45, 45, 0),
    )

    # GROUND PLANE
    plane = rep.create.plane(
        scale=(30, 30, 1),
        position=(0, 0, 0),
        semantics=[("class", "road")],
    )

    # VEHICLE 1 — blue cube
    vehicle = rep.create.cube(
        position=(0, 0, 0.6),
        scale=(1.6, 0.9, 0.6),
        semantics=[("class", "vehicle")],
    )

    # PEDESTRIAN — orange sphere
    pedestrian = rep.create.sphere(
        position=(1.5, 0.5, 0.5),
        scale=(0.35, 0.35, 1.0),
        semantics=[("class", "pedestrian")],
    )

    # VEHICLE 2 — green cube
    vehicle2 = rep.create.cube(
        position=(-2, 1, 0.6),
        scale=(1.4, 0.8, 0.55),
        semantics=[("class", "vehicle")],
    )

    # CAMERA — close, wide angle
    camera = rep.create.camera(
        position=(6.0, -6.0, 3.5),
        look_at=(0, 0, 0.5),
        focal_length=24.0,
        clipping_range=(0.05, 200.0),
    )

    render_product = rep.create.render_product(camera, (1024, 1024))

    # WRITER — RGB + bounding boxes + segmentation
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=OUTPUT_DIR,
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True,
    )
    writer.attach([render_product])

    # RANDOMIZATION
    with rep.trigger.on_frame(max_execs=10):
        with vehicle:
            rep.modify.pose(
                position=rep.distribution.uniform((-2.5, -2.5, 0.4), (2.5, 2.5, 0.9)),
                rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
            )
        with vehicle2:
            rep.modify.pose(
                position=rep.distribution.uniform((-3, -3, 0.4), (3, 3, 0.8)),
                rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
            )
        with pedestrian:
            rep.modify.pose(
                position=rep.distribution.uniform((-2.5, -2.5, 0.35), (2.5, 2.5, 0.8)),
            )
        with sun:
            rep.modify.attribute("intensity", rep.distribution.uniform(3000, 7000))

# ============================================================
# WARM-UP — 25 frames for renderer initialization
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

simulation_app.close()
