"""Grade a render and set the poster type. typeset.py <name> <in.png> <out.jpg> <fonts dir>"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

name, src, dst, FD = sys.argv[1:5]


def font(file, size, weight=None):
    f = ImageFont.truetype(os.path.join(FD, file), size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


POSTERS = {
    'lowtide': dict(title='LOW TIDE', tfont=('Cinzel-VF.ttf', 150, 600), track=0.16, ty=0.085,
                    tag='SOME LIGHTS ARE LEFT ON FOR A REASON', tagfont=('Oswald-VF.ttf', 30, 300), tagy=0.045,
                    color=(236, 240, 248), grade=dict(gain=(1.0, 1.0, 1.04), lift=(0, 2, 6))),
    'dryseason': dict(title='DRY SEASON', tfont=('BebasNeue-Regular.ttf', 210, None), track=0.05, ty=0.07,
                      tag='NOTHING GROWS HERE. SOMETHING WAITS.', tagfont=('Oswald-VF.ttf', 30, 300), tagy=0.04,
                      color=(255, 238, 220), grade=dict(gain=(1.1, 0.97, 0.86), lift=(8, 0, 0), sky=((255, 150, 80), 0.45))),
    'regolith': dict(title='REGOLITH', tfont=('Orbitron-VF.ttf', 128, 800), track=0.22, ty=0.07,
                     tag='EIGHT DAYS OF AIR. TWO HUNDRED MILES OF DUST.', tagfont=('Oswald-VF.ttf', 28, 300), tagy=0.04,
                     color=(225, 235, 250), grade=dict(gain=(0.98, 1.0, 1.06), lift=(0, 0, 3))),
    'hollow': dict(title='PINE HOLLOW', tfont=('CormorantGaramond-VF.ttf', 150, 600), track=0.08, ty=0.075,
                   tag='EVERYONE WHO WALKS IN COMES OUT QUIETER', tagfont=('Oswald-VF.ttf', 28, 400), tagy=0.04,
                   color=(28, 34, 30), top_dark=-0.6, billing=(236, 232, 218), glow=(255, 250, 235), grade=dict(gain=(1.06, 1.02, 0.92), lift=(4, 2, 0), sky=((255, 205, 140), 0.25))),
}
P = POSTERS[name]

im = Image.open(src).convert('RGB')
W, H = im.size
a = np.asarray(im).astype(np.float32)
g = P['grade']
a = a * np.array(g['gain']) + np.array(g['lift'])
yy, xx = np.mgrid[0:H, 0:W]
if 'sky' in g:  # warm wash over the top half
    col, k = g['sky']
    t = np.clip(1 - yy / (H * 0.6), 0, 1)[..., None] ** 1.5 * k
    a = a * (1 - t) + np.array(col) * (a.mean(-1, keepdims=True) / 255) ** 0.5 * t
# vignette
r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
a *= (1 - 0.32 * np.clip(r - 0.55, 0, 1) ** 1.4)[..., None]
# darken behind the title and the billing block so the type reads
top = np.clip(1 - yy / (H * 0.3), 0, 1) ** 2 * P.get('top_dark', 0.35)
bot = np.clip((yy - H * 0.86) / (H * 0.14), 0, 1) ** 1.5 * 0.55
a *= (1 - np.maximum(top, 0) - bot)[..., None]
if P.get('top_dark', 0) < 0:  # lighten towards a fog colour instead
    k = np.clip(1 - yy / (H * 0.32), 0, 1)[..., None] ** 1.6 * -P['top_dark']
    a = a * (1 - k) + np.array(P['glow']) * 0.93 * k
im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
d = ImageDraw.Draw(layer)


def tracked(text, f, y, color, track, center=True):
    widths = [d.textlength(ch, font=f) for ch in text]
    sp = f.size * track
    total = sum(widths) + sp * (len(text) - 1)
    x = (W - total) / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=color)
        x += w + sp
    return total


tf = font(*P['tfont'])
# fit the title to 86% of the width
size = P['tfont'][1]
while True:
    widths = sum(d.textlength(ch, font=tf) for ch in P['title']) + tf.size * P['track'] * (len(P['title']) - 1)
    if widths <= W * 0.86 or size < 40:
        break
    size -= 4; tf = font(P['tfont'][0], size, P['tfont'][2])
ty = H * P['ty']
tracked(P['title'], tf, ty, P['color'] + (255,), P['track'])
asc = tf.getbbox('A')[3]
tagf = font(*P['tagfont'])
tracked(P['tag'], tagf, ty + asc + H * P['tagy'] * 0.6, P['color'] + (215,), 0.28)

# billing block
small = font('Oswald-VF.ttf', 19, 300)
tiny = font('Oswald-VF.ttf', 15, 400)
by = H * 0.905
lines = ['A DEPTH POSTERS PICTURE   ·   RENDERED IN BLENDER CYCLES   ·   SCENERY FROM POLY HAVEN',
         'NO ACTORS   ·   NO SCRIPT   ·   ONE CAMERA   ·   A LOT OF FOG']
for i, line in enumerate(lines):
    tracked(line, small, by + i * 28, P.get('billing', P['color']) + (170,), 0.12)
tracked('CC0 1.0   ·   PUBLIC DOMAIN DEDICATION', tiny, by + 72, P.get('billing', P['color']) + (140,), 0.3)

shadow = layer.split()[3].filter(ImageFilter.GaussianBlur(6))
sh = Image.new('RGBA', im.size, P.get('glow', (0, 0, 0)) + (0,)); sh.putalpha(shadow.point(lambda v: int(v * 0.6)))
out = im.convert('RGBA')
out.alpha_composite(sh); out.alpha_composite(layer)
out.convert('RGB').save(dst, quality=92, optimize=True, progressive=True)
print('wrote', dst, out.size)
