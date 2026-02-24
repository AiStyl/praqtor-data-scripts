"""
PRAQTOR DATΔ — Synthetic Data Generator v6
Fixed: Black image issue — explicit lighting + fixed camera + no randomized look_at
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
import omni.replicator.core as rep

OUTPUT_DIR = "/workspace/output"
NUM_FRAMES = 10
os.makedirs(OUTPUT_DIR, exist_ok=True)

ASSETS = "/workspace/nvidia_assets/Assets/ArchVis/Industrial"
WAREHOUSE_USD = f"{ASSETS}/Stages/IsaacWarehouse.usd"
PALLET_A_USD  = f"{ASSETS}/Pallets/Pallet_A1.usd"
PALLET_B_USD  = f"{ASSETS}/Pallets/Pallet_B1.usd"
RACK_USD      = f"{ASSETS}/Racks/RackLarge_A1.usd"
CARDBOX_A_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_A1.usd"

print("[PRAQTOR DATA] Loading warehouse...")

with rep.new_layer():

    # Warehouse scene
    warehouse = rep.create.from_usd(WAREHOUSE_USD, semantics=[("class", "warehouse")])
    print("[PRAQTOR DATA] Warehouse loaded.")

    # Strong explicit lights to guarantee visibility
    rep.create.light(light_type="Dome", intensity=3000, rotation=(270, 0, 0))
    rep.create.light(light_type="Distant", intensity=10000, color=(1.0, 0.98, 0.95), rotation=(-60, 30, 0))
    rep.create.light(light_type="Rect", intensity=15000, color=(1.0, 0.97, 0.9), position=(0, 0, 10), rotation=(-90, 0, 0), scale=(5, 5, 1))

    # Pallets on floor
    pallets = []
    for usd, pos in [(PALLET_A_USD, (0.0, 2.0, 0.0)), (PALLET_B_USD, (3.0, 0.0, 0.0)), (PALLET_A_USD, (-2.0, 3.0, 0.0))]:
        p = rep.create.from_usd(usd, semantics=[("class", "pallet")])
        with p: rep.modify.pose(position=pos)
        pallets.append(p)

    # Boxes on pallets
    boxes = []
    for pos in [(0.0, 2.0, 0.2), (3.0, 0.0, 0.2), (-2.0, 3.0, 0.2)]:
        b = rep.create.from_usd(CARDBOX_A_USD, semantics=[("class", "box")])
        with b: rep.modify.pose(position=pos)
        boxes.append(b)

    print("[PRAQTOR DATA] Assets loaded. Setting up camera...")

    # Fixed camera pointing straight at the scene center — no randomization on look_at
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

    # Only randomize object positions — keep camera fixed
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
                    position=rep.distribution.uniform((-3, -1, 0.1), (3, 4, 0.15)),
                )

print("[PRAQTOR DATA] Warming up (25 frames)...")
for i in range(25):
    simulation_app.update()
print("[PRAQTOR DATA] Warm-up complete. Capturing...")

rep.orchestrator.run_until_complete()
print(f"[PRAQTOR DATA] Done! Output: {OUTPUT_DIR}")
simulation_app.close()
