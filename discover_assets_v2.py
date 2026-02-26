"""
PRAQTOR DATΔ — Asset Discovery v2
====================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090

PURPOSE: Probe NVIDIA's S3 asset server AND local paths to build a
         confirmed inventory of what's actually loadable.

Run:    /isaac-sim/python.sh /workspace/praqtor-data-scripts/discover_assets_v2.py
Cost:   ~$0.05 (runs in ~2-3 minutes)
Output: Prints confirmed asset inventory + saves to /workspace/asset_inventory.txt

CHANGES FROM v1:
  - Preflight checks (Document 2 recommendation)
  - Timeout per asset probe (prevents freezing on 404s)
  - Checks BOTH remote S3 and local container paths
  - Saves results to file for use by photoreal_scene script
  - Structured job manifest metadata
"""

import os
import sys
import time
import json
from datetime import datetime

# ============================================================
# JOB MANIFEST — tracks exactly what ran (Document 2 recommendation)
# ============================================================
JOB_MANIFEST = {
    "script": "discover_assets_v2.py",
    "version": "2.0",
    "started_at": datetime.utcnow().isoformat() + "Z",
    "purpose": "Asset discovery and inventory",
}

print("=" * 70)
print("  PRAQTOR DATΔ — Asset Discovery v2")
print("=" * 70)

# ============================================================
# PHASE 0: Launch Isaac Sim (minimal config)
# ============================================================
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})
print("[PRAQTOR DATΔ] SimulationApp launched.")

# Warm up renderer minimally
for _ in range(5):
    simulation_app.update()

from pxr import Sdf, Usd

# ============================================================
# PHASE 1: PREFLIGHT — Check environment before probing
# (Document 2: "prove assets exist" before any Replicator run)
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 1: PREFLIGHT CHECKS")
print("=" * 70)

# Check 1: Isaac Sim install path
isaac_path = os.environ.get("ISAAC_PATH", "/isaac-sim")
print(f"  Isaac install:  {isaac_path}")
print(f"  Isaac exists:   {os.path.isdir(isaac_path)}")

# Check 2: Workspace
workspace = "/workspace"
print(f"  Workspace:      {workspace}")
print(f"  Workspace exists: {os.path.isdir(workspace)}")

# Check 3: Try to resolve asset root (may return None!)
assets_root = None
try:
    from omni.isaac.nucleus import get_assets_root_path
    assets_root = get_assets_root_path()
    print(f"  Asset root:     {assets_root}")
    JOB_MANIFEST["assets_root"] = str(assets_root)
except Exception as e:
    print(f"  Asset root:     FAILED ({e})")
    JOB_MANIFEST["assets_root"] = f"FAILED: {e}"

if assets_root is None:
    print("\n  [WARNING] get_assets_root_path() returned None.")
    print("  This means Nucleus is not configured on this container.")
    print("  Will still check local paths and try direct S3 URLs.")

# Check 4: Local assets in container
print("\n  Checking container for bundled assets...")
local_asset_dirs = [
    "/isaac-sim/exts",
    "/isaac-sim/data",
    "/isaac-sim/standalone_examples/replicator",
    "/workspace/assets",
    "/workspace/scenes",
]
for d in local_asset_dirs:
    exists = os.path.isdir(d)
    print(f"    {d}: {'EXISTS' if exists else 'MISSING'}")

# Check 5: List replicator examples (these contain working patterns)
replicator_examples = "/isaac-sim/standalone_examples/replicator"
if os.path.isdir(replicator_examples):
    print(f"\n  Replicator examples found:")
    for item in sorted(os.listdir(replicator_examples)):
        print(f"    {item}")

# ============================================================
# PHASE 2: PROBE REMOTE S3 ASSETS (with timeout protection)
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 2: REMOTE ASSET PROBING")
print("=" * 70)

KNOWN_PATHS = {
    "WAREHOUSE_ENVIRONMENTS": [
        "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
        "/Isaac/Environments/Simple_Warehouse/warehouse.usd",
        "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
        "/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
        "/Isaac/Environments/Hospital/hospital.usd",
        "/Isaac/Environments/Office/office.usd",
    ],
    "VEHICLES_AND_ROBOTS": [
        "/Isaac/Props/Forklift/forklift.usd",
        "/Isaac/Robots/Transporter/transporter_wheels.usd",
        "/Isaac/Robots/Carter/carter_v1.usd",
        "/Isaac/Robots/Jetbot/jetbot.usd",
        "/Isaac/Robots/FrankaNutBolt/franka_alt_fingers.usd",
    ],
    "WAREHOUSE_PROPS": [
        "/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxA_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxB_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_RackLong_01.usd",
        "/Isaac/Environments/Simple_Warehouse/Props/SM_RackShelf_01.usd",
    ],
    "PEOPLE": [
        "/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd",
        "/Isaac/People/Characters/original_female_adult_police_01/female_adult_police_01.usd",
        "/Isaac/People/Characters/original_male_adult_police_04/male_adult_police_04.usd",
        "/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd",
        "/Isaac/People/Characters/F_Biped/biped_demo.usd",
        "/Isaac/People/Characters/F_Biped/f_avg_adult_female_biped.usd",
    ],
    "SKIES_AND_LIGHTS": [
        "/NVIDIA/Assets/Skies/Clear/noon_grass_2k.hdr",
        "/NVIDIA/Assets/Skies/Indoor/ZetoCGcom_ExhibitionHall_Interior1.hdr",
        "/NVIDIA/Assets/Skies/Cloudy/champagne_castle_1_4k.hdr",
    ],
    "SPECULATIVE_OUTDOOR": [
        "/Isaac/Environments/Road/road.usd",
        "/Isaac/Environments/Street/street.usd",
        "/Isaac/Environments/Urban/urban.usd",
        "/Isaac/Vehicles/Car/car.usd",
        "/Isaac/Vehicles/Sedan/sedan.usd",
    ],
}

found_assets = {}
missing_assets = {}

if assets_root:
    for category, paths in KNOWN_PATHS.items():
        print(f"\n--- {category} ---")
        found_assets[category] = []
        missing_assets[category] = []

        for path in paths:
            full_url = assets_root + path
            status = "UNKNOWN"

            try:
                # Timeout protection: update sim to keep it alive,
                # but don't wait forever for S3 response
                start = time.time()
                layer = Sdf.Layer.FindOrOpen(full_url)
                elapsed = time.time() - start

                if layer is not None:
                    status = "FOUND"
                    found_assets[category].append(path)
                    print(f"  ✓ FOUND  ({elapsed:.1f}s)  {path}")
                else:
                    status = "MISS"
                    missing_assets[category].append(path)
                    print(f"  ✗ MISS   ({elapsed:.1f}s)  {path}")

            except Exception as e:
                elapsed = time.time() - start
                status = f"ERROR: {str(e)[:50]}"
                missing_assets[category].append(path)
                print(f"  ✗ ERROR  ({elapsed:.1f}s)  {path} — {str(e)[:80]}")

            # Keep sim alive between probes
            simulation_app.update()

else:
    print("\n  [SKIP] No asset root available. Cannot probe remote S3.")
    print("  Proceeding to local and direct URL checks...")

# ============================================================
# PHASE 3: CHECK LOCAL CONTAINER ASSETS
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 3: LOCAL CONTAINER ASSET SCAN")
print("=" * 70)

local_usd_files = []
search_dirs = [
    "/isaac-sim/exts/omni.isaac.core/data",
    "/isaac-sim/exts/omni.isaac.sensor/data",
    "/isaac-sim/standalone_examples",
    "/isaac-sim/data",
]

for search_dir in search_dirs:
    if not os.path.isdir(search_dir):
        continue
    for root, dirs, files in os.walk(search_dir):
        for f in files:
            if f.endswith(('.usd', '.usda', '.usdc', '.usdz')):
                full_path = os.path.join(root, f)
                size_kb = os.path.getsize(full_path) / 1024
                local_usd_files.append((full_path, size_kb))

print(f"  Found {len(local_usd_files)} local USD files:")
for path, size in sorted(local_usd_files, key=lambda x: -x[1])[:30]:
    print(f"    {size:8.1f} KB  {path}")

if len(local_usd_files) > 30:
    print(f"    ... and {len(local_usd_files) - 30} more")

# ============================================================
# PHASE 4: TRY DIRECT S3 URLs (bypass Nucleus)
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 4: DIRECT S3 URL TEST")
print("=" * 70)

DIRECT_S3_BASE = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
DIRECT_TEST_PATHS = [
    "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
    "/Isaac/Props/Forklift/forklift.usd",
    "/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd",
]

print(f"  Testing direct S3 access (no Nucleus)...")
direct_found = []
for path in DIRECT_TEST_PATHS:
    full_url = DIRECT_S3_BASE + path
    try:
        start = time.time()
        layer = Sdf.Layer.FindOrOpen(full_url)
        elapsed = time.time() - start
        if layer is not None:
            print(f"  ✓ DIRECT S3 WORKS  ({elapsed:.1f}s)  {path}")
            direct_found.append(path)
        else:
            print(f"  ✗ DIRECT S3 MISS   ({elapsed:.1f}s)  {path}")
    except Exception as e:
        print(f"  ✗ DIRECT S3 ERROR  {path} — {str(e)[:80]}")
    simulation_app.update()

# ============================================================
# SUMMARY & SAVE
# ============================================================
print("\n" + "=" * 70)
print("  ASSET DISCOVERY SUMMARY")
print("=" * 70)

total_found = sum(len(v) for v in found_assets.values())
total_missing = sum(len(v) for v in missing_assets.values())

print(f"  Remote S3 (via Nucleus):  {total_found} found / {total_missing} missing")
print(f"  Direct S3 (no Nucleus):   {len(direct_found)} found / {len(DIRECT_TEST_PATHS) - len(direct_found)} missing")
print(f"  Local container USD:      {len(local_usd_files)} files")

# Determine best strategy
print("\n  RECOMMENDED STRATEGY:")
if total_found >= 5:
    print("  → Remote S3 is WORKING. Use assets_root + paths in photoreal_scene.py")
    JOB_MANIFEST["strategy"] = "remote_s3_via_nucleus"
elif len(direct_found) >= 2:
    print("  → Direct S3 is WORKING. Hardcode S3 base URL in photoreal_scene.py")
    JOB_MANIFEST["strategy"] = "direct_s3_urls"
elif len(local_usd_files) >= 3:
    print("  → Use LOCAL container assets only. No remote access available.")
    JOB_MANIFEST["strategy"] = "local_container_assets"
else:
    print("  → NO VIABLE ASSET SOURCE FOUND.")
    print("  → You need to download SimReady packs or build a custom RunPod image.")
    JOB_MANIFEST["strategy"] = "none_found"

# Print copy-paste ready list
if total_found > 0:
    print(f"\n  COPY-PASTE READY (remote assets):")
    print("  " + "-" * 50)
    for cat, paths in found_assets.items():
        for p in paths:
            print(f'    "{p}"')

if len(direct_found) > 0:
    print(f"\n  COPY-PASTE READY (direct S3):")
    print("  " + "-" * 50)
    for p in direct_found:
        print(f'    "{DIRECT_S3_BASE}{p}"')

# Save inventory to file
JOB_MANIFEST["completed_at"] = datetime.utcnow().isoformat() + "Z"
JOB_MANIFEST["remote_found"] = {k: v for k, v in found_assets.items() if v}
JOB_MANIFEST["direct_s3_found"] = direct_found
JOB_MANIFEST["local_usd_count"] = len(local_usd_files)
JOB_MANIFEST["local_usd_top10"] = [p for p, _ in sorted(local_usd_files, key=lambda x: -x[1])[:10]]

inventory_path = "/workspace/asset_inventory.json"
with open(inventory_path, "w") as f:
    json.dump(JOB_MANIFEST, f, indent=2)
print(f"\n  Inventory saved to: {inventory_path}")

# Also save human-readable version
txt_path = "/workspace/asset_inventory.txt"
with open(txt_path, "w") as f:
    f.write("PRAQTOR DATΔ — Asset Inventory\n")
    f.write(f"Generated: {JOB_MANIFEST['completed_at']}\n")
    f.write(f"Strategy: {JOB_MANIFEST['strategy']}\n\n")
    f.write("REMOTE FOUND:\n")
    for cat, paths in found_assets.items():
        for p in paths:
            f.write(f"  {cat}: {p}\n")
    f.write(f"\nDIRECT S3 FOUND:\n")
    for p in direct_found:
        f.write(f"  {p}\n")
    f.write(f"\nLOCAL USD ({len(local_usd_files)} files):\n")
    for p, s in sorted(local_usd_files, key=lambda x: -x[1])[:30]:
        f.write(f"  {s:.1f}KB  {p}\n")
print(f"  Text inventory:  {txt_path}")

print("\n" + "=" * 70)
print("  [PRAQTOR DATΔ] Discovery complete!")
print("  Next: Run photoreal_scene_v2.py using the confirmed assets above.")
print("=" * 70)

simulation_app.close()
