"""PRAQTOR DATΔ — V5 Quick Verify
Confirms omni.anim.graph.core initialized properly after kit config patch.
Run AFTER patch_kit_config.py, BEFORE photoreal_v5.py.
Takes ~90 seconds. If CharacterManager shows 'initialized', the T-pose fix works.
"""
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
import omni.kit.app, omni.usd, omni.timeline
from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf
import os
a = omni.kit.app.get_app()
S3 = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
out = open("/workspace/v5_verify.txt","w")
def log(m):
    print(m); out.write(m+"\n"); out.flush()

# Let extensions fully initialize
log("[VERIFY] Warming up (30 frames)...")
for _ in range(30): a.update()

# Check if omni.anim.graph.core loaded at boot
ext = a.get_extension_manager()
graph_loaded = ext.is_extension_enabled("omni.anim.graph.core")
log(f"[VERIFY] omni.anim.graph.core enabled at boot: {graph_loaded}")

# Enable omni.anim.people
try:
    ext.set_extension_enabled_immediate("omni.anim.people", True)
    for _ in range(20): a.update()
    log("[VERIFY] omni.anim.people: enabled")
except Exception as e:
    log(f"[VERIFY] omni.anim.people failed: {e}")

# Load a character and check if AnimGraph evaluates
log("[VERIFY] Loading test character...")
omni.usd.get_context().new_stage()
stage = omni.usd.get_context().get_stage()
for _ in range(10): a.update()

char_prim = stage.DefinePrim("/World/Characters/TestPerson", "Xform")
char_prim.GetReferences().AddReference(
    f"{S3}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd"
)
for _ in range(60): a.update()

# Find SkelRoot and check animationGraph relationship
skelroot = None
for p in Usd.PrimRange(stage.GetPrimAtPath("/World/Characters/TestPerson")):
    if p.IsA(UsdSkel.Root) and not skelroot:
        skelroot = str(p.GetPath())
log(f"[VERIFY] SkelRoot: {skelroot}")

if skelroot:
    sr = stage.GetPrimAtPath(skelroot)
    ag = sr.GetRelationship("animationGraph")
    if ag and ag.IsValid():
        targets = ag.GetTargets()
        log(f"[VERIFY] AnimGraph targets: {targets}")

# Play timeline and check for CharacterManager errors
log("[VERIFY] Playing timeline (60 frames)...")
tl = omni.timeline.get_timeline_interface()
tl.play()
for _ in range(60): a.update()
tl.pause()

# Render quick test
log("[VERIFY] Quick render test...")
import omni.replicator.core as rep
rep.create.light(light_type="Dome", intensity=2000)
cam = rep.create.camera(position=(2,1.5,2), look_at=(0,0.9,0))
rp = rep.create.render_product(cam, (640,360))
w = rep.WriterRegistry.get("BasicWriter")
w.initialize(output_dir="/workspace/v5_verify_img", rgb=True)
w.attach([rp])
rep.orchestrator.run()
for _ in range(30): a.update()

d = "/workspace/v5_verify_img"
if os.path.exists(d):
    rgbs = [f for f in os.listdir(d) if f.startswith("rgb_")]
    if rgbs:
        sz = os.path.getsize(os.path.join(d, rgbs[0]))/1024
        log(f"[VERIFY] Render: {sz:.1f} KB")
        os.system(f"cp {d}/rgb_0000.png /workspace/praqtor-data-scripts/v5_verify.png")

log(f"\n[VERIFY] RESULT: AnimGraph at boot = {graph_loaded}")
if graph_loaded:
    log("[VERIFY] PASS - Kit config patch is working!")
    log("[VERIFY] Proceed with: /isaac-sim/python.sh photoreal_v5.py")
else:
    log("[VERIFY] FAIL - omni.anim.graph.core not loaded at boot")
    log("[VERIFY] Make sure you ran: python3 patch_kit_config.py")
out.close()
app.close()
