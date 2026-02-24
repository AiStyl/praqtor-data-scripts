"""
PRAQTOR DATΔ — Synthetic Data Generator v5
===========================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090
Run: /isaac-sim/python.sh test_replicator.py
Output: /workspace/output/

v5: Uses REAL local NVIDIA assets downloaded from official pack.
- IsaacWarehouse.usd — full pre-built warehouse stage
- Pallet_A1/B1/C1.usd — real wooden pallets
- RackLarge_A1.usd — storage racks
- Cardbox_A1/B1.usd — cardboard boxes
- WoodenCrate_A1.usd — wooden crates
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
NUM_FRAMES = 10
os.makedirs(OUTPUT_DIR, exist_ok=True)

ASSETS = "/workspace/nvidia_assets/Assets/ArchVis/Industrial"

WAREHOUSE_USD = f"{ASSETS}/Stages/IsaacWarehouse.usd"
PALLET_A_USD  = f"{ASSETS}/Pallets/Pallet_A1.usd"
PALLET_B_USD  = f"{ASSETS}/Pallets/Pallet_B1.usd"
PALLET_C_USD  = f"{ASSETS}/Pallets/Pallet_C1.usd"
RACK_USD      = f"{ASSETS}/Racks/RackLarge_A1.usd"
CARDBOX_A_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_A1.usd"
CARDBOX_B_USD = f"{ASSETS}/Containers/Cardboard/Cardbox_B1.usd"
CRATE_USD     = f"{ASSETS}/Containers/Wooden/WoodenCrate_A1.usd"

print("[PRAQTOR DATΔ] Loading IsaacWarehouse stage...")

with rep.new_layer():

    warehouse = rep.create.from_usd(WAREHOUSE_USD, semantics=[("class", "warehouse")])
    print("[PRAQTOR DATΔ] Warehouse loaded.")

    rack_positions = [(-8.0, 0.0, 0.0), (-8.0, 4.0, 0.0), (8.0, 0.0, 0.0), (8.0, 4.0, 0.0)]
    racks = []
    for pos in rack_positions:
        r = rep.create.from_usd(RACK_USD, semantics=[("class", "rack")])
        with r:
            rep.modify.pose(position=pos)
        racks.append(r)
    print("[PRAQTOR DATΔ] Racks loaded.")

    pallet_configs = [
        (PALLET_A_USD, (0.0, 2.0, 0.0)), (PALLET_B_USD, (3.0, 0.0, 0.0)),
        (PALLET_C_USD, (-3.0, 3.0, 0.0)), (PALLET_A_USD, (2.0, -2.0, 0.0)),
        (PALLET_B_USD, (-1.0, 5.0, 0.0)),
    ]
    pallets = []
    for usd_path, pos in pallet_configs:
        p = rep.create.from_usd(usd_path, semantics=[("class", "pallet")])
        with p:
            rep.modify.pose(position=pos)
        pallets.append(p)
    print("[PRAQTOR DATΔ] Pallets loaded.")

    box_configs = [
        (CARDBOX_A_USD, (0.0, 2.0, 0.15)), (CARDBOX_B_USD, (3.0, 0.0, 0.15)),
        (CARDBOX_A_USD, (2.0, -2.0, 0.15)), (CARDBOX_B_USD, (-1.0, 5.0, 0.15)),
        (CARDBOX_A_USD, (0.5, 2.5, 0.35)),
    ]
    boxes = []
    for usd_path, pos in box_configs:
        b = rep.create.from_usd(usd_path, semantics=[("class", "box")])
        with b:
            rep.modify.pose(position=pos)
        boxes.append(b)
    print("[PRAQTOR DATΔ] Boxes loaded.")

    crates = []
    for pos in [(-3.0, 3.0, 0.15), (-3.5, 3.0, 0.15)]:
        c = rep.create.from_usd(CRATE_USD, semantics=[("class", "crate")])
        with c:
            rep.modify.pose(position=pos)
        crates.append(c)
    print("[PRAQTOR DATΔ] Crates loaded. Building camera + writer...")

    camera = rep.create.camera(
        position=(10.0, -8.0, 4.5),
        look_at=(0, 2, 0.5),
        focal_length=28.0,
        clipping_range=(0.1, 500.0),
        f_stop=2.8,
    )
    render_product = rep.create.render_product(camera, (1024, 1024))

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir=OUTPUT_DIR, rgb=True, bounding_box_2d_tight=True, semantic_segmentation=True)
    writer.attach([render_product])

    with rep.trigger.on_frame(max_execs=NUM_FRAMES):
        for p in pallets:
            with p:
                rep.modify.pose(
                    position=rep.distribution.uniform((-6, -4, 0), (6, 8, 0)),
                    rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
                )
        for b in boxes:
            with b:
                rep.modify.pose(
                    position=rep.distribution.uniform((-5, -3, 0), (5, 7, 0.2)),
                    rotation=rep.distribution.uniform((0, 0, -90), (0, 0, 90)),
                )
        with camera:
            rep.modify.pose(
                position=rep.distribution.uniform((6, -10, 3), (14, -4, 6)),
                look_at=rep.distribution.uniform((-2, 1, 0), (2, 4, 1)),
            )

print("[PRAQTOR DATΔ] Warming up renderer (25 frames)...")
for i in range(25):
    simulation_app.update()
print("[PRAQTOR DATΔ] Warm-up complete. Starting capture...")

rep.orchestrator.run_until_complete()

print(f"[PRAQTOR DATΔ] Capture complete! Output: {OUTPUT_DIR}")
simulation_app.close()
