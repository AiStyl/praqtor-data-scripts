"""
PRAQTOR DATΔ — Black Image Diagnostic (v8)
==========================================
Isaac Sim 4.2.0 | Headless | RTX 4090 | RunPod
Run: /isaac-sim/python.sh test_replicator.py

Runs 4 tests to isolate root cause of black images:
  Test 1: Pure Replicator primitives (no USD environment) - baseline
  Test 2: open_stage() + rep.create.camera() with look_at
  Test 3: open_stage() + USD API camera (no look_at)
  Test 4: rep.create.from_usd() inside rep.new_layer() (old broken approach)
"""

from isaacsim import SimulationApp

simulation_app = SimulationApp({
    "headless": True,
    "renderer": "RayTracedLighting",
    "width": 1024,
    "height": 1024,
})

import os
import numpy as np
import omni.usd
import omni.replicator.core as rep
import carb
from pxr import UsdGeom, UsdLux, Gf, Sdf

WAREHOUSE_USD = "/workspace/nvidia_assets/Assets/ArchVis/Industrial/Stages/IsaacWarehouse.usd"

def warm_up(n=25, label=""):
    print(f"  Warm-up {n} frames {label}...")
    for _ in range(n):
        simulation_app.update()

def reset_stage():
    omni.usd.get_context().new_stage()
    warm_up(10, "reset")

def analyze(output_dir, test_name):
    from PIL import Image
    rgb_dir = os.path.join(output_dir, "rgb")
    if not os.path.exists(rgb_dir):
        # BasicWriter may write directly without rgb/ subfolder
        rgb_dir = output_dir
    found = False
    for fname in sorted(os.listdir(rgb_dir)):
        if fname.endswith(".png") and "rgb" in fname:
            img = np.array(Image.open(os.path.join(rgb_dir, fname)))
            r = img[:,:,0].mean()
            g = img[:,:,1].mean()
            b = img[:,:,2].mean()
            a = img[:,:,3].mean() if img.shape[2] == 4 else 255
            status = "BLACK" if (r==0 and g==0 and b==0) else "VISIBLE"
            print(f"  [{test_name}] {fname}: R={r:.1f} G={g:.1f} B={b:.1f} A={a:.1f} -> {status}")
            found = True
            return status == "VISIBLE"
    if not found:
        print(f"  [{test_name}] No rgb PNG files found in {rgb_dir}")
    return False

# Install Pillow
try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call(["/isaac-sim/python.sh", "-m", "pip", "install", "Pillow", "-q"])
    from PIL import Image

print("\n[PRAQTOR DATΔ] Initial warm-up...")
warm_up(20, "renderer init")

# ============================================================
# TEST 1: Pure Replicator primitives — baseline
# ============================================================
print("\n" + "="*60)
print("TEST 1: Pure Replicator primitives (baseline)")
print("="*60)
reset_stage()
os.makedirs("/workspace/output_test1", exist_ok=True)

with rep.new_layer():
    rep.create.light(light_type="Dome", rotation=(270,0,0), intensity=2000)
    rep.create.light(light_type="Distant", rotation=(-45,30,0), intensity=3000)
    plane = rep.create.plane(scale=10, position=(0,0,0))
    cube = rep.create.cube(position=(0,0,50), scale=1)
    sphere = rep.create.sphere(position=(100,0,30), scale=0.5)
    cam = rep.create.camera(position=(250,250,200), look_at=(0,0,25), focal_length=24)
    rp = rep.create.render_product(cam, (1024,1024))
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir="/workspace/output_test1", rgb=True)
    writer.attach([rp])
    rep.trigger.on_frame(max_execs=3)

warm_up(30, "test1 settle")
rep.orchestrator.run_until_complete()
test1 = analyze("/workspace/output_test1", "TEST 1")

# ============================================================
# TEST 2: open_stage() + rep.create.camera() with look_at
# ============================================================
print("\n" + "="*60)
print("TEST 2: open_stage() + rep.create.camera(look_at=...)")
print("="*60)
os.makedirs("/workspace/output_test2", exist_ok=True)

print(f"  Loading: {WAREHOUSE_USD}")
omni.usd.get_context().open_stage(WAREHOUSE_USD)
warm_up(50, "stage load")

with rep.new_layer():
    rep.create.light(light_type="Dome", rotation=(270,0,0), intensity=2000)
    rep.create.light(light_type="Distant", rotation=(-45,30,0), intensity=3000)
    cam2 = rep.create.camera(position=(8,-6,4), look_at=(0,1,0), focal_length=24)
    rp2 = rep.create.render_product(cam2, (1024,1024))
    writer2 = rep.WriterRegistry.get("BasicWriter")
    writer2.initialize(output_dir="/workspace/output_test2", rgb=True)
    writer2.attach([rp2])
    rep.trigger.on_frame(max_execs=3)

warm_up(30, "test2 settle")
rep.orchestrator.run_until_complete()
test2 = analyze("/workspace/output_test2", "TEST 2")

# ============================================================
# TEST 3: open_stage() + USD API camera (no look_at)
# ============================================================
print("\n" + "="*60)
print("TEST 3: open_stage() + USD API camera (no rep.create.camera)")
print("="*60)
os.makedirs("/workspace/output_test3", exist_ok=True)

omni.usd.get_context().open_stage(WAREHOUSE_USD)
warm_up(50, "stage load")

stage = omni.usd.get_context().get_stage()

dome = stage.DefinePrim("/World/DiagDome", "DomeLight")
dome.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(2000.0)

sun = stage.DefinePrim("/World/DiagSun", "DistantLight")
sun.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(3000.0)
sun.CreateAttribute("inputs:angle", Sdf.ValueTypeNames.Float).Set(1.0)
UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-45, 30, 0))

cam3_prim = stage.DefinePrim("/World/DiagCamera", "Camera")
cam3_xform = UsdGeom.Xformable(cam3_prim)
cam3_xform.AddTranslateOp().Set(Gf.Vec3d(8.0, -6.0, 4.0))
cam3_xform.AddRotateXYZOp().Set(Gf.Vec3f(-21, 0, -49))
cam3_prim.CreateAttribute("focalLength", Sdf.ValueTypeNames.Float).Set(24.0)
cam3_prim.CreateAttribute("clippingRange", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(0.1, 10000.0))

warm_up(10, "USD prims")

with rep.new_layer():
    rp3 = rep.create.render_product("/World/DiagCamera", (1024,1024))
    writer3 = rep.WriterRegistry.get("BasicWriter")
    writer3.initialize(output_dir="/workspace/output_test3", rgb=True)
    writer3.attach([rp3])
    rep.trigger.on_frame(max_execs=3)

warm_up(30, "test3 settle")
rep.orchestrator.run_until_complete()
test3 = analyze("/workspace/output_test3", "TEST 3")

# ============================================================
# TEST 4: rep.create.from_usd() in rep.new_layer() — old approach
# ============================================================
print("\n" + "="*60)
print("TEST 4: rep.create.from_usd() inside rep.new_layer() (old approach)")
print("="*60)
os.makedirs("/workspace/output_test4", exist_ok=True)
reset_stage()

with rep.new_layer():
    rep.create.from_usd(WAREHOUSE_USD)
    rep.create.light(light_type="Dome", rotation=(270,0,0), intensity=3000)
    rep.create.light(light_type="Distant", rotation=(-45,30,0), intensity=5000)
    cam4 = rep.create.camera(position=(8,-6,4), look_at=(0,1,0), focal_length=24)
    rp4 = rep.create.render_product(cam4, (1024,1024))
    writer4 = rep.WriterRegistry.get("BasicWriter")
    writer4.initialize(output_dir="/workspace/output_test4", rgb=True)
    writer4.attach([rp4])
    rep.trigger.on_frame(max_execs=3)

warm_up(50, "test4 settle")
rep.orchestrator.run_until_complete()
test4 = analyze("/workspace/output_test4", "TEST 4")

# ============================================================
# VERDICT
# ============================================================
print("\n" + "="*60)
print("DIAGNOSTIC VERDICT")
print("="*60)
print(f"  Test 1 (pure primitives):          {'VISIBLE' if test1 else 'BLACK'}")
print(f"  Test 2 (open_stage + rep camera):  {'VISIBLE' if test2 else 'BLACK'}")
print(f"  Test 3 (open_stage + USD camera):  {'VISIBLE' if test3 else 'BLACK'}")
print(f"  Test 4 (from_usd in new_layer):    {'VISIBLE' if test4 else 'BLACK'}")

if not test1:
    print("\nDIAGNOSIS: Renderer itself is broken - GPU/driver issue")
elif test1 and (test2 or test3) and not test4:
    print("\nDIAGNOSIS: rep.create.from_usd() for environments is the problem")
    print("FIX: Use open_stage() to load the warehouse")
elif test1 and not test2 and test3:
    print("\nDIAGNOSIS: rep.create.camera(look_at=) is broken - use USD API camera")
elif test1 and not any([test2, test3, test4]):
    print("\nDIAGNOSIS: IsaacWarehouse.usd itself has issues in headless mode")

simulation_app.close()
print("\n[PRAQTOR DATΔ] Diagnostic complete.")
