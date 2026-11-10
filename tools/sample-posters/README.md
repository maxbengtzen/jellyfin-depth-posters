# Sample posters

Four posters for films that do not exist, made for the demo and for trying the
[playground](../../docs/playground.md) without real cover art.

| | |
|---|---|
| `lowtide.jpg` | A lantern on a pier at night, an island and a moon behind fog |
| `dryseason.jpg` | A backlit tree in a desert at sunset |
| `regolith.jpg` | A moonscape under a ringed planet |
| `hollow.jpg` | A misty pine forest at dawn |

They are rendered in [Blender](https://www.blender.org/) (Cycles, CPU) from
[Poly Haven](https://polyhaven.com/) models, textures and skies, which are all CC0. The type is
set in [Bebas Neue](https://fonts.google.com/specimen/Bebas+Neue), Cinzel, Cormorant Garamond,
Orbitron and Oswald (SIL Open Font License).

**The posters are dedicated to the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).** Use them for anything.

## Try them in the playground

```bash
mkdir -p posters && cp tools/sample-posters/*.jpg posters/
```

then follow [docs/playground.md](../../docs/playground.md).

## Rendering them again

Tested with Blender 4.5 LTS. Each scene takes 2 to 8 minutes at 1000×1500 and 128 samples on 8 CPU cores.

```bash
cd tools/sample-posters
python3 fetch_assets.py assets \
  model:Lantern_01 model:modular_wooden_pier model:coastal_cliff_01 model:coastal_cliff_02 \
  model:coast_rocks_01 model:coast_rocks_02 model:pine_tree_01 hdri:kloppenheim_07_puresky \
  model:namaqualand_boulder_02 model:namaqualand_boulder_05 model:namaqualand_cliff_01 \
  model:namaqualand_boulders_01 model:island_tree_01 model:island_tree_02 model:othonna_cerarioides \
  hdri:qwantani_sunset_puresky tex:red_sand \
  model:moon_rock_01 model:moon_rock_03 model:moon_rock_05 tex:moon_dusted_02 \
  model:dead_tree_trunk model:boulder_01 hdri:qwantani_dawn_puresky tex:forest_leaves_02

for scene in lowtide dryseason regolith hollow; do
  blender -b --python scenes/$scene.py -- "$PWD/assets" "$PWD/out/$scene.png" 1000 128
done
```

`typeset.py` grades a render and sets the title, tagline and billing block. It needs Pillow and
NumPy, and the five font files in a directory (from [google/fonts](https://github.com/google/fonts)):
`BebasNeue-Regular.ttf`, `Cinzel-VF.ttf`, `CormorantGaramond-VF.ttf`, `Orbitron-VF.ttf`, `Oswald-VF.ttf`.

```bash
python3 typeset.py lowtide out/lowtide.png lowtide.jpg fonts/
```

The assets (about 1.3 GB, mostly the pine trees) and renders are git-ignored.
