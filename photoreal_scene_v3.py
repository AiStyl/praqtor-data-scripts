"""
PRAQTOR DATΔ — Photorealistic Scene SDG v3
=============================================
Isaac Sim 4.2.0 | Headless | RunPod RTX 4090

IMPROVEMENTS OVER v2:
  1. T-pose fix: attempts skeleton animation binding, falls back to joint rotation
  2. Clipping fix: people placed at proper Z height above ground objects
  3. Multiple warehouse layouts: rotates between 3 environments
  4. 50 frames instead of 10
  5. All 4 human character models loaded
  6. Better lighting: dome + distant + fill light
  7. max_execs instead of deprecated num_frames
  8. Job manifest with full provenance tracking
  9. Semantic segmentation enabled

Run:    /isaac-sim/python.sh /workspace/praqtor-data-scripts/photoreal_scene_v3.py
Cost:   ~$0.50-0.75 (runs in ~10-15 min)
Output: /workspace/output_v3/

PREREQUISITES:
  - Run discover_assets_v2.py FIRST (or have asset_inventory.json from previous run)
"""

import os
import sys
import time
import json
import random
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
OUTPUT_DIR = "/workspace/output_v3"
FRAMES_PER_ENVIRONMENT = 17  # 17 * 3 environments = 51 frames total
RESOLUTION = (1280, 720)
PERSON_Z_OFFSET = 0.15  # Height above ground to prevent clipping (pallet height ~0.15m)

# ============================================================
# JOB MANIFEST
# ============================================================
JOB_MANIFEST = {
    "script": "photoreal_scene_v3.py",
    "version": "3.0",
    "started_at": datetime.utcnow().isoformat() + "Z",
    "config": {
        "frames_per_env": FRAMES_PER_ENVIRONMENT,
        "resolution": list(RESOLUTION),
        "person_z_offset": PERSON_Z_OFFSET,
    },
    "environments_used": [],
    "assets_used": {},
    "errors": [],
    "tpose_fix_status": "not_attempted",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("  PRAQTOR DATΔ — Photorealistic Scene Generator v3")
print("  Multi-environment | Multi-character | 50+ frames")
print("=" * 70)

# ============================================================
# PHASE 0: Launch Isaac Sim
# ============================================================
from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": RESOLUTION[0],
    "height": RESOLUTION[1],
})

print("[PRAQTOR DATΔ] SimulationApp launched.")
print("[PRAQTOR DATΔ] Warming up renderer (10 frames)...")
for _ in range(10):
    simulation_app.update()

import omni.usd
import omni.replicator.core as rep
from pxr import Sdf, Usd, UsdGeom, UsdSkel, Gf

# ============================================================
# PHASE 1: RESOLVE ASSETS
# ============================================================
print("\n" + "=" * 70)
print("  PHASE 1: ASSET RESOLUTION")
print("=" * 70)


def get_asset_root():
    """Get asset root from inventory file or live Nucleus."""
    inventory_path = "/workspace/asset_inventory.json"
    if os.path.exists(inventory_path):
        with open(inventory_path) as f:
            inv = json.load(f)
        root = inv.get("assets_root", "")
        if root and root != "None":
            print(f"  Asset root (from inventory): {root}")
            return root

    try:
        from omni.isaac.nucleus import get_assets_root_path
        root = get_assets_root_path()
        if root:
            print(f"  Asset root (live Nucleus): {root}")
            return root
    except Exception:
        pass

    # Direct S3 fallback
    root = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
    print(f"  Asset root (direct S3 fallback): {root}")
    return root


assets_root = get_asset_root()

# Define all environments we'll rotate through
ENVIRONMENTS = [
    "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
    "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
    "/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
]

# All character models
CHARACTER_MODELS = [
    "/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd",
    "/Isaac/People/Characters/original_female_adult_police_01/female_adult_police_01.usd",
    "/Isaac/People/Characters/original_male_adult_police_04/male_adult_police_04.usd",
    "/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd",
]

# Props
FORKLIFT_PATH = "/Isaac/Props/Forklift/forklift.usd"
PROP_PATHS = {
    "cone": ("/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd", "obstacle"),
    "pallet": ("/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd", "pallet"),
    "box_d": ("/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd", "cargo"),
    "box_a": ("/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxA_01.usd", "cargo"),
    "box_b": ("/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxB_01.usd", "cargo"),
    "shelf": ("/Isaac/Environments/Simple_Warehouse/Props/SM_RackShelf_01.usd", "shelf"),
}

JOB_MANIFEST["assets_used"] = {
    "environments": ENVIRONMENTS,
    "characters": CHARACTER_MODELS,
    "forklift": FORKLIFT_PATH,
    "props": {k: v[0] for k, v in PROP_PATHS.items()},
}


# ============================================================
# T-POSE FIX HELPER FUNCTIONS
# ============================================================
def attempt_tpose_fix_via_joint_rotation(stage):
    """
    Attempt to fix T-pose by finding skeleton prims and rotating
    the shoulder joints downward. This is the fallback approach
    if animation binding doesn't work.

    Strategy: Find all SkelRoot prims, traverse to find shoulder
    joints, and rotate them ~75 degrees downward.
    """
    print("  [T-POSE FIX] Attempting joint rotation approach...")
    fixed_count = 0

    try:
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skel = UsdSkel.Skeleton(prim)
                # Get the rest transforms
                joints_attr = skel.GetJointsAttr()
                if not joints_attr:
                    continue

                joints = joints_attr.Get()
                if not joints:
                    continue

                # Look for shoulder joints
                rest_transforms = skel.GetRestTransformsAttr().Get()
                bind_transforms = skel.GetBindTransformsAttr().Get()

                if rest_transforms:
                    new_transforms = list(rest_transforms)
                    for i, joint_name in enumerate(joints):
                        joint_lower = str(joint_name).lower()
                        # Rotate shoulders downward from T-pose
                        if "shoulder" in joint_lower or "upperarm" in joint_lower or "l_arm" in joint_lower or "r_arm" in joint_lower:
                            # Apply ~75 degree rotation on the forward axis to bring arms down
                            xform = new_transforms[i]
                            # Create rotation to bring arm down
                            if "left" in joint_lower or "_l_" in joint_lower or "l_arm" in joint_lower:
                                rot = Gf.Rotation(Gf.Vec3d(0, 0, 1), 75)  # Left arm down
                            else:
                                rot = Gf.Rotation(Gf.Vec3d(0, 0, 1), -75)  # Right arm down

                            current_matrix = Gf.Matrix4d(xform)
                            rot_matrix = Gf.Matrix4d()
                            rot_matrix.SetRotate(rot)
                            new_matrix = rot_matrix * current_matrix
                            new_transforms[i] = Gf.Matrix4d(new_matrix)
                            fixed_count += 1

                    if fixed_count > 0:
                        skel.GetRestTransformsAttr().Set(new_transforms)

        if fixed_count > 0:
            print(f"  [T-POSE FIX] Rotated {fixed_count} shoulder joints")
            return True
        else:
            print("  [T-POSE FIX] No shoulder joints found to rotate")
            return False

    except Exception as e:
        print(f"  [T-POSE FIX] Joint rotation failed: {e}")
        return False


def attempt_tpose_fix_via_animation(stage, assets_root):
    """
    Attempt to fix T-pose by binding a skeletal animation clip.
    This is the preferred approach but may not work in all headless configs.
    """
    print("  [T-POSE FIX] Attempting animation binding approach...")

    # Try to find animation clips on the S3 server
    possible_anim_paths = [
        "/Isaac/People/Characters/Animations/idle.skelanim",
        "/Isaac/People/Characters/Animations/standing_idle.skelanim",
        "/Isaac/People/Characters/Animations/walk_loop.skelanim",
        "/Isaac/People/Characters/Biped_Setup/Animations/idle.skelanim",
        "/Isaac/Samples/PeopleDemo/Animations/idle.skelanim",
    ]

    anim_url = None
    for path in possible_anim_paths:
        url = assets_root + path
        try:
            layer = Sdf.Layer.FindOrOpen(url)
            if layer is not None:
                anim_url = url
                print(f"  [T-POSE FIX] Found animation clip: {path}")
                break
        except Exception:
            pass
        simulation_app.update()

    if not anim_url:
        print("  [T-POSE FIX] No animation clips found on S3")
        return False

    try:
        # Find all skeleton prims and try to bind the animation
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skel_path = prim.GetPath()

                # Create animation prim as child
                anim_path = skel_path.AppendChild("BoundAnimation")
                anim_prim = stage.DefinePrim(anim_path, "SkelAnimation")
                anim_prim.GetReferences().AddReference(anim_url)

                # Bind animation to skeleton
                binding_api = UsdSkel.BindingAPI.Apply(prim)
                binding_api.CreateAnimationSourceRel().SetTargets([anim_path])

                simulation_app.update()
                print(f"  [T-POSE FIX] Bound animation to {skel_path}")

        return True

    except Exception as e:
        print(f"  [T-POSE FIX] Animation binding failed: {e}")
        return False


# ============================================================
# PHASE 2: RENDER LOOP (per environment)
# ============================================================

frame_offset = 0
total_rgb = 0
total_bbox = 0
total_seg = 0

for env_idx, env_path in enumerate(ENVIRONMENTS):
    env_url = assets_root + env_path
    env_output_dir = os.path.join(OUTPUT_DIR, f"env_{env_idx}")
    os.makedirs(env_output_dir, exist_ok=True)

    print(f"\n{'=' * 70}")
    print(f"  ENVIRONMENT {env_idx + 1}/{len(ENVIRONMENTS)}: {env_path.split('/')[-1]}")
    print(f"{'=' * 70}")

    # --- Load environment ---
    print(f"  Loading environment from S3...")
    try:
        from omni.isaac.core.utils.stage import open_stage
        result = open_stage(env_url)
        if not result:
            print(f"  [WARNING] open_stage returned False")
            JOB_MANIFEST["errors"].append(f"open_stage False for env {env_idx}")
    except Exception as e:
        print(f"  [ERROR] Failed to load environment: {e}")
        JOB_MANIFEST["errors"].append(f"env {env_idx} load failed: {e}")
        continue

    # Wait for streaming
    print("  Waiting for S3 streaming...")
    for i in range(50):
        simulation_app.update()
        if i % 10 == 0:
            print(f"    Loading... {i}/50")
        time.sleep(0.3)

    print("  [OK] Environment loaded.")
    JOB_MANIFEST["environments_used"].append(env_path)

    # --- Attempt T-pose fix (only on first environment) ---
    if env_idx == 0:
        stage = omni.usd.get_context().get_stage()
        # Try animation binding first, then joint rotation as fallback
        anim_success = attempt_tpose_fix_via_animation(stage, assets_root)
        if anim_success:
            JOB_MANIFEST["tpose_fix_status"] = "animation_binding"
        else:
            joint_success = attempt_tpose_fix_via_joint_rotation(stage)
            if joint_success:
                JOB_MANIFEST["tpose_fix_status"] = "joint_rotation"
            else:
                JOB_MANIFEST["tpose_fix_status"] = "failed_using_tpose"
                print("  [T-POSE FIX] Both approaches failed. Characters will be in T-pose.")

    # --- Build Replicator scene ---
    print("  Building Replicator scene...")

    with rep.new_layer():

        # --- LIGHTING (improved: dome + sun + fill) ---
        dome = rep.create.light(
            light_type="Dome",
            intensity=1500,
            color=(0.9, 0.92, 1.0),
        )
        sun = rep.create.light(
            light_type="Distant",
            intensity=4000,
            color=(1.0, 0.97, 0.90),
            rotation=(60, 30, 0),
        )
        # Fill light to reduce dark shadows on foreground objects
        fill = rep.create.light(
            light_type="Distant",
            intensity=1500,
            color=(0.85, 0.88, 1.0),
            rotation=(-30, -60, 0),
        )

        # --- FORKLIFTS ---
        print("  Spawning forklifts (3)...")
        vehicles = rep.create.from_usd(
            assets_root + FORKLIFT_PATH,
            semantics=[("class", "forklift")],
            count=3,
        )

        # --- PEOPLE (multiple character models) ---
        # Pick 2 different characters for this environment
        char_indices = [(env_idx * 2) % len(CHARACTER_MODELS),
                        (env_idx * 2 + 1) % len(CHARACTER_MODELS)]
        people_prims = []

        for ci in char_indices:
            char_path = CHARACTER_MODELS[ci]
            char_name = char_path.split("/")[-1].replace(".usd", "")
            print(f"  Spawning person: {char_name}...")
            try:
                person = rep.create.from_usd(
                    assets_root + char_path,
                    semantics=[("class", "person")],
                    count=1,
                )
                people_prims.append(person)
            except Exception as e:
                print(f"    Failed to load {char_name}: {e}")
                JOB_MANIFEST["errors"].append(f"Character load failed: {char_name}: {e}")

        # If no real people loaded, use capsule fallback
        if not people_prims:
            print("  Using capsule fallback for people...")
            capsule_people = rep.create.capsule(
                count=3,
                scale=(0.35, 0.35, 1.7),
                semantics=[("class", "person")],
            )
            people_prims.append(capsule_people)

        # --- PROPS ---
        loaded_props = []
        for prop_name, (prop_path, semantic_class) in PROP_PATHS.items():
            try:
                count = 4 if prop_name == "cone" else 3 if "box" in prop_name else 2
                prop = rep.create.from_usd(
                    assets_root + prop_path,
                    semantics=[("class", semantic_class)],
                    count=count,
                )
                loaded_props.append(prop)
            except Exception as e:
                JOB_MANIFEST["errors"].append(f"Prop {prop_name} failed: {e}")

        # --- CAMERA ---
        print("  Setting up camera...")
        cam = rep.create.camera(
            position=(5, -8, 3),
            look_at=(0, 5, 1),
            focal_length=28.0,
        )
        rp = rep.create.render_product(cam, RESOLUTION)

        # --- WRITER ---
        print(f"  Configuring writer → {env_output_dir}")
        writer = rep.WriterRegistry.get("BasicWriter")
        writer.initialize(
            output_dir=env_output_dir,
            rgb=True,
            bounding_box_2d_tight=True,
            semantic_segmentation=True,
        )
        writer.attach([rp])

        # --- RANDOMIZATION ---
        print(f"  Setting up randomization ({FRAMES_PER_ENVIRONMENT} frames)...")
        with rep.trigger.on_frame(max_execs=FRAMES_PER_ENVIRONMENT):
            # Forklifts: random position and rotation within warehouse
            with vehicles:
                rep.modify.pose(
                    position=rep.distribution.uniform((-8, -8, 0), (8, 8, 0)),
                    rotation=(0, 0, rep.distribution.uniform(-180, 180)),
                )

            # People: random position WITH Z offset to prevent clipping
            for person_prim in people_prims:
                with person_prim:
                    rep.modify.pose(
                        position=rep.distribution.uniform(
                            (-10, -10, PERSON_Z_OFFSET),
                            (10, 10, PERSON_Z_OFFSET)
                        ),
                        rotation=(0, 0, rep.distribution.uniform(-180, 180)),
                    )

            # Camera: varied viewpoints
            with cam:
                rep.modify.pose(
                    position=rep.distribution.uniform((2, -15, 2), (10, -3, 6)),
                    look_at=rep.distribution.uniform((-3, 0, 0), (3, 8, 2)),
                )

    # --- WARM UP + RENDER ---
    print(f"  Warm-up (25 frames)...")
    for i in range(25):
        simulation_app.update()
        if i % 5 == 0:
            print(f"    Warm-up frame {i}/25")

    print(f"  Capturing {FRAMES_PER_ENVIRONMENT} frames...")
    rep.orchestrator.run_until_complete()
    print(f"  [OK] Environment {env_idx + 1} capture complete.")

    # Count outputs for this environment
    for f in os.listdir(env_output_dir):
        if f.startswith("rgb") and f.endswith(".png"):
            total_rgb += 1
        elif "bounding_box" in f:
            total_bbox += 1
        elif "semantic" in f and f.endswith(".png"):
            total_seg += 1

    frame_offset += FRAMES_PER_ENVIRONMENT

# ============================================================
# PHASE 3: OUTPUT VERIFICATION
# ============================================================
print(f"\n{'=' * 70}")
print("  PHASE 3: OUTPUT VERIFICATION")
print(f"{'=' * 70}")

# Check all outputs across environments
total_files = 0
total_size = 0
all_output_files = []

for env_idx in range(len(ENVIRONMENTS)):
    env_dir = os.path.join(OUTPUT_DIR, f"env_{env_idx}")
    if not os.path.isdir(env_dir):
        continue
    for f in os.listdir(env_dir):
        fpath = os.path.join(env_dir, f)
        fsize = os.path.getsize(fpath)
        all_output_files.append({"file": fpath, "size_bytes": fsize})
        total_files += 1
        total_size += fsize

print(f"  Total files:        {total_files}")
print(f"  Total size:         {total_size / (1024*1024):.1f} MB")
print(f"  RGB images:         {total_rgb}")
print(f"  Bounding boxes:     {total_bbox}")
print(f"  Segmentation masks: {total_seg}")
print(f"  Environments used:  {len(JOB_MANIFEST['environments_used'])}")
print(f"  T-pose fix:         {JOB_MANIFEST['tpose_fix_status']}")

# Quality check
rgb_sizes = [f["size_bytes"] for f in all_output_files
             if "rgb" in f["file"] and f["file"].endswith(".png")]
if rgb_sizes:
    avg_rgb = sum(rgb_sizes) / len(rgb_sizes)
    print(f"  Avg RGB size:       {avg_rgb / 1024:.1f} KB")
    if avg_rgb > 300 * 1024:
        print("  ✓ PHOTOREALISTIC quality confirmed (>300KB avg)")
        JOB_MANIFEST["quality_check"] = "PASS_PHOTOREALISTIC"
    elif avg_rgb > 100 * 1024:
        print("  ⚠ Moderate quality (100-300KB avg)")
        JOB_MANIFEST["quality_check"] = "MODERATE"
    else:
        print("  ✗ Primitive quality (<100KB avg) — assets may not have loaded")
        JOB_MANIFEST["quality_check"] = "FAIL_PRIMITIVE"

# Save manifest
JOB_MANIFEST["completed_at"] = datetime.utcnow().isoformat() + "Z"
JOB_MANIFEST["status"] = "COMPLETED"
JOB_MANIFEST["summary"] = {
    "total_files": total_files,
    "total_size_mb": round(total_size / (1024 * 1024), 1),
    "rgb_count": total_rgb,
    "bbox_count": total_bbox,
    "seg_count": total_seg,
    "avg_rgb_size_kb": round(avg_rgb / 1024, 1) if rgb_sizes else 0,
    "environments_rendered": len(JOB_MANIFEST["environments_used"]),
    "errors_count": len(JOB_MANIFEST["errors"]),
}

manifest_path = os.path.join(OUTPUT_DIR, "job_manifest.json")
with open(manifest_path, "w") as f:
    json.dump(JOB_MANIFEST, f, indent=2)
print(f"\n  Job manifest: {manifest_path}")

if JOB_MANIFEST["errors"]:
    print(f"\n  Errors ({len(JOB_MANIFEST['errors'])}):")
    for err in JOB_MANIFEST["errors"]:
        print(f"    - {err}")

print(f"\n{'=' * 70}")
print("  [PRAQTOR DATΔ] v3 Scene generation complete!")
print(f"  Output: {OUTPUT_DIR}")
print(f"  Total: {total_rgb} RGB + {total_bbox} bbox + {total_seg} seg across {len(JOB_MANIFEST['environments_used'])} environments")
print("  Next: Push to GitHub, pull to PC, evaluate quality.")
print(f"{'=' * 70}")

simulation_app.close()
