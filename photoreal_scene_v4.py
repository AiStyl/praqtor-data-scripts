"""
PRAQTOR DATΔ — Photoreal Scene v4
T-pose fix + Character Grounding + Camera Variety

Key changes from v2/v3:
1. T-POSE FIX: Enables omni.anim.graph.core extension for headless mode,
   then binds SkelAnimation clips directly to character skeletons via UsdSkelBindingAPI.
   Falls back to timeline advance if binding fails.
2. CHARACTER GROUNDING: Places characters at Y=0 (floor level) with small random offset,
   not on top of props.
3. CAMERA VARIETY: 8 camera presets covering wide, close-up, overhead, aisle, and corner angles.
4. MULTI-CHARACTER: Spawns 2-3 characters per scene with different animations.

Requires: Isaac Sim 4.2 container on RunPod RTX 4090
Asset base: http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2
"""

import os
import sys
import json
import random
import time

print("[PRAQTOR DATΔ v4] Starting photoreal scene with T-pose fix...")
print(f"[PRAQTOR DATΔ v4] Python: {sys.version}")
print(f"[PRAQTOR DATΔ v4] CWD: {os.getcwd()}")

# ============================================================
# PHASE 0: Enable animation extensions for headless mode
# This is the KEY fix for T-pose — omni.anim.graph.core must
# be loaded before characters are spawned
# ============================================================
print("[PRAQTOR DATΔ v4] Phase 0: Enabling animation extensions...")

try:
    import omni.kit.app
    app = omni.kit.app.get_app()
    ext_manager = app.get_extension_manager()
    
    ANIM_EXTENSIONS = [
        "omni.anim.graph.core",
        "omni.anim.graph.schema",
        "omni.anim.navigation.schema",
        "omni.anim.skelJoint",
        "omni.anim.retarget.core",
    ]
    
    for ext_name in ANIM_EXTENSIONS:
        try:
            result = ext_manager.set_extension_enabled_immediate(ext_name, True)
            print(f"  [OK] Enabled {ext_name}: {result}")
        except Exception as e:
            print(f"  [WARN] Could not enable {ext_name}: {e}")
    
    # Give extensions time to initialize
    for _ in range(10):
        app.update()
    print("[PRAQTOR DATΔ v4] Animation extensions loaded.")
except Exception as e:
    print(f"[PRAQTOR DATΔ v4] Extension loading failed (non-fatal): {e}")

# ============================================================
# PHASE 1: Import core modules
# ============================================================
print("[PRAQTOR DATΔ v4] Phase 1: Importing modules...")

import omni.replicator.core as rep
from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf

print("[PRAQTOR DATΔ v4] Modules imported successfully.")

# ============================================================
# CONFIGURATION
# ============================================================

S3_BASE = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"

# Warehouse environments (confirmed working from discovery)
WAREHOUSES = [
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/warehouse.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
]

# Characters (confirmed from discovery)
CHARACTERS = [
    f"{S3_BASE}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd",
    f"{S3_BASE}/Isaac/People/Characters/male_adult_construction_05/male_adult_construction_05.usd",
    f"{S3_BASE}/Isaac/People/Characters/male_adult_police_04/male_adult_police_04.usd",
    f"{S3_BASE}/Isaac/People/Characters/female_adult_police_01/female_adult_police_01.usd",
]

# Animation clips (confirmed from discovery — 24+ available)
ANIMATIONS = {
    "walking": [
        f"{S3_BASE}/Isaac/People/Characters/Animations/walking_01.skelanim.usd",
        f"{S3_BASE}/Isaac/People/Characters/Animations/walking_02.skelanim.usd",
    ],
    "idle": [
        f"{S3_BASE}/Isaac/People/Characters/Animations/idle_01.skelanim.usd",
        f"{S3_BASE}/Isaac/People/Characters/Animations/idle_02.skelanim.usd",
    ],
    "waving": [
        f"{S3_BASE}/Isaac/People/Characters/Animations/waving_01.skelanim.usd",
    ],
    "sitting": [
        f"{S3_BASE}/Isaac/People/Characters/Animations/sitting_01.skelanim.usd",
    ],
}

# Flat list of all animations for random selection
ALL_ANIMATIONS = []
for anim_list in ANIMATIONS.values():
    ALL_ANIMATIONS.extend(anim_list)

# Props (confirmed from discovery)
PROPS = [
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxC_01.usd",
]

FORKLIFT = f"{S3_BASE}/Isaac/Props/Forklift/forklift.usd"

# Camera presets — 8 diverse angles for warehouse scenes
# Format: (position, look_at_target)
CAMERA_PRESETS = [
    # Wide establishing shots
    {"name": "wide_front",    "pos": (8, 3.5, 6),    "look": (0, 1.0, 0)},
    {"name": "wide_corner",   "pos": (-6, 4.0, 8),   "look": (2, 0.5, -2)},
    # Medium shots (worker-level)
    {"name": "medium_aisle",  "pos": (3, 1.8, 2),    "look": (-3, 1.0, -2)},
    {"name": "medium_side",   "pos": (-4, 2.0, 0),   "look": (2, 1.2, 0)},
    # Close-up / detail
    {"name": "close_worker",  "pos": (1.5, 1.6, 1.5),"look": (0, 1.2, 0)},
    {"name": "close_forklift","pos": (2, 1.2, -3),   "look": (0, 0.8, -4)},
    # Overhead / surveillance
    {"name": "overhead",      "pos": (0, 8, 0),      "look": (0, 0, 0)},
    {"name": "high_angle",    "pos": (5, 6, 5),      "look": (0, 0, 0)},
]

OUTPUT_DIR = "/workspace/output_v4"
FRAMES_PER_CAMERA = 3
TOTAL_ENVIRONMENTS = 2  # Use 2 warehouses per run

# ============================================================
# PHASE 2: Load environment
# ============================================================
print("[PRAQTOR DATΔ v4] Phase 2: Loading environment...")

selected_warehouses = random.sample(WAREHOUSES, min(TOTAL_ENVIRONMENTS, len(WAREHOUSES)))
manifest = {
    "version": "4.0",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "environments": [],
    "tpose_fix_method": "unknown",
    "character_grounding": True,
    "camera_presets": len(CAMERA_PRESETS),
}

# ============================================================
# HELPER: Find skeleton prim recursively
# ============================================================
def find_skeleton_prim(stage, root_path):
    """Traverse children of root_path to find UsdSkel.Skeleton prim."""
    root_prim = stage.GetPrimAtPath(root_path)
    if not root_prim.IsValid():
        return None
    
    for prim in Usd.PrimRange(root_prim):
        if prim.IsA(UsdSkel.Skeleton):
            return prim
    return None

def find_skelroot_prim(stage, root_path):
    """Traverse children of root_path to find UsdSkel.Root prim."""
    root_prim = stage.GetPrimAtPath(root_path)
    if not root_prim.IsValid():
        return None
    
    for prim in Usd.PrimRange(root_prim):
        if prim.IsA(UsdSkel.Root):
            return prim
    return None

# ============================================================
# HELPER: Apply animation to character
# ============================================================
def apply_animation_to_character(stage, person_path, anim_usd_path):
    """
    Bind a SkelAnimation clip to a character's skeleton.
    This is the T-pose fix — without animation, characters default to bind pose (T-pose).
    
    Approach:
    1. Create an Animation prim under the person as a USD reference
    2. Find the Skeleton prim in the character hierarchy
    3. Apply UsdSkelBindingAPI to the skeleton
    4. Set the animation source to our animation prim
    """
    person_prim = stage.GetPrimAtPath(person_path)
    if not person_prim.IsValid():
        print(f"  [WARN] Person prim not valid at {person_path}")
        return False
    
    try:
        # Step 1: Create animation reference prim
        anim_path = f"{person_path}/AppliedAnimation"
        anim_prim = stage.DefinePrim(anim_path, "SkelAnimation")
        if anim_prim.IsValid():
            anim_prim.GetReferences().AddReference(anim_usd_path)
            print(f"  [OK] Added animation reference: {anim_usd_path}")
        else:
            print(f"  [WARN] Could not create animation prim at {anim_path}")
            return False
        
        # Step 2: Find the skeleton
        skeleton_prim = find_skeleton_prim(stage, person_path)
        if skeleton_prim is None:
            # Try finding SkelRoot and looking deeper
            skelroot = find_skelroot_prim(stage, person_path)
            if skelroot:
                skeleton_prim = find_skeleton_prim(stage, str(skelroot.GetPath()))
            
        if skeleton_prim is None:
            print(f"  [WARN] No Skeleton prim found under {person_path}")
            # Try alternative: apply to SkelRoot directly
            skelroot = find_skelroot_prim(stage, person_path)
            if skelroot:
                print(f"  [INFO] Trying SkelRoot binding at {skelroot.GetPath()}")
                binding_api = UsdSkel.BindingAPI.Apply(skelroot.GetPrim() if hasattr(skelroot, 'GetPrim') else skelroot)
                binding_api.CreateAnimationSourceRel().SetTargets([Sdf.Path(anim_path)])
                print(f"  [OK] Animation bound to SkelRoot")
                return True
            return False
        
        # Step 3: Apply UsdSkelBindingAPI and set animation source
        print(f"  [INFO] Found skeleton at: {skeleton_prim.GetPath()}")
        binding_api = UsdSkel.BindingAPI.Apply(skeleton_prim)
        binding_api.CreateAnimationSourceRel().SetTargets([Sdf.Path(anim_path)])
        print(f"  [OK] Animation bound to skeleton successfully!")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Animation binding failed: {e}")
        return False

# ============================================================
# HELPER: Advance timeline to apply animation
# ============================================================
def advance_timeline(num_frames=30):
    """Advance the simulation timeline to let animations settle."""
    try:
        import omni.timeline
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        
        app = omni.kit.app.get_app()
        for i in range(num_frames):
            app.update()
        
        timeline.pause()
        print(f"  [OK] Advanced timeline {num_frames} frames")
        return True
    except Exception as e:
        print(f"  [WARN] Timeline advance failed: {e}")
        return False

# ============================================================
# PHASE 3: Build scenes and capture
# ============================================================
print("[PRAQTOR DATΔ v4] Phase 3: Building scenes...")

env_index = 0
tpose_fix_success = False

for warehouse_path in selected_warehouses:
    env_name = os.path.basename(warehouse_path).replace('.usd', '')
    env_output = os.path.join(OUTPUT_DIR, f"env_{env_index}")
    os.makedirs(env_output, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"[ENV {env_index}] {env_name}")
    print(f"{'='*60}")
    
    env_data = {
        "name": env_name,
        "warehouse": warehouse_path,
        "characters": [],
        "animation_status": [],
        "cameras_used": [],
    }
    
    # --- Open stage ---
    with rep.new_layer():
        # Load warehouse
        warehouse = rep.create.from_usd(warehouse_path, semantics=[("class", "warehouse")])
        print(f"  [OK] Loaded warehouse: {env_name}")
        
        # --- Spawn characters with GROUNDING FIX ---
        # Place characters on the floor (Y≈0) at spread-out X/Z positions
        CHARACTER_POSITIONS = [
            (0.0, 0.0, 0.0),     # Center of warehouse
            (3.0, 0.0, -2.0),    # Near shelves
            (-2.0, 0.0, 3.0),    # Other side
        ]
        
        num_characters = random.randint(2, 3)
        selected_chars = random.sample(CHARACTERS, min(num_characters, len(CHARACTERS)))
        
        people_prims = []
        for i, (char_path, pos) in enumerate(zip(selected_chars, CHARACTER_POSITIONS[:num_characters])):
            char_name = os.path.basename(os.path.dirname(char_path))
            
            # Create character with FLOOR-LEVEL positioning (Y=0, not on props)
            person = rep.create.from_usd(
                char_path,
                semantics=[("class", "person")],
                position=pos,
                count=1
            )
            people_prims.append(person)
            
            print(f"  [OK] Spawned {char_name} at floor position {pos}")
            env_data["characters"].append({
                "model": char_name,
                "position": list(pos),
                "grounded": True,
            })
        
        # --- Load forklift ---
        forklift = rep.create.from_usd(
            FORKLIFT,
            semantics=[("class", "forklift")],
            position=(4.0, 0.0, -3.0),
        )
        print(f"  [OK] Loaded forklift")
        
        # --- Scatter some props on the floor ---
        for j, prop_path in enumerate(random.sample(PROPS, min(3, len(PROPS)))):
            prop_positions = [(-3, 0, -1), (2, 0, 2), (-1, 0, -4)]
            rep.create.from_usd(
                prop_path,
                semantics=[("class", "prop")],
                position=prop_positions[j % len(prop_positions)],
            )
        print(f"  [OK] Scattered props")
        
        # --- ATTEMPT T-POSE FIX ---
        print(f"\n  [TPOSE FIX] Attempting animation binding...")
        
        # Get the USD stage to manipulate skeletons directly
        try:
            import omni.usd
            stage = omni.usd.get_context().get_stage()
            
            if stage:
                # Force a stage update so character hierarchies are loaded
                app = omni.kit.app.get_app()
                for _ in range(20):
                    app.update()
                
                # Try to find and animate each character
                # Characters spawned by replicator get paths like /Replicator/Ref_Xform_*
                # We need to search the stage for SkelRoot prims
                anim_bound_count = 0
                
                for prim in stage.Traverse():
                    if prim.IsA(UsdSkel.Root):
                        prim_path = str(prim.GetPath())
                        # Pick a random animation
                        anim_clip = random.choice(ALL_ANIMATIONS)
                        anim_type = "unknown"
                        for atype, clips in ANIMATIONS.items():
                            if anim_clip in clips:
                                anim_type = atype
                                break
                        
                        print(f"  [TPOSE FIX] Found SkelRoot: {prim_path}")
                        success = apply_animation_to_character(stage, prim_path, anim_clip)
                        
                        env_data["animation_status"].append({
                            "skelroot": prim_path,
                            "animation": os.path.basename(anim_clip),
                            "type": anim_type,
                            "bound": success,
                        })
                        
                        if success:
                            anim_bound_count += 1
                
                if anim_bound_count > 0:
                    tpose_fix_success = True
                    print(f"  [TPOSE FIX] Bound animations to {anim_bound_count} characters")
                    
                    # Advance timeline to let animations take effect
                    advance_timeline(60)
                else:
                    print(f"  [TPOSE FIX] No animations bound — trying timeline advance only")
                    advance_timeline(60)
            else:
                print(f"  [TPOSE FIX] Could not get USD stage")
                
        except Exception as e:
            print(f"  [TPOSE FIX] Error during animation binding: {e}")
            import traceback
            traceback.print_exc()
        
        # --- Setup lighting ---
        rep.create.light(
            light_type="Dome",
            intensity=1000,
            texture=f"{S3_BASE}/Isaac/Materials/Textures/Skies/Indoor/autoshop_01_4k.hdr"
        )
        rep.create.light(
            light_type="Rect",
            intensity=5000,
            position=(0, 5, 0),
            rotation=(-90, 0, 0),
            scale=(8, 8, 1),
        )
        print(f"  [OK] Lighting configured")
        
        # --- Setup cameras and capture ---
        # Select a subset of camera presets for variety
        num_cameras = min(4, len(CAMERA_PRESETS))
        selected_cameras = random.sample(CAMERA_PRESETS, num_cameras)
        
        for cam_idx, cam in enumerate(selected_cameras):
            camera = rep.create.camera(
                position=cam["pos"],
                look_at=cam["look"],
                focal_length=28.0,
            )
            rp = rep.create.render_product(camera, (1280, 720))
            
            writer = rep.WriterRegistry.get("BasicWriter")
            cam_output = os.path.join(env_output, f"cam_{cam['name']}")
            writer.initialize(
                output_dir=cam_output,
                rgb=True,
                bounding_box_2d_tight=True,
                semantic_segmentation=True,
                instance_segmentation=True,
            )
            writer.attach([rp])
            
            env_data["cameras_used"].append(cam["name"])
            print(f"  [CAM] {cam['name']}: pos={cam['pos']}, look={cam['look']}")
        
        # --- Randomization for variety between frames ---
        with rep.trigger.on_frame(num_frames=FRAMES_PER_CAMERA):
            # Slightly randomize prop positions each frame
            for person in people_prims:
                with person:
                    # Small position jitter (simulates slight movement, keeps grounded at Y≈0)
                    rep.modify.pose(
                        position=rep.distribution.uniform(
                            (-0.3, -0.05, -0.3),
                            (0.3, 0.05, 0.3)
                        ),
                        rotation=rep.distribution.uniform(
                            (-5, -180, -5),
                            (5, 180, 5)
                        ),
                    )
        
        print(f"\n  [CAPTURE] Warming up (25 frames)...")
        rep.orchestrator.preview()
        
        # Give time for assets to fully load and render
        try:
            app = omni.kit.app.get_app()
            for _ in range(25):
                app.update()
        except:
            pass
        
        print(f"  [CAPTURE] Capturing {FRAMES_PER_CAMERA * num_cameras} frames across {num_cameras} cameras...")
        rep.orchestrator.run()
        
        # Wait for capture to complete
        try:
            app = omni.kit.app.get_app()
            for _ in range(50):
                app.update()
        except:
            pass
    
    manifest["environments"].append(env_data)
    env_index += 1

# ============================================================
# PHASE 4: Verify outputs and write manifest
# ============================================================
print(f"\n{'='*60}")
print("[PRAQTOR DATΔ v4] Phase 4: Verifying outputs...")
print(f"{'='*60}")

total_files = 0
total_rgb = 0
rgb_sizes = []

for root, dirs, files in os.walk(OUTPUT_DIR):
    for f in files:
        total_files += 1
        fpath = os.path.join(root, f)
        if f.startswith("rgb_") and f.endswith(".png"):
            total_rgb += 1
            size_kb = os.path.getsize(fpath) / 1024
            rgb_sizes.append(size_kb)

avg_rgb_size = sum(rgb_sizes) / len(rgb_sizes) if rgb_sizes else 0

manifest["tpose_fix_method"] = "skelanim_binding" if tpose_fix_success else "timeline_advance_only"
manifest["tpose_fix_success"] = tpose_fix_success
manifest["output_stats"] = {
    "total_files": total_files,
    "total_rgb_images": total_rgb,
    "avg_rgb_size_kb": round(avg_rgb_size, 1),
    "photorealistic": avg_rgb_size > 100,  # Real scenes are 100KB+, cubes are ~20KB
}

# Write manifest
manifest_path = os.path.join(OUTPUT_DIR, "manifest_v4.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)

print(f"\n[PRAQTOR DATΔ v4] RESULTS:")
print(f"  Total files: {total_files}")
print(f"  RGB images: {total_rgb}")
print(f"  Avg RGB size: {avg_rgb_size:.1f} KB")
print(f"  Photorealistic: {'YES' if avg_rgb_size > 100 else 'NO (likely cubes)'}")
print(f"  T-pose fix: {manifest['tpose_fix_method']}")
print(f"  T-pose success: {tpose_fix_success}")
print(f"  Manifest: {manifest_path}")
print(f"\n[PRAQTOR DATΔ v4] Done!")
