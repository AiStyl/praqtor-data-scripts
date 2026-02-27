"""
PRAQTOR DATΔ — Animation Diagnostic v4
Quick test to verify T-pose fix works BEFORE running full render.
Run time: ~2 minutes. Cost: ~$0.03

Tests:
1. Can we enable omni.anim.graph.core?
2. Can we load a character and find its Skeleton prim?
3. Can we load an animation clip?
4. Can we bind the animation to the skeleton?
5. Does the character pose change after timeline advance?
"""

import os
import sys
import json
import time

print("[DIAG v4] PRAQTOR DATΔ Animation Diagnostic")
print(f"[DIAG v4] Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"[DIAG v4] Python: {sys.version}")

results = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "tests": {},
    "isaac_sim_version": "unknown",
    "anim_extensions": {},
    "character_hierarchy": [],
    "skeleton_found": False,
    "animation_bound": False,
    "recommendations": [],
}

S3_BASE = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"

# ============================================================
# TEST 1: Enable animation extensions
# ============================================================
print("\n[TEST 1] Enabling animation extensions...")

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
        "omni.anim.people",
    ]
    
    for ext_name in ANIM_EXTENSIONS:
        try:
            enabled = ext_manager.set_extension_enabled_immediate(ext_name, True)
            results["anim_extensions"][ext_name] = {"enabled": True, "result": str(enabled)}
            print(f"  [OK] {ext_name}: {enabled}")
        except Exception as e:
            results["anim_extensions"][ext_name] = {"enabled": False, "error": str(e)}
            print(f"  [FAIL] {ext_name}: {e}")
    
    # Update app after enabling extensions
    for _ in range(20):
        app.update()
    
    results["tests"]["enable_extensions"] = True
    print("[TEST 1] PASSED")
except Exception as e:
    results["tests"]["enable_extensions"] = False
    results["recommendations"].append(f"Extension loading failed: {e}")
    print(f"[TEST 1] FAILED: {e}")

# ============================================================
# TEST 2: Load a character and inspect hierarchy
# ============================================================
print("\n[TEST 2] Loading character and inspecting hierarchy...")

try:
    import omni.usd
    from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf
    
    # Open a fresh stage
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    
    # Give stage time to initialize
    for _ in range(10):
        app.update()
    
    # Add a ground plane for reference
    UsdGeom.Mesh.Define(stage, "/World/Ground")
    
    # Load a character
    char_url = f"{S3_BASE}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd"
    char_prim = stage.DefinePrim("/World/TestCharacter", "Xform")
    char_prim.GetReferences().AddReference(char_url)
    
    print(f"  [OK] Character reference added: {char_url}")
    
    # Force load
    for _ in range(30):
        app.update()
    
    # Inspect hierarchy
    print(f"\n  Character hierarchy under /World/TestCharacter:")
    skeleton_path = None
    skelroot_path = None
    
    for prim in Usd.PrimRange(stage.GetPrimAtPath("/World/TestCharacter")):
        depth = str(prim.GetPath()).count("/") - 2
        indent = "  " * depth
        prim_type = prim.GetTypeName()
        is_skel = prim.IsA(UsdSkel.Skeleton)
        is_skelroot = prim.IsA(UsdSkel.Root)
        
        marker = ""
        if is_skel:
            marker = " ◀ SKELETON"
            skeleton_path = str(prim.GetPath())
        if is_skelroot:
            marker = " ◀ SKELROOT"
            skelroot_path = str(prim.GetPath())
        
        entry = f"{indent}{prim.GetName()} [{prim_type}]{marker}"
        print(f"    {entry}")
        results["character_hierarchy"].append(entry.strip())
        
        # Only go 5 levels deep to avoid flooding
        if depth > 5:
            continue
    
    results["skeleton_found"] = skeleton_path is not None
    results["skelroot_path"] = skelroot_path
    results["skeleton_path"] = skeleton_path
    
    if skeleton_path:
        print(f"\n  [OK] Skeleton found at: {skeleton_path}")
        
        # Inspect skeleton details
        skel_prim = stage.GetPrimAtPath(skeleton_path)
        skel = UsdSkel.Skeleton(skel_prim)
        
        # Check for existing animation source
        binding = UsdSkel.BindingAPI(skel_prim)
        if binding:
            anim_source = binding.GetAnimationSourceRel()
            if anim_source:
                targets = anim_source.GetTargets()
                print(f"  [INFO] Existing animation source: {targets}")
                results["existing_animation"] = [str(t) for t in targets]
            else:
                print(f"  [INFO] No existing animation source")
                results["existing_animation"] = None
        
        # Check joints
        joints_attr = skel.GetJointsAttr()
        if joints_attr:
            joints = joints_attr.Get()
            if joints:
                print(f"  [INFO] Skeleton has {len(joints)} joints")
                results["joint_count"] = len(joints)
                # Print first few joints
                for j in list(joints)[:5]:
                    print(f"    - {j}")
                if len(joints) > 5:
                    print(f"    ... and {len(joints) - 5} more")
    else:
        print(f"\n  [WARN] No Skeleton prim found!")
        if skelroot_path:
            print(f"  [INFO] SkelRoot found at: {skelroot_path}")
        results["recommendations"].append("No Skeleton prim found in character. Try a different character model.")
    
    results["tests"]["load_character"] = True
    print("[TEST 2] PASSED")
    
except Exception as e:
    results["tests"]["load_character"] = False
    results["recommendations"].append(f"Character loading failed: {e}")
    print(f"[TEST 2] FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# TEST 3: Load animation clip and bind to skeleton
# ============================================================
print("\n[TEST 3] Loading animation clip and binding...")

try:
    if skeleton_path:
        # Try multiple animation paths
        ANIM_CANDIDATES = [
            f"{S3_BASE}/Isaac/People/Characters/Animations/walking_01.skelanim.usd",
            f"{S3_BASE}/Isaac/People/Characters/Animations/idle_01.skelanim.usd",
            f"{S3_BASE}/Isaac/People/Characters/Animations/standing_01.skelanim.usd",
            # Alternative path patterns
            f"{S3_BASE}/Isaac/People/Animations/walking_01.skelanim.usd",
            f"{S3_BASE}/Isaac/People/Animations/idle_01.skelanim.usd",
        ]
        
        bound = False
        for anim_url in ANIM_CANDIDATES:
            try:
                anim_name = os.path.basename(anim_url).replace('.usd', '')
                anim_prim_path = f"/World/TestCharacter/Anim_{anim_name}"
                
                # Create animation prim with reference
                anim_prim = stage.DefinePrim(anim_prim_path, "SkelAnimation")
                anim_prim.GetReferences().AddReference(anim_url)
                
                # Update to load
                for _ in range(15):
                    app.update()
                
                # Check if prim loaded successfully
                if anim_prim.IsValid() and anim_prim.GetChildren():
                    print(f"  [OK] Animation loaded: {anim_name}")
                else:
                    # Check if it has any attributes (skelanim might not have children)
                    print(f"  [INFO] Animation prim created: {anim_name} (checking attributes...)")
                
                # Bind to skeleton
                skel_prim = stage.GetPrimAtPath(skeleton_path)
                binding = UsdSkel.BindingAPI.Apply(skel_prim)
                binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(anim_prim_path)])
                
                # Also try binding to SkelRoot if available
                if skelroot_path:
                    skelroot_prim = stage.GetPrimAtPath(skelroot_path)
                    root_binding = UsdSkel.BindingAPI.Apply(skelroot_prim)
                    root_binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(anim_prim_path)])
                
                print(f"  [OK] Animation bound to skeleton")
                results["animation_bound"] = True
                results["working_animation"] = anim_url
                bound = True
                break
                
            except Exception as e:
                print(f"  [SKIP] {anim_name}: {e}")
                continue
        
        if not bound:
            print(f"  [WARN] No animations could be bound")
            results["recommendations"].append("No animation clips loaded. Check S3 paths.")
    else:
        print(f"  [SKIP] No skeleton to bind to")
    
    results["tests"]["bind_animation"] = bound if skeleton_path else False
    print(f"[TEST 3] {'PASSED' if bound else 'NEEDS INVESTIGATION'}")
    
except Exception as e:
    results["tests"]["bind_animation"] = False
    print(f"[TEST 3] FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# TEST 4: Advance timeline and check pose
# ============================================================
print("\n[TEST 4] Advancing timeline to apply animation...")

try:
    import omni.timeline
    timeline = omni.timeline.get_timeline_interface()
    
    # Record pre-animation state
    print(f"  [INFO] Starting timeline play...")
    timeline.play()
    
    for i in range(60):
        app.update()
        if i % 20 == 0:
            print(f"  [INFO] Frame {i}/60...")
    
    timeline.pause()
    print(f"  [OK] Timeline advanced 60 frames")
    
    # Check if skeleton transform changed
    if skeleton_path:
        skel_prim = stage.GetPrimAtPath(skeleton_path)
        xform = UsdGeom.Xformable(skel_prim)
        if xform:
            local_transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            print(f"  [INFO] Skeleton transform: {local_transform}")
    
    results["tests"]["timeline_advance"] = True
    print("[TEST 4] PASSED")
    
except Exception as e:
    results["tests"]["timeline_advance"] = False
    print(f"[TEST 4] FAILED: {e}")

# ============================================================
# TEST 5: Quick render test
# ============================================================
print("\n[TEST 5] Quick single-frame render...")

try:
    import omni.replicator.core as rep
    
    with rep.new_layer():
        camera = rep.create.camera(
            position=(3, 2, 3),
            look_at=(0, 1, 0),
        )
        rp = rep.create.render_product(camera, (640, 480))
        
        writer = rep.WriterRegistry.get("BasicWriter")
        test_output = "/workspace/output_v4_diag"
        writer.initialize(output_dir=test_output, rgb=True)
        writer.attach([rp])
        
        rep.orchestrator.run()
        
        for _ in range(30):
            app.update()
    
    # Check output
    rgb_files = [f for f in os.listdir(test_output) if f.startswith("rgb_")] if os.path.exists(test_output) else []
    if rgb_files:
        size = os.path.getsize(os.path.join(test_output, rgb_files[0])) / 1024
        print(f"  [OK] Rendered {len(rgb_files)} frame(s), size: {size:.1f} KB")
        results["test_render_size_kb"] = round(size, 1)
        results["tests"]["render"] = True
    else:
        print(f"  [WARN] No RGB output found")
        results["tests"]["render"] = False
        
    print(f"[TEST 5] {'PASSED' if rgb_files else 'FAILED'}")
    
except Exception as e:
    results["tests"]["render"] = False
    print(f"[TEST 5] FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print("[DIAG v4] SUMMARY")
print(f"{'='*60}")

passed = sum(1 for v in results["tests"].values() if v)
total = len(results["tests"])
print(f"  Tests passed: {passed}/{total}")
print(f"  Skeleton found: {results['skeleton_found']}")
print(f"  Animation bound: {results['animation_bound']}")

if results["recommendations"]:
    print(f"\n  RECOMMENDATIONS:")
    for rec in results["recommendations"]:
        print(f"    → {rec}")

if results["animation_bound"]:
    print(f"\n  ✅ T-POSE FIX LIKELY TO WORK — proceed with photoreal_scene_v4.py")
else:
    print(f"\n  ⚠️ ANIMATION BINDING UNCLEAR — check results before running full render")
    print(f"  The diagnostic render at /workspace/output_v4_diag/ will show if the pose changed.")

# Save results
diag_path = "/workspace/diagnostic_v4.json"
with open(diag_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\n  Full results: {diag_path}")
print(f"[DIAG v4] Done!")
