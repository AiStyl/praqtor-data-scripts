"""
PRAQTOR DATΔ — Photoreal Scene v4
T-pose fix + Character Grounding + Camera Variety
Requires: Isaac Sim 4.2 container on RunPod RTX 4090
"""
import os, sys, json, random, time

print("[PRAQTOR DATΔ v4] Starting Isaac Sim runtime...")
from omni.isaac.kit import SimulationApp
simulation_app = SimulationApp({"headless": True})
print("[PRAQTOR DATΔ v4] Runtime started.")

import omni.kit.app
import omni.usd
import omni.timeline
import omni.replicator.core as rep
from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf

app = omni.kit.app.get_app()

# Enable animation extensions (KEY fix for headless T-pose)
print("[PRAQTOR DATΔ v4] Enabling animation extensions...")
ext_manager = app.get_extension_manager()
for ext_name in ["omni.anim.graph.core","omni.anim.graph.schema","omni.anim.navigation.schema","omni.anim.skelJoint","omni.anim.retarget.core"]:
    try:
        ext_manager.set_extension_enabled_immediate(ext_name, True)
        print(f"  [OK] {ext_name}")
    except Exception as e:
        print(f"  [WARN] {ext_name}: {e}")
for _ in range(20): app.update()

# ============================================================
# CONFIGURATION
# ============================================================
S3_BASE = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"

WAREHOUSES = [
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/warehouse.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
]

CHARACTERS = [
    f"{S3_BASE}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd",
    f"{S3_BASE}/Isaac/People/Characters/male_adult_construction_05/male_adult_construction_05.usd",
    f"{S3_BASE}/Isaac/People/Characters/male_adult_police_04/male_adult_police_04.usd",
    f"{S3_BASE}/Isaac/People/Characters/female_adult_police_01/female_adult_police_01.usd",
]

ALL_ANIMATIONS = [
    f"{S3_BASE}/Isaac/People/Characters/Animations/walking_01.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Characters/Animations/walking_02.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Characters/Animations/idle_01.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Characters/Animations/idle_02.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Characters/Animations/waving_01.skelanim.usd",
]

PROPS = [
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd",
    f"{S3_BASE}/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd",
]

FORKLIFT = f"{S3_BASE}/Isaac/Props/Forklift/forklift.usd"

CAMERA_PRESETS = [
    {"name": "wide_front",    "pos": (8, 3.5, 6),     "look": (0, 1.0, 0)},
    {"name": "wide_corner",   "pos": (-6, 4.0, 8),    "look": (2, 0.5, -2)},
    {"name": "medium_aisle",  "pos": (3, 1.8, 2),     "look": (-3, 1.0, -2)},
    {"name": "medium_side",   "pos": (-4, 2.0, 0),    "look": (2, 1.2, 0)},
    {"name": "close_worker",  "pos": (1.5, 1.6, 1.5), "look": (0, 1.2, 0)},
    {"name": "close_forklift","pos": (2, 1.2, -3),    "look": (0, 0.8, -4)},
    {"name": "overhead",      "pos": (0, 8, 0),       "look": (0, 0, 0)},
    {"name": "high_angle",    "pos": (5, 6, 5),       "look": (0, 0, 0)},
]

OUTPUT_DIR = "/workspace/output_v4"
FRAMES_PER_ENV = 17
TOTAL_ENVIRONMENTS = 3

manifest = {
    "version": "4.0",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "environments": [],
    "tpose_fix_method": "skelanim_binding + anim_extensions",
    "character_grounding": True,
    "camera_presets": len(CAMERA_PRESETS),
}

# ============================================================
# HELPER: Apply animation to a SkelRoot/Skeleton via USD API
# ============================================================
def bind_animation(stage, root_path, anim_url):
    """Find skeleton under root_path, create anim reference, bind it."""
    target = None
    for prim in Usd.PrimRange(stage.GetPrimAtPath(root_path)):
        if prim.IsA(UsdSkel.Skeleton):
            target = prim
            break
    if target is None:
        for prim in Usd.PrimRange(stage.GetPrimAtPath(root_path)):
            if prim.IsA(UsdSkel.Root):
                target = prim
                break
    if target is None:
        return False

    aname = os.path.basename(anim_url).replace('.usd','').replace('.','_')
    aprim_path = f"{root_path}/Anim_{aname}"
    aprim = stage.DefinePrim(aprim_path, "SkelAnimation")
    aprim.GetReferences().AddReference(anim_url)
    for _ in range(10): app.update()

    binding = UsdSkel.BindingAPI.Apply(target)
    binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(aprim_path)])
    return True

# ============================================================
# RENDER LOOP
# ============================================================
selected_warehouses = random.sample(WAREHOUSES, min(TOTAL_ENVIRONMENTS, len(WAREHOUSES)))

for env_idx, warehouse_path in enumerate(selected_warehouses):
    env_name = os.path.basename(warehouse_path).replace('.usd', '')
    env_output = os.path.join(OUTPUT_DIR, f"env_{env_idx}")
    os.makedirs(env_output, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"[ENV {env_idx}] {env_name}")
    print(f"{'='*60}")

    env_data = {"name": env_name, "characters": [], "animations": [], "cameras": []}

    with rep.new_layer():
        # Load warehouse
        warehouse = rep.create.from_usd(warehouse_path, semantics=[("class", "warehouse")])
        print(f"  [OK] Loaded warehouse")

        # Spawn characters at FLOOR LEVEL (y=0)
        CHAR_POSITIONS = [(0,0,0), (3,0,-2), (-2,0,3)]
        num_chars = random.randint(2, 3)
        selected_chars = random.sample(CHARACTERS, min(num_chars, len(CHARACTERS)))
        people = []

        for i, (char_path, pos) in enumerate(zip(selected_chars, CHAR_POSITIONS[:num_chars])):
            person = rep.create.from_usd(char_path, semantics=[("class","person")], position=pos)
            people.append(person)
            cname = os.path.basename(os.path.dirname(char_path))
            print(f"  [OK] Spawned {cname} at {pos}")
            env_data["characters"].append(cname)

        # Forklift + props
        rep.create.from_usd(FORKLIFT, semantics=[("class","forklift")], position=(4,0,-3))
        for j, pp in enumerate(random.sample(PROPS, min(3, len(PROPS)))):
            ppos = [(-3,0,-1),(2,0,2),(-1,0,-4)]
            rep.create.from_usd(pp, semantics=[("class","prop")], position=ppos[j])
        print(f"  [OK] Props + forklift placed")

        # Let assets load fully
        for _ in range(60): app.update()

        # --- T-POSE FIX: bind animations via USD API ---
        print(f"\n  [TPOSE FIX] Searching for skeletons...")
        stage = omni.usd.get_context().get_stage()
        anim_count = 0
        if stage:
            for prim in stage.Traverse():
                if prim.IsA(UsdSkel.Root):
                    anim_clip = random.choice(ALL_ANIMATIONS)
                    ok = bind_animation(stage, str(prim.GetPath()), anim_clip)
                    aname = os.path.basename(anim_clip)
                    status = "BOUND" if ok else "FAILED"
                    print(f"    {prim.GetPath()} -> {aname} [{status}]")
                    env_data["animations"].append({"skelroot": str(prim.GetPath()), "clip": aname, "ok": ok})
                    if ok: anim_count += 1

            # Advance timeline to apply animations
            if anim_count > 0:
                print(f"  [TPOSE FIX] Bound {anim_count} animations, advancing timeline...")
                try:
                    timeline = omni.timeline.get_timeline_interface()
                    timeline.play()
                    for _ in range(60): app.update()
                    timeline.pause()
                    print(f"  [TPOSE FIX] Timeline advanced 60 frames")
                except Exception as e:
                    print(f"  [TPOSE FIX] Timeline error: {e}")
            else:
                print(f"  [TPOSE FIX] No skeletons found for binding")

        # Lighting
        rep.create.light(light_type="Dome", intensity=1000,
            texture=f"{S3_BASE}/Isaac/Materials/Textures/Skies/Indoor/autoshop_01_4k.hdr")
        rep.create.light(light_type="Rect", intensity=5000, position=(0,5,0),
            rotation=(-90,0,0), scale=(8,8,1))

        # Cameras — pick 4 random presets
        selected_cams = random.sample(CAMERA_PRESETS, 4)
        for cam in selected_cams:
            camera = rep.create.camera(position=cam["pos"], look_at=cam["look"], focal_length=28.0)
            rp = rep.create.render_product(camera, (1280, 720))
            cam_out = os.path.join(env_output, f"cam_{cam['name']}")
            writer = rep.WriterRegistry.get("BasicWriter")
            writer.initialize(output_dir=cam_out, rgb=True,
                bounding_box_2d_tight=True, semantic_segmentation=True)
            writer.attach([rp])
            env_data["cameras"].append(cam["name"])
            print(f"  [CAM] {cam['name']}")

        # Randomize between frames
        with rep.trigger.on_frame(num_frames=FRAMES_PER_ENV):
            for person in people:
                with person:
                    rep.modify.pose(
                        position=rep.distribution.uniform((-0.3,-0.05,-0.3),(0.3,0.05,0.3)),
                        rotation=rep.distribution.uniform((-5,-180,-5),(5,180,5)),
                    )

        # Warm up + capture
        print(f"\n  [CAPTURE] Warming up...")
        rep.orchestrator.preview()
        for _ in range(25): app.update()

        print(f"  [CAPTURE] Rendering {FRAMES_PER_ENV} frames across 4 cameras...")
        rep.orchestrator.run()
        for _ in range(50): app.update()

    manifest["environments"].append(env_data)

# ============================================================
# VERIFY OUTPUTS
# ============================================================
print(f"\n{'='*60}")
print("[PRAQTOR DATΔ v4] Verifying outputs...")

total_files = 0
total_rgb = 0
rgb_sizes = []
for root, dirs, files in os.walk(OUTPUT_DIR):
    for f in files:
        total_files += 1
        fpath = os.path.join(root, f)
        if f.startswith("rgb_") and f.endswith(".png"):
            total_rgb += 1
            rgb_sizes.append(os.path.getsize(fpath)/1024)

avg_kb = sum(rgb_sizes)/len(rgb_sizes) if rgb_sizes else 0
manifest["output_stats"] = {
    "total_files": total_files, "total_rgb": total_rgb,
    "avg_rgb_kb": round(avg_kb,1), "photorealistic": avg_kb > 100,
}

with open(os.path.join(OUTPUT_DIR, "manifest_v4.json"), "w") as f:
    json.dump(manifest, f, indent=2)

print(f"  Total files: {total_files}")
print(f"  RGB images: {total_rgb}")
print(f"  Avg size: {avg_kb:.1f} KB ({'photorealistic' if avg_kb > 100 else 'CUBES'})")
print(f"  Manifest: {OUTPUT_DIR}/manifest_v4.json")
print(f"\n[PRAQTOR DATΔ v4] Done!")

simulation_app.close()
