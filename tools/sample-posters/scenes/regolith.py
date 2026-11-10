"""Regolith: a moonscape, boulders foreground, ringed planet low in a black starfield."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *

# black sky with stars
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
tc = nt.nodes.new('ShaderNodeTexCoord'); vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 420
nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
ramp.color_ramp.elements[1].position = 0.05; ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
nt.links.new(vor.outputs['Distance'], ramp.inputs[0])
nz = nt.nodes.new('ShaderNodeTexWhiteNoise'); nt.links.new(tc.outputs['Generated'], nz.inputs['Vector'])
mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
nt.links.new(ramp.outputs[0], mul.inputs[0]); nt.links.new(vor.outputs['Color'], nz.inputs[0])
nt.links.new(nz.outputs['Value'], mul.inputs[1])
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 3.0
mul2 = nt.nodes.new('ShaderNodeMath'); mul2.operation = 'MULTIPLY'; mul2.inputs[1].default_value = 14
nt.links.new(mul.outputs[0], mul2.inputs[0]); nt.links.new(mul2.outputs[0], bg.inputs['Strength'])
bg.inputs['Color'].default_value = (0.85, 0.9, 1, 1)
out = nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(bg.outputs[0], out.inputs[0])

ground = textured_ground('moon_dusted_02', size=10, tile=2.0, bump=0.5)
bpy.data.objects.remove(ground)
mat = bpy.data.materials['moon_dusted_02']
t = terrain(size=3000, height=14, scale=0.004, seed=11, flat_radius=40, sub=8, material=mat)
# the grid's UVs run 0..1, so tile the texture by size / tile length
mp = next(n for n in mat.node_tree.nodes if n.type == 'MAPPING'); mp.inputs['Scale'].default_value = (3000 / 2.5,) * 3

place('moon_rock_01', (-1.5, -5.2, -0.25), rot=30, scale=13)
place('moon_rock_05', (2.2, -2.8, -0.15), rot=120, scale=12)
place('moon_rock_03', (-14, 45, -0.8), rot=0, scale=80)
place('moon_rock_01', (70, 240, -4), rot=80, scale=260)
place('moon_rock_05', (-170, 520, -10), rot=10, scale=600)
rnd = random.Random(5)
spots = [(rnd.uniform(-30, 30), rnd.uniform(2, 90)) for _ in range(40)]
for i, r in enumerate(['moon_rock_01', 'moon_rock_03', 'moon_rock_05']):
    instances(r, [(x, y, -0.05) for x, y in spots[i::3]], seed=i, scale=(2, 7))

# ringed planet
bpy.ops.mesh.primitive_uv_sphere_add(radius=420, location=(-230, 3200, 760), segments=96, ring_count=48)
pl = bpy.context.object
m = bpy.data.materials.new('planet'); m.use_nodes = True; pl.data.materials.append(m)
n, l = m.node_tree.nodes, m.node_tree.links
p = n['Principled BSDF']; p.inputs['Roughness'].default_value = 0.9
wave = n.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'Z'
wave.inputs['Scale'].default_value = 1.2; wave.inputs['Distortion'].default_value = 6; wave.inputs['Detail'].default_value = 4
cr = n.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].color = (0.16, 0.26, 0.48, 1); cr.color_ramp.elements[1].color = (0.7, 0.84, 0.95, 1)
l.new(wave.outputs['Fac'], cr.inputs[0]); l.new(cr.outputs[0], p.inputs['Base Color'])
bpy.ops.mesh.primitive_circle_add(vertices=256, radius=900, fill_type='NGON', location=pl.location)
ring = bpy.context.object
ring.rotation_euler = (math.radians(21), math.radians(-17), 0)
ring.visible_shadow = False
rm = bpy.data.materials.new('ring'); rm.use_nodes = True; ring.data.materials.append(rm)
rn, rl_ = rm.node_tree.nodes, rm.node_tree.links
rp = rn['Principled BSDF']; rp.inputs['Base Color'].default_value = (0.75, 0.8, 0.88, 1)
grad = rn.new('ShaderNodeTexGradient'); grad.gradient_type = 'SPHERICAL'
rtc = rn.new('ShaderNodeTexCoord'); rmp = rn.new('ShaderNodeMapping'); rmp.inputs['Scale'].default_value = (1 / 900,) * 3
rl_.new(rtc.outputs['Object'], rmp.inputs[0]); rl_.new(rmp.outputs[0], grad.inputs[0])
rw = rn.new('ShaderNodeTexWave'); rw.wave_type = 'RINGS'; rw.inputs['Scale'].default_value = 9; rw.inputs['Distortion'].default_value = 1.5
rl_.new(rmp.outputs[0], rw.inputs[0])
band = rn.new('ShaderNodeValToRGB')  # radial window: hole in the middle, fade out at the edge
band.color_ramp.elements[0].position = 0.0; band.color_ramp.elements[0].color = (0, 0, 0, 1)
band.color_ramp.elements[1].position = 0.22; band.color_ramp.elements[1].color = (1, 1, 1, 1)
e = band.color_ramp.elements.new(0.6); e.color = (0, 0, 0, 1)
rl_.new(grad.outputs['Fac'], band.inputs[0])
am = rn.new('ShaderNodeMath'); am.operation = 'MULTIPLY'
rl_.new(band.outputs[0], am.inputs[0]); rl_.new(rw.outputs['Fac'], am.inputs[1])
rl_.new(am.outputs[0], rp.inputs['Alpha'])

sun((90 - 14, 0, 205 + 90), 5.0, (1.0, 0.97, 0.92), angle=0.6)

camera((0.4, -11, 1.3), (0, 120, 14), lens=26, focus=12, fstop=11)
render(mist=(40, 3000), fog=(0.03, 0.03, 0.04), fog_amount=0.5, exposure=-0.2, glow=1.5, sky_fog=0.0)
