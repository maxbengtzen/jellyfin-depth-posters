/* Depth Posters: parallax + tilt on poster hover, driven by per-item depth maps.
 * Depth data comes from /DepthPosters/<itemId>/... (proxied by the plugin). Items
 * without depth data are left alone. */
(function () {
  'use strict';
  if (window.__depthPosters) return;
  window.__depthPosters = true;
  if (window.matchMedia && window.matchMedia('(hover: none)').matches) return;

  const CFG = { useLayers: true, strength: 0.04, focus: 0.45, tilt: 6, posterSize: 720, missingRetryMs: 60000, textureCache: 40 };
  const POSTER_RE = /Items\/([0-9a-f]{32})\/Images\/Primary/i;

  // Settings from the plugin's configuration page; the defaults above apply until (or unless) they load.
  const settingsReady = fetch(`${(window.ApiClient && window.ApiClient.serverAddress && window.ApiClient.serverAddress()) || location.origin}/DepthPosters/config.json`)
    .then(r => (r.ok ? r.json() : {}))
    .then(c => { for (const k of ['useLayers', 'strength', 'tilt', 'focus']) if (c[k] !== undefined) CFG[k] = c[k]; })
    .catch(() => {});

  const apiBase = () => ((window.ApiClient && window.ApiClient.serverAddress && window.ApiClient.serverAddress()) || location.origin).replace(/\/$/, '');

  // ---- data ---------------------------------------------------------------
  const manifests = new Map(); // itemId -> { promise, at }
  function getManifest(id) {
    const hit = manifests.get(id);
    if (hit && !(hit.missing && Date.now() - hit.at > CFG.missingRetryMs)) return hit.promise;
    const entry = { at: Date.now(), missing: false };
    entry.promise = fetch(`${apiBase()}/DepthPosters/${id}/manifest.json`)
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null)
      .then(m => { entry.missing = !m; return m; });
    manifests.set(id, entry);
    return entry.promise;
  }

  const loadImage = src => new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });

  // ---- WebGL --------------------------------------------------------------
  const VS = `attribute vec2 p; varying vec2 uv;
    void main(){ uv = p * .5 + .5; uv.y = 1. - uv.y; gl_Position = vec4(p, 0., 1.); }`;
  const FS = `precision highp float;
    varying vec2 uv;
    uniform sampler2D img, dep;
    uniform vec2 mouse, cover;
    uniform float strength, focus, amount;
    float depthAt(vec2 t){ return texture2D(dep, t).r; }
    void main(){
      vec2 cuv = (uv - .5) * cover + .5;                       // emulate object-fit: cover
      vec2 base = (cuv - .5) / (1. + strength * 1.6) + .5;     // zoom so shifted edges stay hidden
      vec2 dir = -mouse * strength;
      const int STEPS = 24;
      float layerD = 1. / float(STEPS);
      float cur = 1.;
      vec2 t = base + dir * (1. - focus);
      vec2 stepv = -dir * layerD;
      float d = depthAt(t);
      for (int i = 0; i < STEPS; i++) {
        if (cur <= d) break;
        cur -= layerD; t += stepv; d = depthAt(t);
      }
      t = clamp(t, vec2(.001), vec2(.999));
      vec3 col = texture2D(img, t).rgb;
      float glare = pow(max(0., 1. - distance(uv, .5 + mouse * .5) * 1.4), 3.) * .10 * amount;
      gl_FragColor = vec4(col + glare, 1.);
    }`;

  // Layer mode: pre-cut, inpainted RGBA layers, each shifted by its own depth, composited back to front.
  const FS_LAYER = `precision highp float;
    varying vec2 uv;
    uniform sampler2D tex;
    uniform vec2 offset, mouse, cover;
    uniform float zoom, amount;
    void main(){
      vec2 cuv = (uv - .5) * cover + .5;
      vec2 t = clamp((cuv - .5) / zoom + .5 + offset, vec2(0.), vec2(1.));
      vec4 c = texture2D(tex, t);
      float glare = pow(max(0., 1. - distance(uv, .5 + mouse * .5) * 1.4), 3.) * .10 * amount;
      gl_FragColor = c + vec4(vec3(glare) * c.a, 0.);
    }`;

  let canvas, gl, prog, uni, progLayer, uniLayer;
  function initGL() {
    if (gl) return true;
    canvas = document.createElement('canvas');
    canvas.className = 'depth-poster-canvas';
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;border-radius:inherit;transform-origin:center;will-change:transform;';
    gl = canvas.getContext('webgl', { antialias: true, alpha: false });
    if (!gl) return false;
    const sh = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const program = fragment => {
      const p = gl.createProgram();
      gl.attachShader(p, sh(gl.VERTEX_SHADER, VS));
      gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fragment));
      gl.bindAttribLocation(p, 0, 'p');
      gl.linkProgram(p);
      return p;
    };
    const uniforms = (p, names) => Object.fromEntries(names.map(n => [n, gl.getUniformLocation(p, n)]));
    prog = program(FS);
    progLayer = program(FS_LAYER);
    uni = uniforms(prog, ['img', 'dep', 'mouse', 'cover', 'strength', 'focus', 'amount']);
    uniLayer = uniforms(progLayer, ['tex', 'offset', 'mouse', 'cover', 'zoom', 'amount']);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    return true;
  }

  function makeTexture(image, rgba = false) {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, rgba);
    const fmt = rgba ? gl.RGBA : gl.RGB;
    gl.texImage2D(gl.TEXTURE_2D, 0, fmt, fmt, gl.UNSIGNED_BYTE, image);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }

  const deleteEntry = e => [e.img, e.dep, ...(e.layers || []).map(l => l.tex)].forEach(t => t && gl.deleteTexture(t));

  const textures = new Map(); // `${id}/${tag}` -> { img, dep, layers, w, h } (Map order = LRU)
  async function getTextures(id, m) {
    const key = `${id}/${m.tag}`;
    const hit = textures.get(key);
    if (hit) { textures.delete(key); textures.set(key, hit); return hit; }
    const base = apiBase();
    const asset = name => `${base}/DepthPosters/${id}/${m.tag}/${name}`;
    let entry;
    if (CFG.useLayers && m.layers && m.layers.files.length) {
      const imgs = await Promise.all(m.layers.files.map(f => loadImage(asset(f))));
      if (!initGL()) return null;
      entry = { layers: imgs.map((im, k) => ({ tex: makeTexture(im, true), depth: m.layers.depths[k] })), w: imgs[0].naturalWidth, h: imgs[0].naturalHeight };
    } else {
      const [poster, depth] = await Promise.all([
        loadImage(`${base}/Items/${id}/Images/Primary?tag=${m.tag}&maxWidth=${CFG.posterSize}&maxHeight=${CFG.posterSize}&quality=95`),
        loadImage(asset(m.depth)),
      ]);
      if (!initGL()) return null;
      entry = { img: makeTexture(poster), dep: makeTexture(depth), w: poster.naturalWidth, h: poster.naturalHeight };
    }
    textures.set(key, entry);
    while (textures.size > CFG.textureCache) {
      const [oldKey, old] = textures.entries().next().value;
      deleteEntry(old);
      textures.delete(oldKey);
    }
    return entry;
  }

  // ---- hover handling -----------------------------------------------------
  let active = null;          // card element being hovered
  let container = null;       // element the canvas lives in
  let tex = null;
  let raf = 0;
  let amount = 0, targetAmount = 0;
  let mouse = [0, 0], cur = [0, 0];
  let seq = 0;

  function posterContainer(card) {
    const id = (card.outerHTML.match(POSTER_RE) || [])[1];
    if (!id) return null;
    const el = [...card.querySelectorAll('.cardImageContainer')].find(e => !e.closest('.cardOverlayContainer'));
    return el ? { id, el } : null;
  }

  function attach(el, entry) {
    container = el;
    tex = entry;
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
    const r = el.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(2, Math.round(r.width * dpr));
    canvas.height = Math.max(2, Math.round(r.height * dpr));
    gl.viewport(0, 0, canvas.width, canvas.height);
    const ca = r.width / r.height, ia = entry.w / entry.h;
    const cover = [ca > ia ? 1 : ca / ia, ca > ia ? ia / ca : 1];
    if (entry.layers) {
      gl.useProgram(progLayer);
      gl.uniform2f(uniLayer.cover, cover[0], cover[1]);
      gl.uniform1i(uniLayer.tex, 0);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    } else {
      gl.useProgram(prog);
      gl.disable(gl.BLEND);
      gl.uniform2f(uni.cover, cover[0], cover[1]);
      gl.uniform1i(uni.img, 0);
      gl.uniform1i(uni.dep, 1);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, entry.img);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, entry.dep);
    }
    cur = [0, 0];
    el.insertBefore(canvas, el.firstChild);
    if (!raf) raf = requestAnimationFrame(frame);
  }

  function detach() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    container = null;
    amount = 0;
  }

  function frame() {
    raf = requestAnimationFrame(frame);
    amount += (targetAmount - amount) * 0.18;
    if (targetAmount === 0 && amount < 0.01) { detach(); return; }
    cur = [cur[0] + (mouse[0] - cur[0]) * 0.14, cur[1] + (mouse[1] - cur[1]) * 0.14];
    const strength = CFG.strength * amount;
    if (tex.layers) {
      gl.clearColor(0, 0, 0, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform2f(uniLayer.mouse, cur[0], cur[1]);
      gl.uniform1f(uniLayer.zoom, 1 + strength * 1.6);
      gl.uniform1f(uniLayer.amount, amount);
      gl.activeTexture(gl.TEXTURE0);
      for (const layer of tex.layers) {
        gl.bindTexture(gl.TEXTURE_2D, layer.tex);
        const k = -strength * (layer.depth - CFG.focus);
        gl.uniform2f(uniLayer.offset, cur[0] * k, cur[1] * k);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      }
    } else {
      gl.uniform2f(uni.mouse, cur[0], cur[1]);
      gl.uniform1f(uni.strength, strength);
      gl.uniform1f(uni.focus, CFG.focus);
      gl.uniform1f(uni.amount, amount);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    const tilt = CFG.tilt * amount;
    canvas.style.transform = `perspective(700px) rotateY(${cur[0] * tilt}deg) rotateX(${-cur[1] * tilt}deg) scale(${1 + 0.03 * amount})`;
  }

  function track(e) {
    if (!container) return;
    const r = container.getBoundingClientRect();
    mouse = [Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1)),
             Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height) * 2 - 1))];
  }

  document.addEventListener('pointerover', async e => {
    const card = e.target.closest && e.target.closest('.card');
    if (!card || card === active) return;
    if (container) detach();
    active = card;
    const my = ++seq;
    const found = posterContainer(card);
    if (!found) return;
    await settingsReady;
    const m = await getManifest(found.id);
    if (!m || my !== seq) return;
    let entry;
    try { entry = await getTextures(found.id, m); } catch (_) { return; }
    if (!entry || my !== seq) return;
    mouse = [0, 0];
    track(e);
    attach(found.el, entry);
    targetAmount = 1;
  }, true);

  document.addEventListener('pointermove', track, true);

  document.addEventListener('pointerout', e => {
    if (!active || active.contains(e.relatedTarget)) return;
    active = null;
    seq++;
    targetAmount = 0;
    mouse = [0, 0];
    if (!container) return;
  }, true);
})();
