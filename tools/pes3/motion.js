/* PES 3 local animation research, format FPSANM14.
 * Port of the supplied v0.14 decoder/local evaluator, with binary32 steps.
 * Source package SHA256: 7561b99ddaca6e12c9c70f483a340c38dbb378172ae67911f2d092fe8f2bda5e.
 * This is not the final PS2 hierarchy, mirroring, blending or action loop.
 */
(function (root) {
  "use strict";
  const f = Math.fround;
  const scratch = new DataView(new ArrayBuffer(4));
  const num = b => { scratch.setUint32(0, b, true); return scratch.getFloat32(0, true); };
  const raw = x => { scratch.setFloat32(0, x, true); return scratch.getUint32(0, true); };
  const add = (a, b) => f(a + b), sub = (a, b) => f(a - b);
  const mul = (a, b) => f(a * b), div = (a, b) => f(a / b);
  const vu = x => { const b = raw(x); return (b & 0x7f800000) ? f(x) : num(b & 0x80000000); };
  const vmul = (a, b) => vu(mul(vu(a), vu(b)));
  const vadd = (a, b) => vu(add(vu(a), vu(b)));
  const requireValue = (condition, message) => { if (!condition) throw new Error(message); };

  function atan(argument) {
    const magnitude = raw(argument);
    let x = argument, region = -1;
    if (magnitude > 0x507fffff) return add(num(0x3fc90fda), num(0x33a22168));
    if (magnitude > 0x3edfffff) {
      if (magnitude <= 0x3f97ffff) {
        if (magnitude <= 0x3f2fffff) {
          x = div(sub(add(x, x), 1), add(x, 2)); region = 0;
        } else { x = div(sub(x, 1), add(x, 1)); region = 1; }
      } else if (magnitude <= 0x401bffff) {
        x = div(sub(x, 1.5), add(mul(x, 1.5), 1)); region = 2;
      } else { x = div(-1, x); region = 3; }
    } else if (magnitude <= 0x30ffffff && 1 < add(x, num(0x7149f2c9))) return x;
    const c = [0x3eaaaaab, 0xbe4ccccc, 0x3e124924, 0xbde38e38, 0x3dba2e6e,
      0xbd9d8795, 0x3d886b34, 0xbd6ef16a, 0x3d4bda59, 0xbd15a221, 0x3c8569d7].map(num);
    const z = mul(x, x), w = mul(z, z);
    let even = add(c[8], mul(w, c[10])), odd = add(c[7], mul(w, c[9]));
    even = add(c[6], mul(w, even)); odd = add(c[5], mul(w, odd));
    even = add(c[4], mul(w, even)); odd = add(c[3], mul(w, odd));
    even = add(c[2], mul(w, even)); odd = add(c[1], mul(w, odd));
    even = add(c[0], mul(w, even)); even = mul(z, even); odd = mul(w, odd);
    let correction = mul(x, add(even, odd));
    if (region < 0) return sub(x, correction);
    const high = [0x3eed6338, 0x3f490fda, 0x3f7b985d, 0x3fc90fda];
    const low = [0x31ac3769, 0x33222167, 0x33140fb4, 0x33a22168];
    correction = sub(sub(correction, num(low[region])), x);
    return sub(num(high[region]), correction);
  }

  function sineKernel(x) {
    if ((raw(x) & 0x7fffffff) <= 0x31ffffff) return x;
    const z = mul(x, x), v = mul(z, x);
    let r = mul(z, num(0x2f2ec9d2));
    for (const bits of [0xb2d72f34, 0x3638ef1a, 0xb9500d01, 0x3c088889]) {
      r = add(r, num(bits));
      if (bits !== 0x3c088889) r = mul(z, r);
    }
    r = add(mul(z, r), num(0xbe2aaaaa));
    return add(x, mul(v, r));
  }

  function cosineKernel(x, tail) {
    const magnitude = raw(x) & 0x7fffffff;
    if (magnitude <= 0x31ffffff) return 1;
    const z = mul(x, x);
    let r = mul(z, num(0xad47d74e));
    for (const bits of [0x310f74f5, 0xb493f27b, 0x37d00d00, 0xbab60b60, 0x3d2aaaaa]) {
      r = mul(z, add(r, num(bits)));
    }
    const product = mul(x, tail);
    if (magnitude <= 0x3e999999) {
      r = sub(mul(z, r), product);
      return sub(1, sub(mul(z, 0.5), r));
    }
    const q = magnitude <= 0x3f480000 ? num(magnitude - 0x01000000) : num(0x3e900000);
    r = sub(mul(z, r), product);
    return sub(sub(1, q), sub(sub(mul(z, 0.5), q), r));
  }

  function angle(sine, cosine) {
    if (raw(cosine) === 0x3f800000) return atan(sine);
    if ((raw(sine) & 0x7fffffff) <= 0x007fffff) return sine;
    if ((raw(cosine) & 0x7fffffff) <= 0x007fffff) return num(0x3fc90fda);
    if ((((raw(sine) - raw(cosine)) | 0) >> 23) >= 61) return num(0x3fc90fda);
    return atan(div(sine, cosine));
  }

  function sine(value) {
    const magnitude = raw(value) & 0x7fffffff;
    if (magnitude <= 0x3f490fd8) return sineKernel(value);
    let reduced = sub(value, num(0x3fc90f80)), tail;
    if ((magnitude & 0xfffffff0) !== 0x3fc90fd0) tail = num(0x37354442);
    else { reduced = sub(reduced, num(0x373543ff)); tail = num(0x2e85a308); }
    const remainder = sub(reduced, tail), error = sub(sub(reduced, remainder), tail);
    return cosineKernel(remainder, error);
  }

  function parseBundle(buffer) {
    requireValue(buffer instanceof ArrayBuffer && buffer.byteLength >= 32, "Contêiner truncado");
    const view = new DataView(buffer), u = at => view.getUint32(at, true);
    const signature = String.fromCharCode(...new Uint8Array(buffer, 0, 8));
    const count = u(8), directory = u(12);
    requireValue(signature === "FPSANM14" && count > 0 && count <= 20000 && directory === 32
      && u(16) === 14 && u(20) === 19 && u(24) === 164 && u(28) === 0,
    "Cabeçalho FPSANM14 não suportado");
    requireValue(32 + count * 16 <= buffer.byteLength, "Diretório truncado");
    const clips = []; let next = 32 + count * 16;
    for (let id = 0; id < count; id++) {
      const entry = directory + id * 16, start = u(entry + 8), size = u(entry + 12);
      requireValue(u(entry) === id && start === next && size >= 32 && start + size <= buffer.byteLength,
        "Índice, intervalo ou sobreposição de clip inválido");
      const block = new DataView(buffer, start, size);
      const duration = block.getFloat32(8, true), table = block.getUint32(16, true);
      requireValue(block.getUint32(0, true) === 0x20011119 && block.getUint32(4, true) === 0x20000002
        && block.getUint32(12, true) === 60 && raw(duration) === u(entry + 4)
        && Number.isFinite(duration) && duration > 0 && duration <= 4096 && table <= size - 4,
      "Formato ou duração de clip inválido");
      const poses = block.getUint32(table, true);
      requireValue(poses > 0 && poses <= 512 && table === 28 + 164 * poses && size === 32 + 172 * poses,
        "Tabela de poses inválida");
      const times = []; let previous = 0;
      for (let key = 0; key < poses; key++) {
        const endpoint = block.getFloat32(table + 4 + key * 8, true);
        requireValue(block.getUint32(table + 8 + key * 8, true) === 28 + key * 164,
          "Offset de chave inválido");
        requireValue(key === poses - 1 ? endpoint === 0
          : Number.isFinite(endpoint) && endpoint > previous && endpoint <= duration,
        "Tempos de chave inválidos");
        times.push(endpoint); previous = endpoint;
        for (let axis = 0; axis < 3; axis++) {
          requireValue(Number.isFinite(block.getFloat32(28 + key * 164 + 8 + axis * 4, true)),
            "Translação não finita");
        }
      }
      clips.push({id, duration, poses, times, block}); next += size;
    }
    requireValue(next === buffer.byteLength, "Bytes excedentes no contêiner");
    return clips;
  }

  function initialState(bindBits) {
    requireValue(Array.isArray(bindBits) && bindBits.length === 19, "Esqueleto inválido");
    return {clampedTime: 0, intervalIndex: 0, channelCount: 0, reserved: 0,
      bones: bindBits.map(bits => {
        requireValue(bits.length === 4, "Translação de referência inválida");
        const translation = bits.map(num);
        requireValue(translation.every(Number.isFinite), "Referência não finita");
        return {rotationA: [0, 0, 0, 1], rotationB: [0, 0, 0, 1],
          translationA: translation.slice(), translationB: translation.slice(),
          rotationDuration: 0, rotationElapsed: 0, translationDuration: 0, translationElapsed: 0};
      })};
  }

  function selectInterval(times, time) {
    const count = times.length;
    if (count < 2) return 0;
    if (count < 6) {
      let index = 0; while (index < count - 2 && times[index] < time) index++;
      return index;
    }
    let start = 0, length = count - 1;
    while (length) {
      const middle = Math.floor(length / 2), candidate = times[start + middle];
      if (time === candidate) return start + middle;
      if (time < candidate) length = middle;
      else { length -= middle + 1; start += middle + 1; }
    }
    if (times[start] === 0) return start - 1;
    if (times[start] < time) start++;
    return start;
  }

  function decode(clip, time, initial) {
    requireValue(Number.isFinite(time) && initial.bones.length === 19, "Entrada inválida");
    const clampedTime = Math.max(0, Math.min(clip.duration, f(time)));
    const intervalIndex = selectInterval(clip.times, clampedTime);
    requireValue(intervalIndex < clip.poses && (clip.poses === 1 || intervalIndex < clip.poses - 1), "Intervalo inválido");
    const start = intervalIndex ? clip.times[intervalIndex - 1] : 0;
    const span = sub(clip.times[intervalIndex], start), elapsed = sub(clampedTime, start);
    const block = clip.block, a = 28 + 164 * intervalIndex, b = span === 0 ? a : a + 164;
    const rotation = at => [0, 1, 2, 3].map(i => vu(mul(block.getInt16(at + i * 2, true), num(0x38000100))));
    const bones = initial.bones.map((old, i) => {
      const sourceA = a + (i ? 20 + (i - 1) * 8 : 0), sourceB = b + (i ? 20 + (i - 1) * 8 : 0);
      const bone = {...old, rotationA: rotation(sourceA), rotationB: rotation(sourceB),
        translationA: old.translationA.slice(), translationB: old.translationB.slice(),
        rotationDuration: span, rotationElapsed: elapsed};
      if (!i) {
        for (let j = 0; j < 3; j++) {
          bone.translationA[j] = block.getFloat32(a + 8 + j * 4, true);
          bone.translationB[j] = block.getFloat32(b + 8 + j * 4, true);
        }
        bone.translationDuration = span; bone.translationElapsed = elapsed;
      } else bone.translationDuration = 0;
      return bone;
    });
    return {...initial, clampedTime, intervalIndex, channelCount: 19, bones};
  }

  function evaluate(state) {
    requireValue(state.channelCount === 19 && state.bones.length === 19, "Canais inválidos");
    return state.bones.map((b, index) => {
      const arrays = [b.rotationA, b.rotationB, b.translationA, b.translationB];
      requireValue(arrays.every(a => a.length === 4 && a.every(Number.isFinite))
        && [b.rotationDuration, b.rotationElapsed, b.translationDuration, b.translationElapsed]
          .every(v => Number.isFinite(v) && v >= 0), "Canal não finito ou duração inválida");
      let rotation;
      if (b.rotationDuration <= 0) rotation = b.rotationA.slice();
      else {
        const alpha = b.rotationElapsed < b.rotationDuration ? div(b.rotationElapsed, b.rotationDuration) : 1;
        const product = b.rotationA.map((v, i) => vmul(v, b.rotationB[i]));
        let dot = vadd(vadd(vadd(product[3], product[0]), product[1]), product[2]);
        const flip = dot < 0; if (flip) dot = -dot;
        let wa, wb;
        if (sub(1, dot) <= num(0x3727c5ac)) { wa = sub(1, alpha); wb = alpha; }
        else {
          const remainder = sub(1, mul(dot, dot)); requireValue(remainder > 0, "Arco inválido");
          const sin = f(Math.sqrt(remainder)), theta = angle(sin, dot), reciprocal = div(1, sin);
          wa = mul(reciprocal, sine(mul(sub(1, alpha), theta)));
          wb = mul(reciprocal, sine(mul(alpha, theta)));
        }
        if (flip) wb = -wb;
        rotation = b.rotationA.map((v, i) => vadd(vmul(v, wa), vmul(b.rotationB[i], wb)));
      }
      let translation = b.translationA.slice();
      if (!index) {
        const alpha = b.translationElapsed < b.translationDuration ? div(b.translationElapsed, b.translationDuration) : 1;
        const complement = vu(sub(1, vu(alpha)));
        translation = b.translationB.map((v, i) => vadd(vmul(v, alpha), vmul(b.translationA[i], complement)));
      }
      requireValue([...rotation, ...translation].every(Number.isFinite), "Pose não finita");
      return {rotation, translation};
    });
  }

  const api = {parseBundle, initialState, decode, evaluate, num, raw};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Pes3Motion = api;
})(globalThis);
