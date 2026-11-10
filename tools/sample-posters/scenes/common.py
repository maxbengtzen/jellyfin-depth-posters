"""Shared helpers for the poster scenes (Blender 4.5, run with -b --python)."""
import bpy, sys, os, math, random, mathutils

args = sys.argv[sys.argv.index('--') + 1:]
A, OUT, W, SAMPLES = args[0], args[1], int(args[2]), int(args[3])
H = W * 3 // 2

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
V = mathutils.Vector


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


def place(name, loc, rot=0, scale=1.0, tilt=(0, 0)):
    r, objs = imp(name)
    r.location = loc
    r.rotation_euler = (math.radians(tilt[0]), math.radians(tilt[1]), math.radians(rot))
    r.scale = (scale,) * 3 if not isinstance(scale, tuple) else scale
    # keep only the most detailed LOD
    for o in objs:
        if '_LOD' in o.name and not o.name.split('.')[0].endswith('LOD0'):
            o.hide_render = True
    return r, objs


def instances(name, spots, seed=1, scale=(0.8, 1.2), ground=None):
    """Scatter copies of every mesh in an asset. spots: (x, y[, z]) list."""
    _, src = imp(name)
    src = [o for o in src if not ('_LOD' in o.name and not o.name.split('.')[0].endswith('LOD0'))]
    rnd = random.Random(seed)
    for o in src:
        o.hide_render = True
    out = []
    for i, sp in enumerate(spots):
        x, y = sp[0], sp[1]
        z = sp[2] if len(sp) > 2 else (ground(x, y) if ground else 0)
        if z is None:
            continue
        s = src[i % len(src)]
        cs = [V(c) for c in s.bound_box]
        cx, cy, mz = sum(c.x for c in cs) / 8, sum(c.y for c in cs) / 8, min(c.z for c in cs)
        ob = bpy.data.objects.new(f'{name}_{i}', s.data); sc.collection.objects.link(ob)
        axes = s.matrix_world.to_3x3().normalized().to_4x4()
        k = rnd.uniform(*scale) if isinstance(scale, tuple) else scale
        ob.matrix_world = (mathutils.Matrix.Translation((x, y, z)) @ mathutils.Matrix.Rotation(rnd.uniform(0, 6.28), 4, 'Z')
                           @ mathutils.Matrix.Scale(k, 4) @ axes @ mathutils.Matrix.Translation((-cx, -cy, -mz)))
        out.append(ob)
    return out


def surface(x, y, top=200.0):
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = sc.ray_cast(dg, V((x, y, top)), V((0, 0, -1)))
    return loc.z if hit else None


def world_hdri(hdri, strength=1.0, rot=0.0, tint=None):
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(os.path.join(A, hdri, f'{hdri}.hdr'))
    mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
    mp.inputs['Rotation'].default_value[2] = math.radians(rot)
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], env.inputs[0])
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    col = env.outputs[0]
    if tint:
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1; mix.inputs[7].default_value = (*tint, 1)
        nt.links.new(col, mix.inputs[6]); col = mix.outputs[2]
    nt.links.new(col, bg.inputs[0])
    o = nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(bg.outputs[0], o.inputs[0])
    return w, nt, bg


def textured_ground(tex, size=600, tile=4.0, tint=(1, 1, 1), bump=0.6, rough=None, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc)
    g = bpy.context.object
    m = bpy.data.materials.new(tex); m.use_nodes = True; g.data.materials.append(m)
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n['Principled BSDF']
    tc = n.new('ShaderNodeTexCoord'); mp = n.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (size / tile,) * 3
    l.new(tc.outputs['UV'], mp.inputs[0])

    def img(f, non_color=False):
        t = n.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(os.path.join(A, tex, f))
        if non_color:
            t.image.colorspace_settings.name = 'Non-Color'
        l.new(mp.outputs[0], t.inputs[0]); return t
    d = img('Diffuse.jpg')
    mul = n.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1
    mul.inputs[7].default_value = (*tint, 1); l.new(d.outputs[0], mul.inputs[6]); l.new(mul.outputs[2], p.inputs['Base Color'])
    if rough is None:
        l.new(img('Rough.jpg', True).outputs[0], p.inputs['Roughness'])
    else:
        p.inputs['Roughness'].default_value = rough
    nm = n.new('ShaderNodeNormalMap'); l.new(img('nor_gl.jpg', True).outputs[0], nm.inputs['Color'])
    bp = n.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.05
    l.new(img('Displacement.jpg', True).outputs[0], bp.inputs['Height']); l.new(nm.outputs[0], bp.inputs['Normal'])
    l.new(bp.outputs[0], p.inputs['Normal'])
    return g


def terrain(size=800, height=6.0, scale=0.012, seed=0, loc=(0, 0, 0), material=None, flat_radius=0.0, sub=8):
    """Displaced grid for gentle dunes / hills; flat near the origin if flat_radius."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=2 ** sub, y_subdivisions=2 ** sub, size=size, location=loc)
    g = bpy.context.object
    noise = mathutils.noise
    for v in g.data.vertices:
        x, y = v.co.x + loc[0], v.co.y + loc[1]
        h = noise.fractal(V((x * scale + seed, y * scale, 0)), 0.5, 2.0, 5) * height
        r = math.hypot(x, y)
        if flat_radius:
            h *= min(1.0, max(0.0, (r - flat_radius) / flat_radius))
        v.co.z = h
    for f in g.data.polygons:
        f.use_smooth = True
    if material:
        g.data.materials.append(material)
    return g


def emission_material(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; n.clear()
    e = n.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    o = n.new('ShaderNodeOutputMaterial'); m.node_tree.links.new(e.outputs[0], o.inputs[0])
    return m


def camera(loc, target, lens=30, focus=None, fstop=8):
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.object; sc.camera = c
    c.data.lens = lens; c.data.sensor_fit = 'VERTICAL'; c.data.clip_end = 5000
    c.rotation_euler = (V(target) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
    if focus:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus; c.data.dof.aperture_fstop = fstop
    return c


def sun(rot_deg, energy, color, angle=1.0):
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 50))
    s = bpy.context.object; s.data.energy = energy; s.data.color = color; s.data.angle = math.radians(angle)
    s.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    return s


def render(mist=(10, 300), fog=(0.1, 0.1, 0.1), fog_amount=0.75, exposure=0.0, look='AgX - Medium High Contrast',
           glow=0.8, world=None, sky_fog=None):
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
    sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = look
    sc.view_settings.exposure = exposure
    sc.view_layers[0].use_pass_mist = True
    w = world or sc.world
    w.mist_settings.start, w.mist_settings.depth = mist; w.mist_settings.falloff = 'QUADRATIC'
    sc.use_nodes = True
    ct = sc.node_tree; ct.nodes.clear()
    rl = ct.nodes.new('CompositorNodeRLayers')
    f = ct.nodes.new('CompositorNodeMixRGB'); f.inputs[2].default_value = (*fog, 1)
    mc = ct.nodes.new('CompositorNodeMath'); mc.operation = 'MULTIPLY'; mc.inputs[1].default_value = fog_amount
    ct.links.new(rl.outputs['Mist'], mc.inputs[0])
    if sky_fog is None:
        ct.links.new(mc.outputs[0], f.inputs[0])
    else:
        # sky (mist == 1) gets its own, usually lighter, fog
        obj = ct.nodes.new('CompositorNodeMath'); obj.operation = 'LESS_THAN'; obj.inputs[1].default_value = 0.999
        ct.links.new(rl.outputs['Mist'], obj.inputs[0])
        mix = ct.nodes.new('CompositorNodeMixRGB'); mix.inputs[1].default_value = (sky_fog,) * 3 + (1,)
        ct.links.new(obj.outputs[0], mix.inputs[0]); ct.links.new(mc.outputs[0], mix.inputs[2])
        ct.links.new(mix.outputs[0], f.inputs[0])
    ct.links.new(rl.outputs['Image'], f.inputs[1])
    g = ct.nodes.new('CompositorNodeGlare'); g.glare_type = 'FOG_GLOW'; g.quality = 'HIGH'; g.threshold = glow; g.size = 8
    ct.links.new(f.outputs[0], g.inputs[0])
    co = ct.nodes.new('CompositorNodeComposite'); ct.links.new(g.outputs[0], co.inputs[0])
    sc.render.filepath = OUT; sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print('DONE', OUT)


def hdri_sun(img):
    """(standard azimuth deg, elevation deg) of the brightest pixel in an equirect image, unrotated."""
    import numpy as np
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[..., :3].sum(-1)
    row, col = np.unravel_index(np.argmax(lum), lum.shape)  # row 0 = bottom
    u, v = (col + .5) / w, (row + .5) / h
    theta = math.pi - (u - 0.5) * 2 * math.pi
    return math.degrees(theta) % 360, math.degrees((v - 0.5) * math.pi)


def aim_hdri(env_node_tree, want_az):
    """Rotate the HDRI so its sun sits at standard azimuth want_az (deg, 90 = +Y). Returns sun elevation."""
    env = next(n for n in env_node_tree.nodes if n.type == 'TEX_ENVIRONMENT')
    mp = next(n for n in env_node_tree.nodes if n.type == 'MAPPING')
    az, el = hdri_sun(env.image)
    mp.inputs['Rotation'].default_value[2] = math.radians(az - want_az)
    print('HDRI sun az', az, 'el', el)
    return el


def sun_disk(az, el, dist=4000, size_deg=2.2, color=(1.0, 0.75, 0.45), strength=40):
    a, e = math.radians(az), math.radians(el)
    loc = V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
    bpy.ops.mesh.primitive_uv_sphere_add(radius=dist * math.tan(math.radians(size_deg / 2)), location=loc)
    o = bpy.context.object; o.data.materials.append(emission_material('sundisk', color, strength))
    o.visible_shadow = False
    return o
