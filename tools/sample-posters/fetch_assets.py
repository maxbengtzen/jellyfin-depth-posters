"""Fetch CC0 assets from Poly Haven: ph.py <dest> model:<id>[@res] hdri:<id>[@res] tex:<id>[@res]"""
import json, os, sys, urllib.request
dest = sys.argv[1]
UA = {'User-Agent': 'depth-posters-demo/1.0'}
open_ = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA))
def get(url, path):
    if os.path.exists(path): return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open_(url) as r, open(path, 'wb') as f: f.write(r.read())
for spec in sys.argv[2:]:
    kind, rest = spec.split(':'); aid, _, res = rest.partition('@')
    files = json.load(open_(f'https://api.polyhaven.com/files/{aid}'))
    out = os.path.join(dest, aid)
    if kind == 'model':
        g = files['gltf'][res or '1k']['gltf']
        get(g['url'], os.path.join(out, f'{aid}.gltf'))
        for rel, f in g['include'].items(): get(f['url'], os.path.join(out, rel))
    elif kind == 'hdri':
        get(files['hdri'][res or '2k']['hdr']['url'], os.path.join(out, f'{aid}.hdr'))
    elif kind == 'tex':
        for m in ('Diffuse', 'Rough', 'nor_gl', 'Displacement', 'AO'):
            if m in files: get(files[m][res or '1k']['jpg']['url'], os.path.join(out, f'{m}.jpg'))
    print('ok', spec, flush=True)
