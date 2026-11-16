/**
 * GLSL for the Cognitive Atlas.
 *
 * Conventions shared by every program:
 *   - colours arrive in display space and are written out raw (no tone mapping),
 *   - everything is additive and premultiplied (blend ONE, ONE) with depth
 *     testing off, so overlapping light accumulates into a soft bloom without a
 *     post-processing pass,
 *   - `uFocusDist` is the camera's distance to its target: geometry in front of
 *     it reads brighter, geometry behind recedes — cheap depth of field,
 *   - two clocks: `uTime` always runs and drives responses to events (a memory
 *     arriving, a recall hop); `uFlow` drives ambient life (twinkle, drift,
 *     travelling packets) and stops when motion is paused or reduced,
 *   - `uAsOf` is the growth-timeline marker (0–1). With `uTimeline` on, anything
 *     the marker has just passed flares, so scrubbing visibly grows the graph.
 */

const DEPTH = /* glsl */ `
float depthGain(float dist, float focusDist) {
  return clamp(1.1 - (dist - focusDist) * 0.46, 0.24, 1.3);
}
`;

/* ------------------------------------------------------------------ cortex */

export const CORTEX_VERT = /* glsl */ `
uniform float uTime;
uniform float uFlow;
uniform float uForm;
uniform float uAsOf;
uniform float uTimeline;
uniform float uDim;
uniform float uCortexDim;
uniform float uMotion;
uniform float uBreath;
uniform float uScale;
uniform float uGain;
uniform float uFocusDist;
uniform float uRegionFocus;
uniform float uRegionGlow[8];
uniform vec4 uWave[4];
uniform float uWaveGain[4];
attribute vec3 aScatter;
attribute vec3 aColor;
attribute float aRegion;
attribute float aSeed;
attribute float aSize;
attribute float aBorn;
attribute float aBirth;
varying vec3 vColor;
varying float vAlpha;
${DEPTH}
void main() {
  // assembly: a sweep from the front of the brain to the back, each particle
  // spiralling in from a wide shell
  float sweep = aSeed * 0.5 + (0.5 - position.x * 0.16);
  float f = clamp((uForm * 2.1 - sweep) / 0.8, 0.0, 1.0);
  f = f * f * (3.0 - 2.0 * f);
  vec3 p = mix(aScatter, position, f);
  float swirl = (1.0 - f) * 1.9;
  float cs = cos(swirl);
  float sn = sin(swirl);
  p.xz = mat2(cs, -sn, sn, cs) * p.xz;

  float ph = aSeed * 6.2831853;
  float drift = aRegion > 6.5 ? 7.0 : 1.0;
  p += uMotion * 0.011 * drift * vec3(
    sin(uFlow * 0.55 + ph * 3.0),
    cos(uFlow * 0.47 + ph * 5.0),
    sin(uFlow * 0.61 + ph * 7.0));
  p *= 1.0 + uBreath;

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float dist = -mv.z;

  // the oldest tissue (born 0) is already there at the very start of the timeline
  float vis = smoothstep(aBorn - 0.03, aBorn + 0.01, uAsOf) * smoothstep(0.0, 1.8, uTime - aBirth);
  float glow = uRegionGlow[int(aRegion + 0.5)];
  // tissue the timeline marker has just reached
  float fresh = uTimeline * step(aBorn, uAsOf) * (1.0 - smoothstep(0.0, 0.07, uAsOf - aBorn));

  // activation fronts expanding through the tissue
  float wave = 0.0;
  for (int i = 0; i < 4; i++) {
    float age = uTime - uWave[i].w;
    if (age > 0.0 && age < 3.0) {
      float d = distance(position, uWave[i].xyz);
      wave += smoothstep(0.2, 0.0, abs(d - age * 0.85)) * exp(-age * 1.5) * uWaveGain[i];
    }
  }

  float twinkle = 0.78 + 0.22 * sin(uFlow * (0.7 + aSeed * 2.4) + ph * 11.0);
  float inFocus = (uRegionFocus < -0.5 || abs(aRegion - uRegionFocus) < 0.5) ? 1.0 : 0.0;
  float dim = mix(1.0, mix(0.16, 1.0, inFocus), uDim) * (1.0 - 0.58 * uCortexDim);
  float depth = depthGain(dist, uFocusDist);
  float energy = (0.8 + glow + wave * 1.8 + fresh * 0.9) * twinkle * dim * depth * uGain;

  vColor = aColor * energy + vec3(1.0, 0.9, 0.93) * wave * 0.2 * depth * dim;
  float coc = abs(dist - uFocusDist);
  float size = aSize * (1.0 + glow * 0.3 + wave * 0.7 + fresh * 0.5) * (1.0 + coc * 0.2);
  gl_PointSize = max(size * uScale / dist, 1.6);
  vAlpha = vis * mix(0.3, 1.0, f);
  gl_Position = projectionMatrix * mv;
}
`;

export const CORTEX_FRAG = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d2 = dot(c, c) * 4.0;
  if (d2 > 1.0) discard;
  float a = (exp(-d2 * 7.0) + exp(-d2 * 2.0) * 0.26) * vAlpha;
  gl_FragColor = vec4(vColor * a, a);
}
`;

/* ------------------------------------------------------------ memory nodes */

export const NODE_VERT = /* glsl */ `
uniform float uTime;
uniform float uFlow;
uniform float uForm;
uniform float uAsOf;
uniform float uTimeline;
uniform float uDim;
uniform float uBreath;
uniform float uScale;
uniform float uGain;
uniform float uFocusDist;
attribute vec3 aColor;
attribute float aSeed;
attribute float aSize;
attribute float aBorn;
attribute float aBirth;
attribute float aPulse;
attribute float aState;
varying vec3 vColor;
varying float vEnergy;
varying float vAlpha;
varying float vPulse;
varying float vState;
varying float vArrive;
${DEPTH}
void main() {
  vec4 mv = modelViewMatrix * vec4(position * (1.0 + uBreath), 1.0);
  float dist = -mv.z;

  float appear = smoothstep(aBorn, aBorn + 0.02, uAsOf);
  float bt = uTime - aBirth;
  // a memory that just arrived swells in with a small overshoot
  float grow = bt <= 0.0 ? 0.0 : (bt > 1.4 ? 1.0 : (1.0 - pow(1.0 - bt / 1.4, 3.0)) * (1.0 + 0.5 * sin(bt * 6.0) * exp(-bt * 3.0)));
  float form = smoothstep(0.55, 1.0, uForm + aSeed * 0.2);

  // 0 → 1 as the timeline marker moves on from this memory; -1 when not arriving
  float past = (uAsOf - aBorn) / 0.06;
  vArrive = (uTimeline > 0.5 && past >= 0.0 && past < 1.0) ? past : -1.0;
  float arriving = vArrive >= 0.0 ? 1.0 - vArrive : 0.0;

  float pulseAge = uTime - aPulse;
  float flare = (pulseAge > 0.0 ? exp(-pulseAge * 1.7) : 0.0) + arriving * 0.9;
  float primary = aState > 1.5 ? 1.0 : 0.0;
  float dim = mix(1.0, aState > 0.5 ? 1.0 : 0.14, uDim);
  float breathe = 0.8 + 0.2 * sin(uFlow * (0.8 + aSeed) + aSeed * 40.0);

  vEnergy = (breathe + flare * 1.7 + primary * 0.6) * dim * depthGain(dist, uFocusDist) * uGain;
  vColor = aColor;
  vPulse = pulseAge;
  vState = aState;
  vAlpha = appear * form;

  float size = aSize * grow * appear * form * (1.0 + flare * 0.45 + primary * 0.3);
  // the sprite is 5x the core so halo and pulse rings have room
  gl_PointSize = clamp(size * 5.0 * uScale / dist, 0.0, 480.0);
  gl_Position = projectionMatrix * mv;
}
`;

export const NODE_FRAG = /* glsl */ `
varying vec3 vColor;
varying float vEnergy;
varying float vAlpha;
varying float vPulse;
varying float vState;
varying float vArrive;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float core = smoothstep(0.23, 0.13, d);
  float hot = smoothstep(0.15, 0.0, d);
  float halo = exp(-d * d * 7.5) * 0.6;
  float edge = smoothstep(1.0, 0.86, d);
  float ring = 0.0;
  if (vPulse > 0.0 && vPulse < 1.7) {
    float r = 0.22 + vPulse * 0.44;
    ring = smoothstep(0.045, 0.0, abs(d - r)) * (1.0 - vPulse / 1.7) * edge;
  }
  if (vArrive >= 0.0) {
    float r = 0.22 + vArrive * 0.7;
    ring += smoothstep(0.045, 0.0, abs(d - r)) * (1.0 - vArrive) * edge;
  }
  float chosen = vState > 1.5 ? smoothstep(0.03, 0.0, abs(d - 0.36)) * 0.7 : 0.0;
  vec3 col = vColor * (core * 0.85 + halo + ring * 1.3)
           + vec3(1.0, 0.95, 0.96) * (hot * 0.75 + chosen * 0.6);
  float a = clamp(core * 0.9 + halo * 0.5 + ring + chosen, 0.0, 1.0) * vAlpha;
  gl_FragColor = vec4(col * vEnergy * vAlpha, a * min(vEnergy, 1.0));
}
`;

/* ---------------------------------------------------------------- pathways */

/** How far behind the timeline marker a pathway finishes drawing itself. */
const DRAW = "0.045";

export const PATH_VERT = /* glsl */ `
uniform float uTime;
uniform float uForm;
uniform float uAsOf;
uniform float uTimeline;
uniform float uDim;
uniform float uBreath;
uniform float uGain;
uniform float uPathGain;
uniform float uFocusDist;
attribute vec3 aColor;
attribute float aT;
attribute float aSeed;
attribute float aBorn;
attribute float aBirth;
attribute float aState;
attribute float aStrength;
varying vec3 vColor;
varying float vT;
varying float vSeed;
varying float vReveal;
varying float vEnergy;
${DEPTH}
void main() {
  vec4 mv = modelViewMatrix * vec4(position * (1.0 + uBreath), 1.0);
  float appear = smoothstep(aBorn, aBorn + 0.02, uAsOf) * smoothstep(0.82, 1.0, uForm);
  float lit = aState > 0.5 ? 1.0 : 0.0;
  float dim = mix(1.0, mix(0.1, 1.0, lit), uDim);
  vColor = aColor;
  vT = aT;
  vSeed = aSeed;
  // a pathway draws itself on: when it forms live, or as the timeline reaches it
  float drawn = mix(10.0, (uAsOf - aBorn) / ${DRAW}, uTimeline);
  vReveal = min((uTime - aBirth) / 1.1, drawn);
  // a focused pathway is always shown, even when ambient pathways are hidden
  float shown = max(uPathGain, lit);
  vEnergy = aStrength * appear * dim * shown * (1.0 + lit * 5.5) * depthGain(-mv.z, uFocusDist) * uGain;
  gl_Position = projectionMatrix * mv;
}
`;

export const PATH_FRAG = /* glsl */ `
uniform float uFlow;
varying vec3 vColor;
varying float vT;
varying float vSeed;
varying float vReveal;
varying float vEnergy;
void main() {
  if (vT > vReveal) discard;
  // a packet of light travelling source -> target
  float ph = fract(vT - uFlow * (0.09 + vSeed * 0.1) + vSeed * 7.0);
  float pulse = exp(-pow((ph - 0.5) * 9.0, 2.0));
  float head = vReveal < 1.3 ? exp(-pow((vT - vReveal) * 12.0, 2.0)) * 2.4 : 0.0;
  float a = (0.075 + pulse * 0.7 + head) * vEnergy;
  gl_FragColor = vec4(vColor * a, a * 0.6);
}
`;

/** The bright packet that rides each pathway — same phase as PATH_FRAG's pulse. */
export const PACKET_VERT = /* glsl */ `
uniform float uTime;
uniform float uFlow;
uniform float uForm;
uniform float uAsOf;
uniform float uTimeline;
uniform float uDim;
uniform float uBreath;
uniform float uScale;
uniform float uGain;
uniform float uPathGain;
uniform float uFocusDist;
attribute vec3 aP1;
attribute vec3 aP2;
attribute vec3 aColor;
attribute float aSeed;
attribute float aBorn;
attribute float aBirth;
attribute float aState;
attribute float aStrength;
varying vec3 vColor;
varying float vAlpha;
${DEPTH}
void main() {
  float t = fract(0.5 + uFlow * (0.09 + aSeed * 0.1) - aSeed * 7.0);
  float k = 1.0 - t;
  vec3 p = (k * k * position + 2.0 * k * t * aP1 + t * t * aP2) * (1.0 + uBreath);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float dist = -mv.z;
  float drawn = mix(10.0, (uAsOf - aBorn) / ${DRAW}, uTimeline);
  float appear = smoothstep(aBorn, aBorn + 0.02, uAsOf) * smoothstep(0.9, 1.0, uForm)
               * step(1.1, uTime - aBirth) * step(1.0, drawn);
  float lit = aState > 0.5 ? 1.0 : 0.0;
  float dim = mix(1.0, mix(0.08, 1.0, lit), uDim);
  float ends = smoothstep(0.0, 0.08, t) * smoothstep(1.0, 0.92, t);
  vColor = mix(aColor, vec3(1.0, 0.95, 0.96), 0.45);
  vAlpha = appear * dim * ends * max(uPathGain, lit) * uGain
         * (0.55 + aStrength * 0.6 + lit * 0.8) * depthGain(dist, uFocusDist);
  gl_PointSize = max((0.03 + lit * 0.02) * uScale / dist, 1.5);
  gl_Position = projectionMatrix * mv;
}
`;

export const PACKET_FRAG = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float a = (exp(-d * d * 9.0) + exp(-d * d * 2.5) * 0.3) * vAlpha;
  gl_FragColor = vec4(vColor * a, a * 0.6);
}
`;

/* ------------------------------------------------------------- recall path */

export const TRACE_VERT = /* glsl */ `
uniform float uBreath;
varying float vU;
void main() {
  vU = uv.x;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position * (1.0 + uBreath), 1.0);
}
`;

export const TRACE_FRAG = /* glsl */ `
uniform float uTime;
uniform float uFlow;
uniform float uStart;
uniform float uGain;
uniform vec3 uColorA;
uniform vec3 uColorB;
varying float vU;
void main() {
  float reveal = (uTime - uStart) / 0.75;
  if (vU > reveal) discard;
  float head = reveal < 1.2 ? exp(-pow((vU - reveal) * 8.0, 2.0)) : 0.0;
  float flow = 0.5 + 0.5 * sin(vU * 11.0 - uFlow * 3.4);
  vec3 col = mix(mix(uColorA, uColorB, vU), vec3(1.0, 0.95, 0.96), 0.3 + head * 0.5);
  float a = uGain * (0.5 + 0.4 * flow + head * 1.8);
  gl_FragColor = vec4(col * a, a);
}
`;

/* ----------------------------------------------------------------- reticle */

export const RETICLE_VERT = /* glsl */ `
uniform float uBreath;
uniform float uScale;
attribute float aSize;
attribute float aKind;
varying float vKind;
void main() {
  vec4 mv = modelViewMatrix * vec4(position * (1.0 + uBreath), 1.0);
  vKind = aKind;
  gl_PointSize = clamp(aSize * uScale / -mv.z, 0.0, 420.0);
  gl_Position = projectionMatrix * mv;
}
`;

export const RETICLE_FRAG = /* glsl */ `
uniform float uFlow;
varying float vKind;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c) * 2.0;
  if (d > 1.0 || vKind < 0.5) discard;
  float ang = atan(c.y, c.x);
  float a;
  if (vKind > 1.5) {
    // selected: a slow rotating bracket plus a fine inner ring
    float arcs = smoothstep(0.2, 0.5, sin(ang * 2.0 + uFlow * 0.7));
    a = smoothstep(0.035, 0.0, abs(d - 0.86)) * arcs + smoothstep(0.02, 0.0, abs(d - 0.66)) * 0.35;
  } else {
    // hovered: a quiet dashed ring
    float dashes = smoothstep(-0.2, 0.3, sin(ang * 10.0 - uFlow * 1.4));
    a = smoothstep(0.04, 0.0, abs(d - 0.8)) * dashes * 0.75;
  }
  gl_FragColor = vec4(vec3(1.0, 0.9, 0.93) * a, a);
}
`;

/* ---------------------------------------------------------- core + platform */

export const GLOW_VERT = /* glsl */ `
uniform float uFlow;
uniform float uForm;
uniform float uScale;
uniform float uBreath;
uniform float uMotion;
uniform float uGain;
varying float vBeat;
void main() {
  vec4 mv = modelViewMatrix * vec4(position * (1.0 + uBreath), 1.0);
  // two-stroke heartbeat
  float t = fract(uFlow * 0.42);
  vBeat = (0.72 + uMotion * (0.28 * exp(-t * 7.0) + 0.16 * exp(-pow((t - 0.2) * 9.0, 2.0)))) * uForm * uGain;
  gl_PointSize = clamp(1.9 * uScale / -mv.z, 0.0, 900.0);
  gl_Position = projectionMatrix * mv;
}
`;

export const GLOW_FRAG = /* glsl */ `
uniform vec3 uColor;
varying float vBeat;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float a = (exp(-d * d * 5.0) * 0.16 + exp(-d * d * 40.0) * 0.2) * vBeat;
  gl_FragColor = vec4(uColor * a, a * 0.5);
}
`;

export const RING_VERT = /* glsl */ `
uniform float uFlow;
uniform float uForm;
uniform float uScale;
uniform float uFocusDist;
attribute float aAngle;
attribute float aRadius;
attribute float aSeed;
varying float vAlpha;
void main() {
  float dir = aRadius > 2.2 ? -1.0 : 1.0;
  float ang = aAngle + uFlow * 0.035 * dir;
  vec3 p = vec3(cos(ang) * aRadius - 0.1, -1.78, sin(ang) * aRadius);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float dist = -mv.z;
  float tick = step(0.92, aSeed);
  vAlpha = (0.2 + tick * 0.5) * clamp(1.0 - (dist - uFocusDist) * 0.3, 0.2, 1.0) * smoothstep(0.6, 1.0, uForm);
  gl_PointSize = max((0.016 + tick * 0.02) * uScale / dist, 1.2);
  gl_Position = projectionMatrix * mv;
}
`;

export const RING_FRAG = /* glsl */ `
uniform vec3 uColor;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float a = exp(-d * d * 4.0) * vAlpha;
  gl_FragColor = vec4(uColor * a, a * 0.5);
}
`;
