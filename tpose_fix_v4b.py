"""PRAQTOR DATΔ — T-Pose Fix Test v4b
Uses CONFIRMED animation paths from probe_anims.py results.
Tests direct SkelAnimation binding with real .skelanim.usd files.
"""
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import os, json, time
import omni.kit.app
import omni.usd
import omni.timeline
from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf

app = omni.kit.app.get_app()
S3 = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"

# Enable anim extensions
print("[v4b] Enabling animation extensions...")
ext = app.get_extension_manager()
for e in ["omni.anim.graph.core","omni.anim.graph.schema","omni.anim.skelJoint","omni.anim.retarget.core"]:
    try: ext.set_extension_enabled_immediate(e, True)
    except: pass
for _ in range(20): app.update()

# CONFIRMED animation paths
ANIMS = {
    "idle": f"{S3}/Isaac/People/Animations/stand_idle_loop.skelanim.usd",
    "walk": f"{S3}/Isaac/People/Animations/stand_walk_loop.skelanim.usd",
    "wave": f"{S3}/Isaac/People/Animations/stand_idle_wave_loop.skelanim.usd",
    "look": f"{S3}/Isaac/People/Animations/LookAround.skelanim.usd",
    "sit":  f"{S3}/Isaac/People/Animations/Sit.skelanim.usd",
}

results = {"tests": [], "skeleton_info": {}, "success": False}
out = open("/workspace/tpose_fix_log.txt", "w")

def log(msg):
    print(msg)
    out.write(msg + "\n")
    out.flush()

# ============================================================
# TEST A: Load character, inspect, try direct skelanim binding
# ============================================================
log("\n[TEST A] Load character + direct skelanim binding")
omni.usd.get_context().new_stage()
stage = omni.usd.get_context().get_stage()
for _ in range(10): app.update()

# Load character
char_url = f"{S3}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd"
char_prim = stage.DefinePrim("/World/Person1", "Xform")
char_prim.GetReferences().AddReference(char_url)
log(f"  Loading character from S3...")
for _ in range(60): app.update()

# Find skeleton and skelroot
skeleton_path = None
skelroot_path = None
for prim in Usd.PrimRange(stage.GetPrimAtPath("/World/Person1")):
    if prim.IsA(UsdSkel.Skeleton) and skeleton_path is None:
        skeleton_path = str(prim.GetPath())
    if prim.IsA(UsdSkel.Root) and skelroot_path is None:
        skelroot_path = str(prim.GetPath())

log(f"  Skeleton: {skeleton_path}")
log(f"  SkelRoot: {skelroot_path}")
results["skeleton_info"] = {"skeleton": skeleton_path, "skelroot": skelroot_path}

# Try binding each animation to both skeleton and skelroot
if skelroot_path or skeleton_path:
    for anim_name, anim_url in ANIMS.items():
        log(f"\n  --- Trying {anim_name}: {os.path.basename(anim_url)} ---")
        test = {"anim": anim_name, "url": anim_url, "approaches": []}

        # Approach 1: Bind to SkelRoot
        if skelroot_path:
            try:
                aprim_path = f"/World/Anim_{anim_name}_root"
                aprim = stage.DefinePrim(aprim_path)
                aprim.GetReferences().AddReference(anim_url)
                for _ in range(20): app.update()

                target = stage.GetPrimAtPath(skelroot_path)
                binding = UsdSkel.BindingAPI.Apply(target)
                binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(aprim_path)])
                log(f"    [A1] Bound to SkelRoot: OK")
                test["approaches"].append({"target": "skelroot", "ok": True})
            except Exception as e:
                log(f"    [A1] SkelRoot binding failed: {e}")
                test["approaches"].append({"target": "skelroot", "ok": False, "err": str(e)})

        # Approach 2: Bind to Skeleton
        if skeleton_path:
            try:
                aprim_path = f"/World/Anim_{anim_name}_skel"
                aprim = stage.DefinePrim(aprim_path)
                aprim.GetReferences().AddReference(anim_url)
                for _ in range(20): app.update()

                target = stage.GetPrimAtPath(skeleton_path)
                binding = UsdSkel.BindingAPI.Apply(target)
                binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(aprim_path)])
                log(f"    [A2] Bound to Skeleton: OK")
                test["approaches"].append({"target": "skeleton", "ok": True})
            except Exception as e:
                log(f"    [A2] Skeleton binding failed: {e}")
                test["approaches"].append({"target": "skeleton", "ok": False, "err": str(e)})

        # Approach 3: Clear animationGraph, then bind
        if skelroot_path:
            try:
                sr_prim = stage.GetPrimAtPath(skelroot_path)
                ag_rel = sr_prim.GetRelationship("animationGraph")
                if ag_rel and ag_rel.IsValid():
                    ag_rel.ClearTargets(True)
                    log(f"    [A3] Cleared animationGraph relationship")

                aprim_path = f"/World/Anim_{anim_name}_clean"
                aprim = stage.DefinePrim(aprim_path)
                aprim.GetReferences().AddReference(anim_url)
                for _ in range(20): app.update()

                binding = UsdSkel.BindingAPI.Apply(sr_prim)
                binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(aprim_path)])
                log(f"    [A3] Bound after clearing animGraph: OK")
                test["approaches"].append({"target": "skelroot_clean", "ok": True})
            except Exception as e:
                log(f"    [A3] Clean binding failed: {e}")
                test["approaches"].append({"target": "skelroot_clean", "ok": False, "err": str(e)})

        results["tests"].append(test)
        # Only test first animation fully, break to save time
        break

# Advance timeline
log("\n[TIMELINE] Advancing 120 frames...")
try:
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    for i in range(120):
        app.update()
        if i % 30 == 0: log(f"  Frame {i}/120")
    timeline.pause()
    log("  Timeline done")
except Exception as e:
    log(f"  Timeline error: {e}")

# ============================================================
# TEST B: Render the character to see if pose changed
# ============================================================
log("\n[RENDER] Capturing test image...")
try:
    import omni.replicator.core as rep

    # Add light so we can see the character
    rep.create.light(light_type="Dome", intensity=2000)
    rep.create.light(light_type="Distant", intensity=3000, rotation=(-45, 30, 0))

    camera = rep.create.camera(position=(2, 1.5, 2), look_at=(0, 0.8, 0))
    rp = rep.create.render_product(camera, (1280, 720))
    writer = rep.WriterRegistry.get("BasicWriter")
    test_dir = "/workspace/output_v4b_test"
    writer.initialize(output_dir=test_dir, rgb=True)
    writer.attach([rp])
    rep.orchestrator.run()
    for _ in range(60): app.update()

    rgbs = [f for f in os.listdir(test_dir) if f.startswith("rgb_")] if os.path.exists(test_dir) else []
    if rgbs:
        sz = os.path.getsize(os.path.join(test_dir, rgbs[0])) / 1024
        log(f"  Rendered: {len(rgbs)} image(s), {sz:.1f} KB")
        results["render_kb"] = round(sz, 1)
        results["success"] = sz > 50  # Real character = larger image
    else:
        log("  No output!")
except Exception as e:
    log(f"  Render error: {e}")

# ============================================================
# TEST C: Also try biped_demo (simpler character)
# ============================================================
log("\n[TEST C] Trying biped_demo character (simpler skeleton)...")
try:
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    for _ in range(10): app.update()

    biped_url = f"{S3}/Isaac/People/Characters/biped_demo/biped_demo_meters.usd"
    bp = stage.DefinePrim("/World/Biped", "Xform")
    bp.GetReferences().AddReference(biped_url)
    for _ in range(60): app.update()

    # Find skeleton
    bskel = None
    bskelroot = None
    for prim in Usd.PrimRange(stage.GetPrimAtPath("/World/Biped")):
        if prim.IsA(UsdSkel.Skeleton) and bskel is None:
            bskel = str(prim.GetPath())
        if prim.IsA(UsdSkel.Root) and bskelroot is None:
            bskelroot = str(prim.GetPath())
    log(f"  Biped skeleton: {bskel}")
    log(f"  Biped skelroot: {bskelroot}")

    # Bind idle animation
    target = bskelroot or bskel
    if target:
        # Clear any animGraph first
        tp = stage.GetPrimAtPath(target)
        ag = tp.GetRelationship("animationGraph")
        if ag and ag.IsValid():
            ag.ClearTargets(True)

        aprim = stage.DefinePrim("/World/BipedAnim")
        aprim.GetReferences().AddReference(ANIMS["idle"])
        for _ in range(20): app.update()

        binding = UsdSkel.BindingAPI.Apply(tp)
        binding.CreateAnimationSourceRel().SetTargets([Sdf.Path("/World/BipedAnim")])
        log(f"  Bound idle to biped")

        # Timeline
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(60): app.update()
        timeline.pause()

        # Quick render
        camera = rep.create.camera(position=(2, 1.5, 2), look_at=(0, 0.8, 0))
        rep.create.light(light_type="Dome", intensity=2000)
        rp = rep.create.render_product(camera, (1280, 720))
        writer = rep.WriterRegistry.get("BasicWriter")
        writer.initialize(output_dir="/workspace/output_v4b_biped", rgb=True)
        writer.attach([rp])
        rep.orchestrator.run()
        for _ in range(60): app.update()

        bd = "/workspace/output_v4b_biped"
        brgbs = [f for f in os.listdir(bd) if f.startswith("rgb_")] if os.path.exists(bd) else []
        if brgbs:
            bsz = os.path.getsize(os.path.join(bd, brgbs[0])) / 1024
            log(f"  Biped render: {bsz:.1f} KB")
            results["biped_render_kb"] = round(bsz, 1)
except Exception as e:
    log(f"  Biped test error: {e}")

# SUMMARY
log(f"\n{'='*50}")
log("[v4b] SUMMARY")
log(f"  Animation binding approaches tested")
for t in results["tests"]:
    for a in t.get("approaches", []):
        log(f"    {a['target']}: {'OK' if a['ok'] else 'FAIL'}")
log(f"  Render size: {results.get('render_kb', 'N/A')} KB")
log(f"  Biped render: {results.get('biped_render_kb', 'N/A')} KB")
log(f"{'='*50}")

with open("/workspace/tpose_fix_results.json", "w") as f:
    json.dump(results, f, indent=2)
out.close()
simulation_app.close()
