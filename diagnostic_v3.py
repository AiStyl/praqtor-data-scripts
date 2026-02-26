"""
PRAQTOR DATΔ — V3 Diagnostic Script
=====================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090

PURPOSE: Run BEFORE photoreal_scene_v3.py to discover:
  1. Character joint hierarchies (exact names for T-pose fix)
  2. Available .skelanim files on S3 (for animation binding)
  3. Confirm all assets loadable
  4. Check if anim graph extensions are available

Run:    /isaac-sim/python.sh /workspace/praqtor-data-scripts/diagnostic_v3.py
Cost:   ~$0.05 (runs in ~3 minutes)
Output: /workspace/diagnostic_report.json
"""

import os
import sys
import time
import json
from datetime import datetime

OUTPUT_PATH = "/workspace/diagnostic_report.json"

report = {
    "script": "diagnostic_v3.py",
    "version": "3.0",
    "started_at": datetime.utcnow().isoformat() + "Z",
    "characters": {},
    "skelanim_files": [],
    "extensions": {},
    "assets": {},
    "errors": [],
}

print("=" * 70)
print("  PRAQTOR DATΔ — V3 Diagnostic Report")
print("=" * 70)

# ============================================================
# PHASE 0: Launch Isaac Sim (minimal)
# ============================================================
from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": 640,
    "height": 480,
})
print("[DIAG] SimulationApp launched.")

for _ in range(10):
    simulation_app.update()

import omni.usd
import omni.kit.app
from pxr import Sdf, Usd, UsdSkel, UsdGeom

# ============================================================
# PHASE 1: Check animation graph extensions
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 1: EXTENSION AVAILABILITY")
print("=" * 70)

ext_manager = omni.kit.app.get_app().get_extension_manager()

extensions_to_check = [
    "omni.anim.graph.core",
    "omni.anim.graph.schema",
    "omni.anim.people",
    "omni.anim.navigation.schema",
    "omni.anim.retarget.core",
]

for ext_name in extensions_to_check:
    try:
        # Check if extension is available (not necessarily enabled)
        enabled = ext_manager.is_extension_enabled(ext_name)
        report["extensions"][ext_name] = {
            "enabled": enabled,
            "status": "ENABLED" if enabled else "DISABLED",
        }
        print(f"  {ext_name}: {'ENABLED' if enabled else 'DISABLED'}")
    except Exception as e:
        report["extensions"][ext_name] = {
            "enabled": False,
            "status": f"ERROR: {e}",
        }
        print(f"  {ext_name}: ERROR ({e})")

# Try enabling anim graph extensions
print("\n  Attempting to enable omni.anim.graph.core...")
try:
    ext_manager.set_extension_enabled_immediate("omni.anim.graph.core", True)
    for _ in range(20):
        simulation_app.update()
    enabled_after = ext_manager.is_extension_enabled("omni.anim.graph.core")
    report["extensions"]["omni.anim.graph.core"]["enable_attempt"] = enabled_after
    print(f"  Result: {'SUCCESS' if enabled_after else 'FAILED'}")
except Exception as e:
    report["extensions"]["omni.anim.graph.core"]["enable_attempt"] = False
    report["extensions"]["omni.anim.graph.core"]["enable_error"] = str(e)
    print(f"  Result: FAILED ({e})")

# ============================================================
# PHASE 2: Resolve assets root
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 2: ASSET ROOT")
print("=" * 70)

assets_root = None
try:
    from omni.isaac.nucleus import get_assets_root_path
    assets_root = get_assets_root_path()
    print(f"  Assets root: {assets_root}")
    report["assets"]["root"] = assets_root
except Exception as e:
    print(f"  get_assets_root_path() failed: {e}")
    assets_root = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
    print(f"  Using fallback: {assets_root}")
    report["assets"]["root"] = assets_root
    report["assets"]["root_method"] = "fallback"

# ============================================================
# PHASE 3: Load character and inspect skeleton
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 3: CHARACTER SKELETON INSPECTION")
print("=" * 70)

CHARACTER_PATHS = {
    "construction_03": "/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd",
    "police_01": "/Isaac/People/Characters/original_female_adult_police_01/female_adult_police_01.usd",
    "police_04": "/Isaac/People/Characters/original_male_adult_police_04/male_adult_police_04.usd",
    "medical_01": "/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd",
}

for char_name, char_path in CHARACTER_PATHS.items():
    full_url = assets_root + char_path
    print(f"\n  --- {char_name} ---")
    print(f"  URL: {full_url[:80]}...")

    char_report = {
        "url": full_url,
        "loadable": False,
        "skel_roots": [],
        "skeletons": [],
        "joint_names": [],
        "shoulder_joints": [],
        "existing_animations": [],
        "prim_types": {},
    }

    try:
        # Load as a layer to inspect structure
        layer = Sdf.Layer.FindOrOpen(full_url)
        simulation_app.update()

        if layer is None:
            print(f"  FAILED to load")
            char_report["error"] = "Layer.FindOrOpen returned None"
            report["characters"][char_name] = char_report
            continue

        char_report["loadable"] = True
        print(f"  Loaded successfully")

        # Open as a stage to traverse
        stage = Usd.Stage.Open(full_url)
        simulation_app.update()

        if stage is None:
            print(f"  Stage.Open failed")
            char_report["error"] = "Stage.Open returned None"
            report["characters"][char_name] = char_report
            continue

        # Count prim types
        prim_type_counts = {}
        for prim in stage.TraverseAll():
            ptype = prim.GetTypeName()
            if ptype:
                prim_type_counts[ptype] = prim_type_counts.get(ptype, 0) + 1

        char_report["prim_types"] = prim_type_counts
        print(f"  Prim types: {prim_type_counts}")

        # Find SkelRoot prims
        for prim in stage.TraverseAll():
            if prim.GetTypeName() == "SkelRoot":
                skel_root_path = str(prim.GetPath())
                char_report["skel_roots"].append(skel_root_path)
                print(f"  SkelRoot: {skel_root_path}")

                # Check for existing animation bindings
                binding = UsdSkel.BindingAPI(prim)
                anim_source = binding.GetAnimationSourceRel()
                if anim_source and anim_source.GetTargets():
                    targets = [str(t) for t in anim_source.GetTargets()]
                    char_report["existing_animations"].extend(targets)
                    print(f"    Existing anim source: {targets}")
                else:
                    print(f"    No existing animation binding")

            elif prim.GetTypeName() == "Skeleton":
                skel_path = str(prim.GetPath())
                char_report["skeletons"].append(skel_path)
                print(f"  Skeleton: {skel_path}")

                # Get joint names — THIS IS THE KEY DATA
                skeleton = UsdSkel.Skeleton(prim)
                joints_attr = skeleton.GetJointsAttr()
                if joints_attr:
                    joint_names = list(joints_attr.Get() or [])
                    char_report["joint_names"] = joint_names
                    print(f"    Total joints: {len(joint_names)}")

                    # Find shoulder/arm joints specifically
                    arm_keywords = [
                        "shoulder", "arm", "upperarm", "clavicle",
                        "Shoulder", "Arm", "UpperArm", "Clavicle",
                        "LeftArm", "RightArm", "L_Arm", "R_Arm",
                    ]
                    for jname in joint_names:
                        short = jname.split("/")[-1]
                        if any(kw.lower() in short.lower() for kw in arm_keywords):
                            char_report["shoulder_joints"].append(jname)
                            print(f"    >>> ARM JOINT: {jname}")

                    # Print first 20 joints for context
                    print(f"    First 20 joints:")
                    for j in joint_names[:20]:
                        print(f"      {j}")
                    if len(joint_names) > 20:
                        print(f"      ... ({len(joint_names) - 20} more)")

            elif prim.GetTypeName() == "SkelAnimation":
                anim_path = str(prim.GetPath())
                char_report["existing_animations"].append(anim_path)
                print(f"  SkelAnimation found: {anim_path}")

        stage = None  # Release

    except Exception as e:
        char_report["error"] = str(e)
        print(f"  ERROR: {e}")

    report["characters"][char_name] = char_report
    simulation_app.update()

# ============================================================
# PHASE 4: Search for .skelanim files on S3
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 4: SKELANIM FILE DISCOVERY")
print("=" * 70)

# Known potential animation paths from LLM research
ANIM_SEARCH_PATHS = [
    "/Isaac/People/Animations/idle.skelanim",
    "/Isaac/People/Animations/idle.skelanim.usd",
    "/Isaac/People/Animations/walk_loop.skelanim",
    "/Isaac/People/Animations/walk_loop.skelanim.usd",
    "/Isaac/People/Animations/stand_idle_loop.skelanim.usd",
    "/Isaac/People/Animations/standing_idle.skelanim",
    "/Isaac/People/Animations/type_keyboard.skelanim.usd",
    "/Isaac/People/Characters/Animations/idle.skelanim",
    "/Isaac/People/Characters/Animations/walk_loop.skelanim",
    # biped_setup animations (confirmed working for some users)
    "/Isaac/People/Characters/biped_setup/biped_setup.usd",
]

print("  Probing known animation paths...")
for anim_path in ANIM_SEARCH_PATHS:
    url = assets_root + anim_path
    try:
        layer = Sdf.Layer.FindOrOpen(url)
        simulation_app.update()
        if layer is not None:
            report["skelanim_files"].append({"path": anim_path, "url": url, "found": True})
            print(f"  ✓ FOUND: {anim_path}")
        else:
            print(f"  ✗ Not found: {anim_path}")
    except Exception as e:
        print(f"  ✗ Error probing {anim_path}: {e}")

# Try omni.client.list to discover directories
print("\n  Attempting omni.client.list on /Isaac/People/...")
try:
    import omni.client
    people_url = assets_root + "/Isaac/People/"
    result, entries = omni.client.list(people_url)
    if result == omni.client.Result.OK:
        print(f"  Found {len(entries)} entries in /Isaac/People/:")
        for entry in entries:
            name = entry.relative_path
            print(f"    {name}")
            report["skelanim_files"].append({"path": f"/Isaac/People/{name}", "type": "directory_entry"})

            # If it's an Animations directory, list contents
            if "anim" in name.lower():
                anim_url = people_url + name
                result2, entries2 = omni.client.list(anim_url)
                if result2 == omni.client.Result.OK:
                    for e2 in entries2:
                        anim_name = e2.relative_path
                        print(f"      {anim_name}")
                        report["skelanim_files"].append({
                            "path": f"/Isaac/People/{name}{anim_name}",
                            "type": "animation_file"
                        })
    else:
        print(f"  omni.client.list failed: {result}")
        report["errors"].append(f"omni.client.list failed: {result}")
except Exception as e:
    print(f"  omni.client not available: {e}")
    report["errors"].append(f"omni.client error: {e}")

# ============================================================
# PHASE 5: Quick asset verification
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 5: ENVIRONMENT + PROP VERIFICATION")
print("=" * 70)

ENVIRONMENTS = {
    "full_warehouse": "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
    "warehouse_shelves": "/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
    "warehouse_forklifts": "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
}

for env_name, env_path in ENVIRONMENTS.items():
    url = assets_root + env_path
    try:
        layer = Sdf.Layer.FindOrOpen(url)
        simulation_app.update()
        found = layer is not None
        report["assets"][env_name] = {"url": url, "found": found}
        print(f"  {'✓' if found else '✗'} {env_name}: {'OK' if found else 'NOT FOUND'}")
    except Exception as e:
        report["assets"][env_name] = {"url": url, "found": False, "error": str(e)}
        print(f"  ✗ {env_name}: ERROR ({e})")

# ============================================================
# SAVE REPORT
# ============================================================
report["completed_at"] = datetime.utcnow().isoformat() + "Z"

with open(OUTPUT_PATH, "w") as f:
    json.dump(report, f, indent=2)

print("\n" + "=" * 70)
print(f"  DIAGNOSTIC REPORT SAVED: {OUTPUT_PATH}")
print("=" * 70)

# Print summary for quick reading
print("\n  === SUMMARY ===")
for char_name, char_data in report["characters"].items():
    n_joints = len(char_data.get("joint_names", []))
    n_shoulder = len(char_data.get("shoulder_joints", []))
    has_anim = len(char_data.get("existing_animations", [])) > 0
    loadable = char_data.get("loadable", False)
    print(f"  {char_name}: loadable={loadable}, joints={n_joints}, shoulder_joints={n_shoulder}, has_anim={has_anim}")

n_skelanim = len([s for s in report["skelanim_files"] if s.get("found")])
print(f"  Skelanim files found: {n_skelanim}")

ext_graph = report["extensions"].get("omni.anim.graph.core", {})
print(f"  omni.anim.graph.core: enabled={ext_graph.get('enabled')}, enable_attempt={ext_graph.get('enable_attempt')}")

print(f"\n  Errors: {len(report['errors'])}")
for err in report["errors"]:
    print(f"    - {err}")

print("\n  NEXT: Read diagnostic_report.json, then run photoreal_scene_v3.py")
print("=" * 70)

simulation_app.close()
