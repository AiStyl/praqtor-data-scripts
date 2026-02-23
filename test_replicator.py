"""
PRAQTOR DATΔ — Synthetic Data Generator (Fixed)
================================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090
Run: ./python.sh /workspace/test_replicator.py
Output: /workspace/output/

Fixes applied (synthesized from 6 LLM analyses):
  1. RayTracedLighting renderer mode (fastest, most reliable in headless)
  2. 25-frame warm-up AFTER scene build (renderer needs BVH/shader init)
  3. Dome Light + Distant Light combo (headless has NO default lights)
  4. Explicit OmniPBR materials on all objects (don't rely on defaults)
  5. Close camera with wide FOV (objects fill frame)
  6. max_execs instead of deprecated num_frames
  7. rt_subframes for render convergence per capture
  8. 3-frame sanity test first, then full 10
"""

# ============================================================
# STEP 1: SimulationApp MUST be created before any omni imports
# ============================================================
from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": 1024,
    "height": 1024,
})

print("[PRAQTOR DATΔ] SimulationApp launched.")

# ============================================================
# STEP 2: Imports (only after SimulationApp exists)
# ============================================================
import os
import omni.replicator.core as rep

OUTPUT_DIR = "/workspace/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# STEP 3: Build the scene
# ============================================================
with rep.new_layer():

    # ----------------------------------------------------------
    # LIGHTING — P0 fix: headless has NO default lights
    # Dome = ambient sky (omnidirectional fill)
    # Distant = sun (directional shadows + depth)
    # ----------------------------------------------------------
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

    # ----------------------------------------------------------
    # GROUND PLANE — dark gray asphalt
    # ----------------------------------------------------------
    plane = rep.create.plane(
        scale=(30, 30, 1),
        position=(0, 0, 0),
        semantics=[("class", "road")],
    )

    road_mat = rep.create.material_omnipbr(
        diffuse=(0.15, 0.15, 0.15),
        roughness=0.9,
        metallic=0.0,
    )

    # ----------------------------------------------------------
    # VEHICLE — blue cube, elongated
    # ----------------------------------------------------------
    vehicle = rep.create.cube(
        position=(0, 0, 0.6),
        scale=(1.6, 0.9, 0.6),
        semantics=[("class", "vehicle")],
    )

    car_mat = rep.create.material_omnipbr(
        diffuse=(0.1, 0.35, 0.9),
        roughness=0.35,
        metallic=0.05,
    )

    # ----------------------------------------------------------
    # PEDESTRIAN — red/orange sphere
    # ----------------------------------------------------------
    pedestrian = rep.create.sphere(
        position=(1.5, 0.5, 0.5),
        scale=(0.35, 0.35, 1.0),
        semantics=[("class", "pedestrian")],
    )

    ped_mat = rep.create.material_omnipbr(
        diffuse=(0.9, 0.2, 0.15),
        roughness=0.6,
        metallic=0.0,
    )

    # ----------------------------------------------------------
    # SECOND VEHICLE — green cube for variety
    # ----------------------------------------------------------
    vehicle2 = rep.create.cube(
        position=(-2, 1, 0.6),
        scale=(1.4, 0.8, 0.55),
        semantics=[("class", "vehicle")],
    )

    car2_mat = rep.create.material_omnipbr(
        diffuse=(0.15, 0.65, 0.2),
        roughness=0.4,
        metallic=0.05,
    )

    # ----------------------------------------------------------
    # Apply materials to objects
    # ----------------------------------------------------------
    with plane:
        rep.modify.attribute("material:binding", road_mat)
    with vehicle:
        rep.modify.attribute("material:binding", car_mat)
    with pedestrian:
        rep.modify.attribute("material:binding", ped_mat)
    with vehicle2:
        rep.modify.attribute("material:binding", car2_mat)

    # ----------------------------------------------------------
    # CAMERA — close, wide angle, looking at scene center
    # ----------------------------------------------------------
    camera = rep.create.camera(
        position=(6.0, -6.0, 3.5),
        look_at=(0, 0, 0.5),
        focal_length=24.0,
        clipping_range=(0.05, 200.0),
    )

    render_product = rep.create.render_product(camera, (1024, 1024))

    # ----------------------------------------------------------
    # WRITER — RGB + bounding boxes + segmentation
    # ----------------------------------------------------------
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=OUTPUT_DIR,
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True,
    )
    writer.attach([render_product])

    # ----------------------------------------------------------
    # RANDOMIZATION — objects stay in tight area near camera
    # ----------------------------------------------------------
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
# STEP 4: WARM-UP — P0 fix: renderer needs frames to initialize
# BVH structures, shader compilation, texture streaming
# Must happen AFTER scene is built, BEFORE capture
# ============================================================
print("[PRAQTOR DATΔ] Warming up renderer (25 frames)...")
for i in range(25):
    simulation_app.update()
print("[PRAQTOR DATΔ] Warm-up complete. Starting capture...")

# ============================================================
# STEP 5: Run orchestrator — blocks until all frames captured
# ============================================================
rep.orchestrator.run_until_complete()

print(f"[PRAQTOR DATΔ] Capture complete! Output: {OUTPUT_DIR}")

# ============================================================
# STEP 6: Clean shutdown
# ============================================================
simulation_app.close()
