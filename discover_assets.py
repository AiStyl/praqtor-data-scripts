"""
PRAQTOR DATΔ — Asset Discovery Script
======================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090
Run: ./python.sh /workspace/discover_assets.py
Cost: ~$0.05 (runs in ~2 minutes)

Maps ALL available 3D assets on NVIDIA's S3 server.
Run this FIRST before any rendering to know what we have.
"""

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

print("[PRAQTOR DATΔ] SimulationApp launched. Starting asset discovery...")

import omni.client
from omni.isaac.nucleus import get_assets_root_path
from pxr import Sdf

# Warm up
for _ in range(10):
    simulation_app.update()

assets_root = get_assets_root_path()
print(f"[PRAQTOR DATΔ] Asset root: {assets_root}")

# ============================================================
# METHOD 1: omni.client.list() — native Omniverse directory listing
# ============================================================
def list_recursive(path, depth=0, max_depth=3, results=None):
    if results is None:
        results = []
    if depth > max_depth:
        return results
    result, entries = omni.client.list(path)
    if result == omni.client.Result.OK:
        for entry in entries:
            is_dir = entry.flags & omni.client.ItemFlags.CAN_HAVE_CHILDREN
            full_path = f"{path}/{entry.relative_path}"
            prefix = "  " * depth
            marker = "/" if is_dir else ""
            print(f"{prefix}{entry.relative_path}{marker}")
            results.append({"path": full_path, "is_dir": bool(is_dir)})
            if is_dir:
                list_recursive(full_path, depth + 1, max_depth, results)
    else:
        print(f"{'  ' * depth}[LISTING FAILED: {result}]")
    return results

print(f"\n{'='*70}")
print("DIRECTORY LISTING (omni.client.list)")
print(f"{'='*70}")

directories_to_scan = [
    ("ENVIRONMENTS", f"{assets_root}/Isaac/Environments", 2),
    ("PROPS", f"{assets_root}/Isaac/Props", 2),
    ("ROBOTS/VEHICLES", f"{assets_root}/Isaac/Robots", 2),
    ("PEOPLE", f"{assets_root}/Isaac/People", 3),
    ("MATERIALS", f"{assets_root}/Isaac/Materials", 1),
    ("SAMPLES", f"{assets_root}/Isaac/Samples", 2),
    ("SENSORS", f"{assets_root}/Isaac/Sensors", 2),
]

all_results = {}
for label, path, depth in directories_to_scan:
    print(f"\n--- {label} ---")
    simulation_app.update()
    all_results[label] = list_recursive(path, max_depth=depth)

# Also check one level up for non-Isaac content (HDRI skies, SimReady)
base_url = assets_root.rsplit("/Isaac", 1)[0] if "/Isaac" in assets_root else assets_root
print(f"\n--- BASE LEVEL (looking for HDRI/SimReady) ---")
list_recursive(base_url, max_depth=1)

# ============================================================
# METHOD 2: Direct path probing — confirms specific known assets
# ============================================================
print(f"\n{'='*70}")
print("DIRECT PATH PROBING (Sdf.Layer.FindOrOpen)")
print(f"{'='*70}")

KNOWN_PATHS = {
    "ENVIRONMENTS": [
        "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
        "/Isaac/Environments/Simple_Warehouse/warehouse.usd",
        "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
        "/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
        "/Isaac/Environments/Simple_Room/simple_room.usd",
        "/Isaac/Environments/Hospital/hospital.usd",
        "/Isaac/Environments/Office/office.usd",
        "/Isaac/Environments/Grid/default_environment.usd",
        "/Isaac/Environments/Grid/gridroom_black.usd",
        "/Isaac/Environments/Grid/gridroom_curved.usd",
        "/Isaac/Environments/Jetracer/jetracer_track_solid.usd",
    ],
    "VEHICLES": [
        "/Isaac/Props/Forklift/forklift.usd",
        "/Isaac/Robots/Vehicle/basic_vehicle_m.usd",
        "/Isaac/Robots/NVIDIA/Leatherback/leatherback.usd",
        "/Isaac/Robots/Carter/carter_v1.usd",
        "/Isaac/Robots/Carter/nova_carter.usd",
        "/Isaac/Robots/NVIDIA/Jetbot/jetbot.usd",
        "/Isaac/Robots/AgilexRobotics/limo/limo.usd",
    ],
    "PEOPLE": [
        "/Isaac/People/Characters/original_male_adult_police_04/male_adult_police_04.usd",
        "/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd",
        "/Isaac/People/Characters/original_female_adult_police_02/female_adult_police_02.usd",
        "/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd",
    ],
    "WAREHOUSE_PROPS": [
        "/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxA_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxB_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_BarelPlastic_A_01.usd",
    ],
    "HUMANOIDS": [
        "/Isaac/Robots/Humanoid/humanoid.usd",
        "/Isaac/Robots/Humanoid/humanoid_instanceable.usd",
    ],
    "SAMPLES": [
        "/Isaac/Samples/NvBlox/nvblox_sample_scene.usd",
    ],
    "SPECULATIVE_OUTDOOR": [
        "/Isaac/Environments/Road/road.usd",
        "/Isaac/Environments/Street/street.usd",
        "/Isaac/Environments/Urban/urban.usd",
        "/Isaac/Environments/Highway/highway.usd",
        "/Isaac/Vehicles/Car/car.usd",
        "/NVIDIA/Assets/Skies/venice_sunset_1k.hdr",
    ],
}

found_assets = []
missing_assets = []

for category, paths in KNOWN_PATHS.items():
    print(f"\n--- {category} ---")
    for path in paths:
        full_url = assets_root + path
        try:
            layer = Sdf.Layer.FindOrOpen(full_url)
            if layer is not None:
                print(f"  ✓ FOUND  {path}")
                found_assets.append(path)
            else:
                print(f"  ✗ MISS   {path}")
                missing_assets.append(path)
        except Exception:
            print(f"  ✗ ERROR  {path}")
            missing_assets.append(path)
        simulation_app.update()

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*70}")
print("ASSET DISCOVERY SUMMARY")
print(f"{'='*70}")
print(f"  Found:   {len(found_assets)}")
print(f"  Missing: {len(missing_assets)}")

print(f"\nCOPY-PASTE READY (found assets):")
print("-" * 50)
for path in found_assets:
    print(f'  "{path}"')

print(f"\n{'='*70}")
print("[PRAQTOR DATΔ] Discovery complete. Save this output!")
print(f"{'='*70}")

simulation_app.close()
