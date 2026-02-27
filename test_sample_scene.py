from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
import omni.kit.app, omni.usd, omni.timeline, omni.replicator.core as rep, os
a = omni.kit.app.get_app()
S3 = "http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2"
out = open("/workspace/sample_test.txt","w")
def log(m):
    print(m); out.write(m+"\n"); out.flush()
log("Loading pre-built PeopleDemo scene...")
omni.usd.get_context().open_stage(f"{S3}/Isaac/Samples/PeopleDemo/SimpleEventSimulation/simple_event_simulation.usd")
for _ in range(120): a.update()
log("Scene loaded. Playing timeline...")
tl = omni.timeline.get_timeline_interface()
tl.play()
for i in range(300):
    a.update()
    if i % 100 == 0: log(f"  Frame {i}")
log("Rendering...")
cam = rep.create.camera(position=(5,2,5), look_at=(0,1,0))
rp = rep.create.render_product(cam, (1280,720))
w = rep.WriterRegistry.get("BasicWriter")
w.initialize(output_dir="/workspace/sample_out", rgb=True)
w.attach([rp])
rep.orchestrator.run()
for _ in range(60): a.update()
d = "/workspace/sample_out"
if os.path.exists(d):
    rgbs = [f for f in os.listdir(d) if f.startswith("rgb_")]
    if rgbs:
        sz = os.path.getsize(os.path.join(d,rgbs[0]))/1024
        log(f"Render: {sz:.1f} KB")
        os.system(f"cp {d}/rgb_0000.png /workspace/praqtor-data-scripts/sample_preview.png")
log("Done")
out.close()
app.close()
