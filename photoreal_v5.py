"""PRAQTOR DATΔ — V5 Photoreal Scene Generator
Uses omni.anim.people Spawn system for properly animated characters.
REQUIRES: Run patch_kit_config.py ONCE before first use on each pod.

Pipeline:
1. Boot SimulationApp (with patched kit config enabling omni.anim.graph.core)
2. Enable omni.anim.people extension
3. Load warehouse environment
4. Spawn characters via omni.anim.people command system
5. Setup characters (attaches AnimGraph + behavior scripts)
6. Play timeline to evaluate animations
7. Render with Replicator from multiple camera angles

Usage: /isaac-sim/python.sh photoreal_v5.py
"""
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import omni.kit.app
import omni.usd
import omni.timeline
import omni.replicator.core as rep
import os, json, time, random
from pxr import Usd, UsdGeom, Sdf, Gf

app = omni.kit.app.get_app()
ext_mgr = app.get_extension_manager()

S3 = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
OUTPUT_DIR = "/workspace/output_v5"
LOG_FILE = "/workspace/v5_log.txt"
RESULTS_FILE = "/workspace/v5_results.json"

out = open(LOG_FILE, "w")
results = {"scenes": [], "total_images": 0, "success": False}

def log(msg):
    print(msg)
    out.write(msg + "\n")
    out.flush()

# ============================================================
# STEP 1: Enable animation extensions
# ============================================================
log("[V5] Step 1: Enabling extensions...")
anim_exts = [
    "omni.anim.graph.core",
    "omni.anim.graph.schema",
    "omni.anim.people",
    "omni.anim.skelJoint",
    "omni.anim.retarget.core",
    "omni.anim.navigation.core",
]
for e in anim_exts:
    try:
        ext_mgr.set_extension_enabled_immediate(e, True)
        log(f"  Enabled: {e}")
    except Exception as ex:
        log(f"  Failed: {e} - {ex}")
for _ in range(30):
    app.update()
log("  Extensions ready")

# ============================================================
# CONFIGURATION
# ============================================================
WAREHOUSES = [
    f"{S3}/Isaac/Environments/Simple_Warehouse/warehouse.usd",
    f"{S3}/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
    f"{S3}/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
]

CHARACTERS = [
    "male_adult_construction_03",
    "male_adult_police_01",
    "male_adult_business_02",
    "female_adult_police_01",
]

ACTIONS = [
    ("Idle", "5"),
    ("LookAround", "5"),
]

CAMERA_PRESETS = [
    {"name": "wide_front",    "pos": (8, 2.5, 8),    "look": (0, 1.0, 0)},
    {"name": "medium_left",   "pos": (-5, 2.0, 3),   "look": (0, 1.0, 0)},
    {"name": "close_worker",  "pos": (2, 1.5, 2),    "look": (0, 1.0, 0)},
    {"name": "overhead",      "pos": (0, 6.0, 0.1),  "look": (0, 0, 0)},
    {"name": "aisle_view",    "pos": (0, 1.8, -6),   "look": (0, 1.2, 2)},
    {"name": "loading_dock",  "pos": (10, 2.0, -3),  "look": (3, 1.0, 0)},
    {"name": "security_cam",  "pos": (-8, 4.0, -8),  "look": (0, 0.5, 0)},
    {"name": "shelf_level",   "pos": (3, 0.8, -2),   "look": (-1, 1.2, 1)},
]

# Character spawn positions (floor level, spread across warehouse)
SPAWN_POSITIONS = [
    (0, 0, 0, 0),
    (3, 0, -2, 90),
    (-2, 0, 3, 180),
    (5, 0, 1, 270),
]

# ============================================================
# STEP 2: Try omni.anim.people programmatic API
# ============================================================
log("\n[V5] Step 2: Testing omni.anim.people API...")
people_api_available = False
try:
    import omni.anim.people
    log(f"  Module loaded: {dir(omni.anim.people)}")
    people_api_available = True
except Exception as e:
    log(f"  omni.anim.people import failed: {e}")
    log("  Will use manual character loading with AnimGraph")

# ============================================================
# SCENE GENERATION LOOP
# ============================================================
num_scenes = min(len(WAREHOUSES), 3)
scene_count = 0

for scene_idx in range(num_scenes):
    log(f"\n{'='*60}")
    log(f"[V5] SCENE {scene_idx+1}/{num_scenes}")
    log(f"{'='*60}")

    # New stage
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    for _ in range(10):
        app.update()

    # Load warehouse
    wh_url = WAREHOUSES[scene_idx]
    wh_name = os.path.basename(wh_url).replace(".usd", "")
    log(f"  Loading warehouse: {wh_name}")
    wh_prim = stage.DefinePrim("/World/Warehouse")
    wh_prim.GetReferences().AddReference(wh_url)

    # Create Characters parent prim (required by omni.anim.people)
    chars_parent = stage.DefinePrim("/World/Characters", "Xform")

    # Wait for warehouse to load
    for _ in range(60):
        app.update()
    log("  Warehouse loaded")

    # Spawn characters
    num_chars = random.randint(2, min(3, len(CHARACTERS)))
    char_selection = random.sample(CHARACTERS, num_chars)

    log(f"  Spawning {num_chars} characters...")
    commands = []
    for i, char_name in enumerate(char_selection):
        x, y, z, rot = SPAWN_POSITIONS[i]
        # Build Spawn command
        commands.append(f"Spawn {char_name}_{i} {x} {y} {z} {rot}")
        log(f"    {char_name}_{i} at ({x},{y},{z}) rot={rot}")

    # Add actions after spawning
    for i, char_name in enumerate(char_selection):
        action, duration = random.choice(ACTIONS)
        commands.append(f"{char_name}_{i} {action} {duration}")
        log(f"    {char_name}_{i}: {action} for {duration}s")

    # Try to use omni.anim.people command system
    log("  Processing commands via omni.anim.people...")
    try:
        # Write command file
        cmd_file = f"/workspace/commands_scene_{scene_idx}.txt"
        with open(cmd_file, "w") as cf:
            cf.write("\n".join(commands))
        log(f"    Command file: {cmd_file}")

        # Try to access PeopleSimulation API
        from omni.anim.people.scripts.global_agent_manager import GlobalAgentManager
        gam = GlobalAgentManager.instance()
        if gam:
            log("    GlobalAgentManager available!")
            # Load and parse commands
            gam.set_command_text("\n".join(commands))
            gam.load_characters()
            for _ in range(120):
                app.update()
            gam.setup_characters()
            for _ in range(60):
                app.update()
            log("    Characters loaded and setup via API")
        else:
            log("    GlobalAgentManager not available, using manual approach")
            raise Exception("No GlobalAgentManager")

    except Exception as e:
        log(f"    omni.anim.people API failed: {e}")
        log("    Falling back to manual character loading...")

        # Manual fallback: load characters directly with AnimGraph
        for i, char_name in enumerate(char_selection):
            x, y, z, rot = SPAWN_POSITIONS[i]
            char_url = f"{S3}/Isaac/People/Characters/{char_name}/{char_name}.usd"
            prim_path = f"/World/Characters/{char_name}_{i}"

            char_prim = stage.DefinePrim(prim_path, "Xform")
            char_prim.GetReferences().AddReference(char_url)
            xf = UsdGeom.Xformable(char_prim)
            xf.AddTranslateOp().Set(Gf.Vec3d(x, y, z))
            if rot != 0:
                xf.AddRotateYOp().Set(float(rot))

        # Load Biped_Setup (contains AnimGraph and animations)
        biped_url = f"{S3}/Isaac/People/Characters/biped_demo/biped_demo_meters.usd"
        # Some versions have a Biped_Setup.usd with the AnimGraph
        try:
            setup_prim = stage.DefinePrim("/World/Biped_Setup")
            setup_prim.GetReferences().AddReference(
                f"{S3}/Isaac/People/Characters/Biped_Setup.usd"
            )
            log("    Loaded Biped_Setup.usd (AnimGraph)")
        except:
            log("    Biped_Setup.usd not found, continuing without")

        for _ in range(60):
            app.update()
        log("    Characters loaded manually")

    # Play timeline for animation evaluation
    log("  Playing timeline (300 frames for animation)...")
    timeline = omni.timeline.get_timeline_interface()
    timeline.set_current_time(0)
    timeline.play()
    for i in range(300):
        app.update()
        if i % 100 == 0:
            log(f"    Frame {i}/300")
    # Don't pause - keep playing for render

    # ============================================================
    # RENDER from multiple camera angles
    # ============================================================
    scene_dir = f"{OUTPUT_DIR}/scene_{scene_idx}_{wh_name}"
    os.makedirs(scene_dir, exist_ok=True)

    log(f"  Rendering from {len(CAMERA_PRESETS)} camera angles...")

    # Add lighting
    rep.create.light(light_type="Dome", intensity=1000)
    rep.create.light(
        light_type="Distant",
        intensity=3000,
        rotation=(-45, 30, 0)
    )

    # Select camera angles for this scene
    num_angles = min(4, len(CAMERA_PRESETS))
    selected_cams = random.sample(CAMERA_PRESETS, num_angles)

    scene_images = 0
    for cam_idx, cam in enumerate(selected_cams):
        try:
            cam_name = cam["name"]
            camera = rep.create.camera(
                position=cam["pos"],
                look_at=cam["look"]
            )
            rp = rep.create.render_product(camera, (1920, 1080))
            writer = rep.WriterRegistry.get("BasicWriter")
            cam_dir = f"{scene_dir}/{cam_name}"
            writer.initialize(
                output_dir=cam_dir,
                rgb=True,
                bounding_box_2d_tight=True,
                semantic_segmentation=True,
            )
            writer.attach([rp])
            rep.orchestrator.run()
            for _ in range(30):
                app.update()

            # Count output files
            if os.path.exists(cam_dir):
                rgbs = [f for f in os.listdir(cam_dir) if f.startswith("rgb_")]
                if rgbs:
                    sz = os.path.getsize(os.path.join(cam_dir, rgbs[0])) / 1024
                    log(f"    [{cam_name}] {len(rgbs)} images, {sz:.1f} KB")
                    scene_images += len(rgbs)
            else:
                log(f"    [{cam_name}] No output directory")
        except Exception as e:
            log(f"    [{cam_name}] Render error: {e}")

    timeline.pause()

    results["scenes"].append({
        "warehouse": wh_name,
        "characters": num_chars,
        "cameras": num_angles,
        "images": scene_images,
    })
    results["total_images"] += scene_images
    scene_count += 1
    log(f"  Scene {scene_idx+1} complete: {scene_images} images")

# ============================================================
# SUMMARY
# ============================================================
log(f"\n{'='*60}")
log("[V5] GENERATION COMPLETE")
log(f"{'='*60}")
log(f"  Scenes rendered: {scene_count}")
log(f"  Total images: {results['total_images']}")
for s in results["scenes"]:
    log(f"    {s['warehouse']}: {s['images']} images, {s['characters']} chars, {s['cameras']} cams")

results["success"] = results["total_images"] > 0

with open(RESULTS_FILE, "w") as f:
    json.dump(results, f, indent=2)

# Package outputs
log("\n[V5] Packaging outputs...")
os.system(f"cd /workspace && tar czf output_v5.tar.gz output_v5/")
tar_size = os.path.getsize("/workspace/output_v5.tar.gz") / (1024*1024) if os.path.exists("/workspace/output_v5.tar.gz") else 0
log(f"  Tarball: {tar_size:.1f} MB")

# Copy first image to repo for quick preview
try:
    for s in results["scenes"]:
        wh = s["warehouse"]
        scene_path = f"{OUTPUT_DIR}/scene_0_{wh}"
        if os.path.exists(scene_path):
            for cam_dir in os.listdir(scene_path):
                full_path = os.path.join(scene_path, cam_dir)
                if os.path.isdir(full_path):
                    for f in os.listdir(full_path):
                        if f.startswith("rgb_"):
                            src = os.path.join(full_path, f)
                            dst = "/workspace/praqtor-data-scripts/v5_preview.png"
                            os.system(f"cp {src} {dst}")
                            log(f"  Preview: v5_preview.png")
                            break
                    break
            break
except:
    pass

log("\n[V5] Done!")
out.close()
simulation_app.close()
