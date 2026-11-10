"""Pine Hollow: a misty pine forest at dawn, mossy log and boulder in front, sun through the trees."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *

w, nt, bg = world_hdri('qwantani_dawn_puresky', strength=0.5, tint=(0.85, 0.95, 1.0))
SUN_AZ = 92
el = aim_hdri(nt, SUN_AZ)
sun((90 - 15, 0, SUN_AZ + 90), 3.0, (1.0, 0.75, 0.5), angle=2)
sun_disk(SUN_AZ, 15, size_deg=2.0, color=(1.0, 0.85, 0.6), strength=60)

g = textured_ground('forest_leaves_02', size=10, tile=2.0, bump=0.6)
mat = g.data.materials[0]; bpy.data.objects.remove(g)
terrain(size=600, height=1.6, scale=0.03, seed=21, flat_radius=8, sub=9, material=mat)
mp = next(n for n in mat.node_tree.nodes if n.type == 'MAPPING'); mp.inputs['Scale'].default_value = (600 / 3.5,) * 3; mp.inputs['Rotation'].default_value[2] = math.radians(33)

rnd = random.Random(3)
spots = []
for _ in range(520):
    x, y = rnd.uniform(-60, 60), rnd.uniform(5, 220)
    if abs(x) < 2.2 + y * 0.02:  # keep a corridor open towards the sun
        continue
    spots.append((x, y))
spots += [(-5.5, 9), (6.5, 13), (-8, 22)]
instances('pine_tree_01', spots, seed=2, scale=(0.8, 1.3), ground=lambda x, y: (surface(x, y, top=50) or 0) - 0.2)

place('dead_tree_trunk', (0.4, -3.4, 0.0), rot=-8, scale=1.5)
place('boulder_01', (-2.0, -4.6, -0.1), rot=40, scale=1.4)

camera((0.1, -9.0, 1.1), (0.0, 80, 6.5), lens=28, focus=6, fstop=5.6)
render(mist=(3, 120), fog=(0.62, 0.68, 0.62), fog_amount=0.85, exposure=-0.2, glow=0.9, sky_fog=0.55)
