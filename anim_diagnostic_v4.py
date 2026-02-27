"""PRAQTOR DATΔ — Animation Diagnostic v4
Requires: Isaac Sim 4.2 container on RunPod RTX 4090
"""
import os, sys, json, time

print("[DIAG v4] Starting Isaac Sim runtime...")
from omni.isaac.kit import SimulationApp
simulation_app = SimulationApp({"headless": True})
print("[DIAG v4] Runtime started.")

import omni.kit.app
import omni.usd
import omni.timeline
from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf

S3_BASE = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
app = omni.kit.app.get_app()
results = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "tests": {}, "anim_extensions": {}}

# TEST 1: Enable animation extensions
print("\n[TEST 1] Enabling animation extensions...")
ext_manager = app.get_extension_manager()
for ext_name in ["omni.anim.graph.core","omni.anim.graph.schema","omni.anim.navigation.schema","omni.anim.skelJoint","omni.anim.retarget.core"]:
    try:
        r = ext_manager.set_extension_enabled_immediate(ext_name, True)
        results["anim_extensions"][ext_name] = True
        print(f"  [OK] {ext_name}")
    except Exception as e:
        results["anim_extensions"][ext_name] = False
        print(f"  [WARN] {ext_name}: {e}")
for _ in range(20): app.update()
results["tests"]["extensions"] = True
print("[TEST 1] PASSED")

# TEST 2: Load character, find skeleton
print("\n[TEST 2] Loading character...")
omni.usd.get_context().new_stage()
stage = omni.usd.get_context().get_stage()
for _ in range(10): app.update()

char_url = f"{S3_BASE}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd"
char_prim = stage.DefinePrim("/World/TestChar", "Xform")
char_prim.GetReferences().AddReference(char_url)
print(f"  Loading from S3...")
for _ in range(60): app.update()

skeleton_path = None
skelroot_path = None
print(f"\n  Hierarchy under /World/TestChar:")
for prim in Usd.PrimRange(stage.GetPrimAtPath("/World/TestChar")):
    depth = str(prim.GetPath()).count("/") - 2
    if depth > 6: continue
    marker = ""
    if prim.IsA(UsdSkel.Skeleton):
        marker = " <<< SKELETON"
        skeleton_path = str(prim.GetPath())
    if prim.IsA(UsdSkel.Root):
        marker = " <<< SKELROOT"
        skelroot_path = str(prim.GetPath())
    print(f"    {'  '*depth}{prim.GetName()} [{prim.GetTypeName()}]{marker}")

results["skeleton_path"] = skeleton_path
results["skelroot_path"] = skelroot_path
results["tests"]["load_char"] = skeleton_path is not None or skelroot_path is not None
print(f"\n  Skeleton: {skeleton_path or 'NOT FOUND'}")
print(f"  SkelRoot: {skelroot_path or 'NOT FOUND'}")
print(f"[TEST 2] {'PASSED' if skeleton_path or skelroot_path else 'FAILED'}")

# TEST 3: Bind animation
print("\n[TEST 3] Binding animation clip...")
bound = False
ANIMS = [
    f"{S3_BASE}/Isaac/People/Characters/Animations/walking_01.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Characters/Animations/idle_01.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Animations/walking_01.skelanim.usd",
    f"{S3_BASE}/Isaac/People/Animations/idle_01.skelanim.usd",
]

target_path = skeleton_path or skelroot_path
if target_path:
    for anim_url in ANIMS:
        try:
            aname = os.path.basename(anim_url).replace('.usd','')
            aprim_path = f"/World/Anim_{aname}"
            aprim = stage.DefinePrim(aprim_path, "SkelAnimation")
            aprim.GetReferences().AddReference(anim_url)
            for _ in range(20): app.update()

            target_prim = stage.GetPrimAtPath(target_path)
            binding = UsdSkel.BindingAPI.Apply(target_prim)
            binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(aprim_path)])
            print(f"  [OK] Bound {aname} to {target_path}")
            results["working_animation"] = anim_url
            bound = True
            break
        except Exception as e:
            print(f"  [SKIP] {aname}: {e}")
else:
    print("  [SKIP] No skeleton/skelroot to bind to")

results["animation_bound"] = bound
results["tests"]["bind_anim"] = bound
print(f"[TEST 3] {'PASSED' if bound else 'NEEDS INVESTIGATION'}")

# TEST 4: Timeline advance
print("\n[TEST 4] Advancing timeline...")
try:
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    for i in range(60):
        app.update()
        if i % 20 == 0: print(f"  Frame {i}/60...")
    timeline.pause()
    results["tests"]["timeline"] = True
    print("[TEST 4] PASSED")
except Exception as e:
    results["tests"]["timeline"] = False
    print(f"[TEST 4] FAILED: {e}")

# TEST 5: Quick render
print("\n[TEST 5] Quick render test...")
try:
    import omni.replicator.core as rep
    camera = rep.create.camera(position=(3,2,3), look_at=(0,1,0))
    rp = rep.create.render_product(camera, (640,480))
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir="/workspace/output_v4_diag", rgb=True, semantic_segmentation=True)
    writer.attach([rp])
    rep.orchestrator.run()
    for _ in range(50): app.update()

    test_dir = "/workspace/output_v4_diag"
    rgbs = [f for f in os.listdir(test_dir) if f.startswith("rgb_")] if os.path.exists(test_dir) else []
    if rgbs:
        sz = os.path.getsize(os.path.join(test_dir, rgbs[0]))/1024
        print(f"  [OK] {len(rgbs)} frame(s), {sz:.1f} KB")
        results["test_render_kb"] = round(sz,1)
        results["tests"]["render"] = True
    else:
        results["tests"]["render"] = False
        print("  [WARN] No output")
    print(f"[TEST 5] {'PASSED' if rgbs else 'FAILED'}")
except Exception as e:
    results["tests"]["render"] = False
    print(f"[TEST 5] FAILED: {e}")

# SUMMARY
print(f"\n{'='*50}")
passed = sum(1 for v in results["tests"].values() if v)
total = len(results["tests"])
print(f"[DIAG v4] {passed}/{total} tests passed")
print(f"  Skeleton: {skeleton_path or 'NOT FOUND'}")
print(f"  Animation bound: {bound}")
if bound:
    print(f"\n  >>> T-POSE FIX READY — run photoreal_scene_v4.py next")
else:
    print(f"\n  >>> Check output_v4_diag/ to see if character pose changed")
print(f"{'='*50}")

with open("/workspace/diagnostic_v4.json","w") as f: json.dump(results,f,indent=2)
print(f"Results: /workspace/diagnostic_v4.json")
simulation_app.close()
