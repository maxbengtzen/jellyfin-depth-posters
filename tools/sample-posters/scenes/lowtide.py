"""Low Tide: a lantern on a pier at night, island with pines and a moon behind fog.

The first of the scenes; it predates common.py and keeps its own helpers.
blender -b --python lowtide.py -- <assets> <out.png> <width> <samples>
"""
import bpy, sys, os, math, random, mathutils

args = sys.argv[sys.argv.index('--') + 1:]
A, OUT, W, SAMPLES = args[0], args[1], int(args[2]), int(args[3])
H = W * 3 // 2

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def imp(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(A, name, f'{name}.gltf'))
    objs = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name + '_root', None)
    sc.collection.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root
    return root, [o for o in objs if o.type == 'MESH']


def bbox(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs for c in o.bound_box]
    return ([min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)])


def place(name, loc, rot=0, scale=1.0):
    r, objs = imp(name)
    r.location = loc
    r.rotation_euler[2] = math.radians(rot)
    r.scale = (scale,) * 3
    return r, objs


# --- world: night sky HDRI, dimmed and tinted ------------------------------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
nt = world.node_tree; nt.nodes.clear()
env = nt.nodes.new('ShaderNodeTexEnvironment')
env.image = bpy.data.images.load(os.path.join(A, 'kloppenheim_07_puresky', 'kloppenheim_07_puresky.hdr'))
mapn = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
mapn.inputs['Rotation'].default_value[2] = math.radians(200)
nt.links.new(tc.outputs['Generated'], mapn.inputs['Vector']); nt.links.new(mapn.outputs[0], env.inputs[0])
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.22
out = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(env.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])

# --- water -----------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, 0))
water = bpy.context.object
m = bpy.data.materials.new('water'); m.use_nodes = True; water.data.materials.append(m)
n = m.node_tree.nodes; l = m.node_tree.links
p = n['Principled BSDF']
p.inputs['Base Color'].default_value = (0.004, 0.008, 0.015, 1)
p.inputs['Roughness'].default_value = 0.06
noise = n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 0.9; noise.inputs['Detail'].default_value = 8
wc = n.new('ShaderNodeTexCoord'); mp = n.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 3.5, 1)
l.new(wc.outputs['Object'], mp.inputs[0]); l.new(mp.outputs[0], noise.inputs[0])
bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25
l.new(noise.outputs['Fac'], bump.inputs['Height']); l.new(bump.outputs[0], p.inputs['Normal'])

# --- pier, three sections end to end ----------------------------------------
pier = []
for k in range(3):
    r, objs = place('modular_wooden_pier', (0, k * 19.0, 0))
    pier += objs
(pmn, pmx) = bbox(pier)
deck = max(o for o in [bbox([ob])[1][2] for ob in pier if 'plank' in ob.name.lower()] or [1.0])


def surface(x, y, top=30.0):
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = sc.ray_cast(dg, mathutils.Vector((x, y, top)), mathutils.Vector((0, 0, -1)))
    return loc.z if hit else None


# --- island: a rocky stack with pines, far away ---------------------------------
place('coastal_cliff_02', (6, 135, -2.5), rot=6, scale=1.8)
place('coast_rocks_02', (-10, 118, -0.5), rot=10, scale=1.6)
place('coastal_cliff_01', (-120, 330, -3), rot=-12, scale=2.6)
place('coastal_cliff_01', (140, 380, -3), rot=20, scale=2.4)
place('coast_rocks_01', (-26, 58, -0.7), rot=40, scale=0.6)
place('coast_rocks_02', (26, 80, -0.9), rot=-30, scale=0.7)
# pines: instance the three trees along the top of the stack
_, pines = place('pine_tree_01', (0, -3000, 0))
random.seed(7)
spots = [(x, 135 + random.uniform(-4, 4)) for x in range(-28, 38, 4)]
for i, (x, y) in enumerate(spots):
    z = surface(x, y, top=80)
    if z is None or z < 4:
        continue
    src = pines[i % len(pines)]
    cs = [mathutils.Vector(c) for c in src.bound_box]
    cx, cy, mz = sum(c.x for c in cs) / 8, sum(c.y for c in cs) / 8, min(c.z for c in cs)
    ob = bpy.data.objects.new(f'pine{i}', src.data); sc.collection.objects.link(ob)
    # glTF meshes keep the importer's axis rotation on the object; reuse it
    rot_axes = src.matrix_world.to_3x3().normalized().to_4x4()
    ob.matrix_world = (mathutils.Matrix.Translation((x, y, z - 0.3)) @ mathutils.Matrix.Rotation(random.uniform(0, 6.28), 4, 'Z')
                       @ mathutils.Matrix.Scale(random.uniform(0.7, 1.05), 4) @ rot_axes @ mathutils.Matrix.Translation((-cx, -cy, -mz)))
for o in pines:
    o.hide_render = True

# --- moon --------------------------------------------------------------------
bpy.ops.mesh.primitive_uv_sphere_add(radius=22, location=(-18, 420, 95), segments=64, ring_count=32)
moon = bpy.context.object
mm = bpy.data.materials.new('moon'); mm.use_nodes = True; moon.data.materials.append(mm)
mn_ = mm.node_tree.nodes; ml = mm.node_tree.links; mn_.clear()
em = mn_.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 6
mnz = mn_.new('ShaderNodeTexNoise'); mnz.inputs['Scale'].default_value = 3; mnz.inputs['Detail'].default_value = 6
ramp = mn_.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.75, 0.78, 0.82, 1); ramp.color_ramp.elements[1].color = (1, 0.98, 0.93, 1)
ml.new(mnz.outputs['Fac'], ramp.inputs[0]); ml.new(ramp.outputs[0], em.inputs['Color'])
mo = mn_.new('ShaderNodeOutputMaterial'); ml.new(em.outputs[0], mo.inputs[0])
moon.visible_shadow = False

# moonlight: back light from the moon direction
bpy.ops.object.light_add(type='SUN', location=(0, 0, 50))
sun = bpy.context.object; sun.data.energy = 0.6; sun.data.color = (0.65, 0.75, 1.0); sun.data.angle = math.radians(1)
sun.rotation_euler = (math.radians(-75), 0, math.radians(180 - 3))

# --- lantern, foreground -----------------------------------------------------
lx, ly = -0.52, -2.2
lz = surface(lx, ly)
lan, lobjs = place('Lantern_01', (lx, ly, lz), rot=25, scale=2.2)
for o in lobjs:
    if 'glass' in o.name.lower():
        for slot in o.material_slots:
            gm = slot.material
            if gm and gm.use_nodes:
                pb = gm.node_tree.nodes.get('Principled BSDF')
                if pb:
                    pb.inputs['Emission Color'].default_value = (1.0, 0.42, 0.1, 1)
                    pb.inputs['Emission Strength'].default_value = 7
bpy.ops.object.light_add(type='POINT', location=(lx, ly, deck + 0.3))
pl = bpy.context.object; pl.location.z = lz + 0.32; pl.data.energy = 140; pl.data.color = (1.0, 0.55, 0.22); pl.data.shadow_soft_size = 0.04

# --- camera ------------------------------------------------------------------
bpy.ops.object.camera_add(location=(0.25, -5.2, deck + 1.25))
cam = bpy.context.object; sc.camera = cam
cam.data.lens = 26; cam.data.sensor_fit = 'VERTICAL'
target = mathutils.Vector((0.0, 60.0, deck + 2.2))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 30; cam.data.dof.aperture_fstop = 8
cam.data.clip_end = 2000

# --- render + mist-based fog in the compositor --------------------------------
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.view_settings.exposure = 0.6
vl = sc.view_layers[0]; vl.use_pass_mist = True
world.mist_settings.start = 12; world.mist_settings.depth = 210; world.mist_settings.falloff = 'QUADRATIC'
sc.use_nodes = True
ct = sc.node_tree; ct.nodes.clear()
rl = ct.nodes.new('CompositorNodeRLayers')
fog = ct.nodes.new('CompositorNodeMixRGB'); fog.inputs[2].default_value = (0.035, 0.06, 0.11, 1)
mist_curve = ct.nodes.new('CompositorNodeMath'); mist_curve.operation = 'MULTIPLY'; mist_curve.inputs[1].default_value = 0.75
ct.links.new(rl.outputs['Mist'], mist_curve.inputs[0]); ct.links.new(mist_curve.outputs[0], fog.inputs[0])
ct.links.new(rl.outputs['Image'], fog.inputs[1])
glare = ct.nodes.new('CompositorNodeGlare'); glare.glare_type = 'FOG_GLOW'; glare.quality = 'HIGH'; glare.threshold = 0.8; glare.size = 8
ct.links.new(fog.outputs[0], glare.inputs[0])
co = ct.nodes.new('CompositorNodeComposite'); ct.links.new(glare.outputs[0], co.inputs[0])

sc.render.filepath = OUT
sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print('DONE', OUT)
