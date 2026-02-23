from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import omni.replicator.core as rep

with rep.new_layer():
    light = rep.create.light(light_type="Sphere", temperature=6500, intensity=35000, position=(0,500,0), scale=100)
    plane = rep.create.plane(scale=10, semantics=[("class","road")])
    cube = rep.create.cube(position=(0,50,0), semantics=[("class","vehicle")])
    sphere = rep.create.sphere(position=(100,50,0), semantics=[("class","pedestrian")])
    camera = rep.create.camera(position=(300,300,300), look_at=(0,0,0))
    rp = rep.create.render_product(camera, (1024,1024))
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir="/workspace/output", rgb=True, bounding_box_2d_tight=True)
    writer.attach([rp])
    with rep.trigger.on_frame(num_frames=10):
        with cube:
            rep.modify.pose(position=rep.distribution.uniform((-200,0,-200),(200,100,200)))
        with sphere:
            rep.modify.pose(position=rep.distribution.uniform((-200,0,-200),(200,100,200)))
rep.orchestrator.run_until_complete()

simulation_app.close()
