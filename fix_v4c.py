from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "extra_extensions": ["omni.anim.graph.core","omni.anim.graph.schema","omni.anim.people","omni.anim.skelJoint","omni.anim.retarget.core","omni.anim.navigation.core"]})
import omni.kit.app, omni.usd, omni.timeline, omni.replicator.core as rep, os
from pxr import Usd, UsdGeom, UsdSkel, Sdf, Gf
a = omni.kit.app.get_app()
S3 = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
out = open("/workspace/v4c_log.txt","w")
def log(m):
    print(m); out.write(m+"\n"); out.flush()
for _ in range(30): a.update()
log("[v4c] Loading scene...")
omni.usd.get_context().new_stage()
stage = omni.usd.get_context().get_stage()
for _ in range(10): a.update()
stage.DefinePrim("/World/Warehouse").GetReferences().AddReference(f"{S3}/Isaac/Environments/Simple_Warehouse/warehouse.usd")
stage.DefinePrim("/World/Person1").GetReferences().AddReference(f"{S3}/Isaac/People/Characters/male_adult_construction_03/male_adult_construction_03.usd")
UsdGeom.Xformable(stage.GetPrimAtPath("/World/Person1")).AddTranslateOp().Set(Gf.Vec3d(0,0,0))
stage.DefinePrim("/World/AnimationGraph")
for _ in range(60): a.update()
skelroot = None
for p in Usd.PrimRange(stage.GetPrimAtPath("/World/Person1")):
    if p.IsA(UsdSkel.Root) and not skelroot: skelroot = str(p.GetPath())
log(f"SkelRoot: {skelroot}")
aprim = stage.DefinePrim("/World/IdleAnim")
aprim.GetReferences().AddReference(f"{S3}/Isaac/People/Animations/stand_idle_loop.skelanim.usd")
for _ in range(20): a.update()
if skelroot:
    tp = stage.GetPrimAtPath(skelroot)
    ag = tp.GetRelationship("animationGraph")
    if ag and ag.IsValid(): ag.ClearTargets(True); log("Cleared animGraph")
    UsdSkel.BindingAPI.Apply(tp).CreateAnimationSourceRel().SetTargets([Sdf.Path("/World/IdleAnim")])
    log("Bound idle anim")
log("Playing timeline 300 frames...")
tl = omni.timeline.get_timeline_interface()
tl.set_current_time(0); tl.play()
for i in range(300):
    a.update()
    if i % 100 == 0: log(f"  Frame {i}")
tl.pause()
log("Rendering...")
rep.create.light(light_type="Dome", intensity=1500)
rep.create.light(light_type="Distant", intensity=3000, rotation=(-45,30,0))
cam = rep.create.camera(position=(3,1.8,3), look_at=(0,0.9,0))
rp = rep.create.render_product(cam, (1280,720))
w = rep.WriterRegistry.get("BasicWriter")
w.initialize(output_dir="/workspace/output_v4c", rgb=True)
w.attach([rp])
rep.orchestrator.run()
for _ in range(60): a.update()
d = "/workspace/output_v4c"
rgbs = [f for f in os.listdir(d) if f.startswith("rgb_")] if os.path.exists(d) else []
if rgbs:
    sz = os.path.getsize(os.path.join(d,rgbs[0]))/1024
    log(f"Render: {len(rgbs)} imgs, {sz:.1f} KB")
    os.system(f"cp {d}/rgb_0000.png /workspace/praqtor-data-scripts/v4c_result.png")
out.close()
app.close()
