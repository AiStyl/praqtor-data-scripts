"""
PRAQTOR DATΔ — Production Script v9
=====================================
Isaac Sim 4.2.0 | Headless | RTX 4090 | RunPod
Target: 5+/10 image quality - proper camera, bright lighting, objects in frame

Key changes from diagnostic:
- Camera elevated and angled DOWN (bird's eye / inspection angle)
- PathTracing renderer for better light quality
- High intensity lights positioned above scene
- Pallets and boxes placed directly in camera view
- rt_subframes=32 for cleaner render
"""

from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "PathTracing",
    "width": 1024,
    "height": 1024,
})

import os
import omni.usd
import omni.replicator.core as rep
import carb
from pxr import UsdGeom, UsdLux, Gf, Sdf

print("[PRAQTOR DATΔ v9] Starting...")

carb.settings.get_settings().set("/app/asyncRendering", False)
carb.settings.get_settings().set("/rtx/pathtracing/spp", 64)

OUTPUT_DIR = "/workspace/output"
NUM_FRAMES = 10
os.makedirs(OUTPUT_DIR, exist_ok=True)

ASSETS = "/workspace/nvidia_assets/Assets/ArchVis/Industrial"
WAREHOUSE_USD = f"{ASSETS}/Stages/IsaacWarehouse.usd"
PALLET_A_USD  = f"{ASSETS}/Pallets/Pallet_A1.usd"
PALLET_B_USD  = f"{ASSETS}/Pallets/Pallet_B1.usd"
CARDBOX_A_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_A1.usd"
CARDBOX_B_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_B1.usd"

# Phase 1: Renderer pre-warm
print("[PRAQTOR DATΔ v9] Phase 1: Renderer pre-warm (20 frames)...")
for _ in range(20):
    simulation_app.update()

# Phase 2: Load warehouse as ROOT stage via open_stage
print(f"[PRAQTOR DATΔ v9] Phase 2: Loading warehouse via open_stage()...")
omni.usd.get_context().open_stage(WAREHOUSE_USD)
print("[PRAQTOR DATΔ v9] Waiting for stage to fully load (60 frames)...")
for i in range(60):
    simulation_app.update()
    if i % 20 == 0:
        print(f"  {i}/60...")

stage = omni.usd.get_context().get_stage()
print(f"[PRAQTOR DATΔ v9] Stage loaded. Root prims: {[p.GetName() for p in stage.GetPseudoRoot().GetChildren()]}")

# Phase 3: Strong lights via USD API on main stage
print("[PRAQTOR DATΔ v9] Phase 3: Adding lights...")

# Dome light - bright ambient
dome = stage.DefinePrim("/World/SDG_Dome", "DomeLight")
dome.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(4000.0)
dome.CreateAttribute("inputs:color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.0, 0.98, 0.95))

# Rect light directly above scene - key light
rect = stage.DefinePrim("/World/SDG_Rect", "RectLight")
rect.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(80000.0)
rect.CreateAttribute("inputs:width", Sdf.ValueTypeNames.Float).Set(15.0)
rect.CreateAttribute("inputs:height", Sdf.ValueTypeNames.Float).Set(15.0)
rect.CreateAttribute("inputs:color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.0, 0.97, 0.9))
rect_xform = UsdGeom.Xformable(rect)
rect_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 12.0))
rect_xform.AddRotateXYZOp().Set(Gf.Vec3f(-90.0, 0.0, 0.0))

# Second fill rect light from the side
rect2 = stage.DefinePrim("/World/SDG_Rect2", "RectLight")
rect2.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(40000.0)
rect2.CreateAttribute("inputs:width", Sdf.ValueTypeNames.Float).Set(10.0)
rect2.CreateAttribute("inputs:height", Sdf.ValueTypeNames.Float).Set(10.0)
rect2_xform = UsdGeom.Xformable(rect2)
rect2_xform.AddTranslateOp().Set(Gf.Vec3d(8.0, 0.0, 8.0))
rect2_xform.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 0.0))

for _ in range(10):
    simulation_app.update()
print("[PRAQTOR DATΔ v9] Lights added.")

# Phase 4: Replicator layer - objects + camera + writer
print("[PRAQTOR DATΔ v9] Phase 4: Setting up Replicator...")

with rep.new_layer():

    # Place pallets in camera view (around origin, spread out)
    pallet_positions = [(0, 0, 0), (2.5, 1.5, 0), (-2.0, 2.0, 0), (1.0, -1.5, 0)]
    pallets = []
    for i, pos in enumerate(pallet_positions):
        usd = PALLET_A_USD if i % 2 == 0 else PALLET_B_USD
        p = rep.create.from_usd(usd, semantics=[("class", "pallet")])
        with p:
            rep.modify.pose(position=pos, rotation=(0, 0, 0))
        pallets.append(p)

    # Stack boxes on top of pallets
    box_positions = [(0, 0, 0.2), (2.5, 1.5, 0.2), (-2.0, 2.0, 0.2)]
    boxes = []
    for i, pos in enumerate(box_positions):
        usd = CARDBOX_A_USD if i % 2 == 0 else CARDBOX_B_USD
        b = rep.create.from_usd(usd, semantics=[("class", "box")])
        with b:
            rep.modify.pose(position=pos)
        boxes.append(b)

    # Camera: high up, angled down 45 degrees — inspection/surveillance angle
    # Warehouse floor at Z=0, objects placed around origin
    # Position at (10, -10, 12) looking at (0, 2, 0) = ~45 deg down angle
    camera = rep.create.camera(
        position=(10.0, -10.0, 12.0),
        look_at=(0.0, 2.0, 0.0),
        focal_length=28.0,
        clipping_range=(0.1, 1000.0),
    )
    render_product = rep.create.render_product(camera, (1024, 1024))

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=OUTPUT_DIR,
        rgb=True,
        bounding_box_2d_tight=True,
        semantic_segmentation=True,
        colorize_semantic_segmentation=True,
    )
    writer.attach([render_product])

    with rep.trigger.on_frame(max_execs=NUM_FRAMES):
        for p in pallets:
            with p:
                rep.modify.pose(
                    position=rep.distribution.uniform((-4, -3, 0), (4, 4, 0)),
                    rotation=rep.distribution.uniform((0, 0, -90), (0, 0, 90)),
                )
        for b in boxes:
            with b:
                rep.modify.pose(
                    position=rep.distribution.uniform((-3, -2, 0.18), (3, 3, 0.18)),
                )

# Phase 5: Final warm-up with everything wired up
print("[PRAQTOR DATΔ v9] Phase 5: Final warm-up (40 frames)...")
for i in range(40):
    simulation_app.update()
    if i % 10 == 0:
        print(f"  {i}/40...")

# Phase 6: Capture with high rt_subframes
print(f"[PRAQTOR DATΔ v9] Phase 6: Capturing {NUM_FRAMES} frames (rt_subframes=32)...")
for i in range(NUM_FRAMES):
    rep.orchestrator.step(delta_time=0.0, rt_subframes=32)
    print(f"  Frame {i+1}/{NUM_FRAMES} captured")

rep.orchestrator.wait_until_complete()
print(f"[PRAQTOR DATΔ v9] Done! Output: {OUTPUT_DIR}")
simulation_app.close()
