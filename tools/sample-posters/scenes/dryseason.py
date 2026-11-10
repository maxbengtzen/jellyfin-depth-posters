"""Dry Season: desert at sunset, backlit acacia, boulders foreground, mesas in haze."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *

w, nt, bg = world_hdri('qwantani_sunset_puresky', strength=0.32, tint=(1.0, 0.6, 0.4))
SUN_AZ = 91
el = aim_hdri(nt, SUN_AZ)
sun((90 - max(el, 4), 0, SUN_AZ + 90), 4.5, (1.0, 0.55, 0.3), angle=1.5)
sun_disk(SUN_AZ, el + 0.4, size_deg=2.6)

g = textured_ground('red_sand', size=2400, tile=1.2, tint=(1.0, 0.72, 0.55), bump=0.25, loc=(0, 0, -0.02))
dunes = terrain(size=2400, height=10, scale=0.005, seed=3, flat_radius=70, sub=8)
dunes.data.materials.append(g.data.materials[0]); bpy.data.objects.remove(g)

place('namaqualand_boulder_02', (-1.9, -5.6, -0.25), rot=160, scale=1.6)
place('namaqualand_boulder_05', (2.3, -4.0, -0.08), rot=70, scale=0.9)
place('island_tree_01', (3.4, 34, -0.05), rot=20, scale=2.4)
place('island_tree_02', (-24, 90, -0.05), rot=200, scale=1.7)
place('othonna_cerarioides', (-5.0, 10, -0.05), rot=60, scale=1.0)
for x, y, s, r in [(-300, 760, 24, 10), (150, 900, 26, -20), (480, 1000, 30, 35), (-650, 1050, 28, 70)]:
    place('namaqualand_cliff_01', (x, y, -10), rot=r, scale=s)
instances('namaqualand_boulders_01', [(x, y, 0) for x, y in [(-7, 16), (9, 24)]], seed=4, scale=(0.8, 1.3))

camera((0.2, -10, 0.85), (0.0, 120, 9.0), lens=30, focus=40, fstop=11)
render(mist=(25, 1500), fog=(1.0, 0.52, 0.3), fog_amount=0.6, exposure=-0.6, glow=1.0, sky_fog=0.12)
