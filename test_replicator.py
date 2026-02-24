"""
PRAQTOR DATΔ — Synthetic Data Generator v7
Fixes: async rendering off, direct USD lights, boost warehouse lights, rt_subframes=16
"""

from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": 1024,
    "height": 1024,
})

print("[PRAQTOR DATA] SimulationApp launched.")

import os
import carb
import omni.usd
import omni.replicator.core as rep
from pxr import Sdf, UsdLux, Gf

carb.settings.get_settings().set("/app/asyncRendering", False)
carb.settings.get_settings().set("/app/asyncRenderingLowLatency", False)
carb.settings.get_settings().set("/omni/replicator/RTSubframes", 16)
print("[PRAQTOR DATA] Async rendering disabled, RTSubframes=16.")

OUTPUT_DIR = "/workspace/output"
NUM_FRAMES = 10
os.makedirs(OUTPUT_DIR, exist_ok=True)

ASSETS = "/workspace/nvidia_assets/Assets/ArchVis/Industrial"
WAREHOUSE_USD = f"{ASSETS}/Stages/IsaacWarehouse.usd"
PALLET_A_USD  = f"{ASSETS}/Pallets/Pallet_A1.usd"
PALLET_B_USD  = f"{ASSETS}/Pallets/Pallet_B1.usd"
CARDBOX_A_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_A1.usd"
CARDBOX_B_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_B1.usd"

print("[PRAQTOR DATA] Loading warehouse...")

with rep.new_layer():

    warehouse = rep.create.from_usd(WAREHOUSE_USD, semantics=[("class", "warehouse")])
    print("[PRAQTOR DATA] Warehouse loaded.")

    for _ in range(10):
        simulation_app.update()

    stage = omni.usd.get_context().get_stage()
    boosted = 0
    for prim in stage.Traverse():
        if prim.IsA(UsdLux.LightAPI):
            intensity_attr = prim.GetAttribute("inputs:intensity")
            if intensity_attr:
                current = intensity_attr.Get() or 1000.0
                intensity_attr.Set(float(current) * 10.0)
                boosted += 1
    print(f"[PRAQTOR DATA] Boosted {boosted} existing warehouse lights x10.")

    dome = stage.DefinePrim("/World/SDG_DomeLight", "DomeLight")
    dome.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(3000.0)

    distant = stage.DefinePrim("/World/SDG_DistantLight", "DistantLight")
    distant.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(8000.0)
    distant.CreateAttribute("inputs:angle", Sdf.ValueTypeNames.Float).Set(1.0)

    rect = stage.DefinePrim("/World/SDG_RectLight", "RectLight")
    rect.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(50000.0)
    rect.CreateAttribute("inputs:width", Sdf.ValueTypeNames.Float).Set(10.0)
    rect.CreateAttribute("inputs:height", Sdf.ValueTypeNames.Float).Set(10.0)
    rect.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(0.0, 0.0, 8.0))
    rect.CreateAttribute("xformOp:rotateXYZ", Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(-90.0, 0.0, 0.0))
    print("[PRAQTOR DATA] Strong USD lights added.")

    pallets = []
    for usd, pos in [(PALLET_A_USD, (0.0, 2.0, 0.0)), (PALLET_B_USD, (3.0, 0.0, 0.0)), (PALLET_A_USD, (-2.0, 3.0, 0.0))]:
        p = rep.create.from_usd(usd, semantics=[("class", "pallet")])
        with p: rep.modify.pose(position=pos)
        pallets.append(p)

    boxes = []
    for usd, pos in [(CARDBOX_A_USD, (0.0, 2.0, 0.18)), (CARDBOX_B_USD, (3.0, 0.0, 0.18)), (CARDBOX_A_USD, (-2.0, 3.0, 0.18))]:
        b = rep.create.from_usd(usd, semantics=[("class", "box")])
        with b: rep.modify.pose(position=pos)
        boxes.append(b)

    print("[PRAQTOR DATA] Assets placed. Setting up camera...")

    camera = rep.create.camera(
        position=(8.0, -6.0, 4.0),
        look_at=(0, 1, 0),
        focal_length=24.0,
        clipping_range=(0.01, 1000.0),
    )
    render_product = rep.create.render_product(camera, (1024, 1024))

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir=OUTPUT_DIR, rgb=True, bounding_box_2d_tight=True, semantic_segmentation=True)
    writer.attach([render_product])

    with rep.trigger.on_frame(max_execs=NUM_FRAMES):
        for p in pallets:
            with p:
                rep.modify.pose(
                    position=rep.distribution.uniform((-4, -2, 0), (4, 5, 0)),
                    rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
                )
        for b in boxes:
            with b:
                rep.modify.pose(
                    position=rep.distribution.uniform((-3, -1, 0.1), (3, 4, 0.18)),
                )

print("[PRAQTOR DATA] Warming up renderer (50 frames)...")
for i in range(50):
    simulation_app.update()
print("[PRAQTOR DATA] Warm-up complete. Capturing with rt_subframes=16...")

for i in range(NUM_FRAMES):
    rep.orchestrator.step(delta_time=0.0, rt_subframes=16)
    print(f"[PRAQTOR DATA] Captured frame {i+1}/{NUM_FRAMES}")

rep.orchestrator.wait_until_complete()
print(f"[PRAQTOR DATA] Done! Output: {OUTPUT_DIR}")
simulation_app.close()
