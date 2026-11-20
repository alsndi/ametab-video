import React from 'react';
import {AbsoluteFill, interpolate, interpolateColors, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// Text that lives *around* the person. Rendered twice with a transparent background:
//   layer "back"  -> composited under the cut-out person (text behind you, back half of an orbit)
//   layer "front" -> composited over the person (front half of an orbit, or text that should sit on top)
// compose.py stacks: video, back layer, person (alpha from matte.py), front layer.

export type DepthItem = {
  mode: 'behind' | 'orbit' | 'rise';
  text: string;
  start: number; // seconds, relative to this clip
  end: number;
  colors?: string[]; // cycles through these; one colour = solid
  y?: number; // behind / rise: vertical centre
  size?: number; // font size px
  // orbit
  cx?: number;
  cy?: number;
  rx?: number;
  ry?: number;
  count?: number; // how many copies of the text sit on the ring
  speed?: number; // turns per second
  tilt?: number; // degrees
  front?: boolean; // behind/rise: draw on the front layer instead
  font?: 'tajawal' | 'ruqaa' | 'kufi' | 'alexandria' | string; // ruqaa = Aref Ruqaa calligraphy
  fill?: 'goldgrad' | 'creamgrad'; // gradient letters instead of cycling colours
};

const FONTS: Record<string, string> = {
  tajawal: "'Tajawal Black', 'Tajawal', 'Cairo', sans-serif",
  ruqaa: "'Aref Ruqaa', 'Amiri', serif",
  kufi: "'Reem Kufi', 'Tajawal', sans-serif",
  alexandria: "'Alexandria', 'Tajawal', sans-serif",
};
const fontOf = (it: DepthItem) => FONTS[it.font ?? 'tajawal'] ?? `'${it.font}', 'Tajawal', sans-serif`;
const GRADS: Record<string, string> = {
  goldgrad: 'linear-gradient(180deg, #FFF1B8 0%, #F2C14E 45%, #B8862B 100%)',
  creamgrad: 'linear-gradient(180deg, #FFFDF5 0%, #F3E6C8 60%, #D9C39A 100%)',
};
const paint = (it: DepthItem, color: string): React.CSSProperties =>
  it.fill && GRADS[it.fill]
    ? {backgroundImage: GRADS[it.fill], WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
       filter: 'drop-shadow(0 8px 24px rgba(0,0,0,0.35))'}
    : {color};

export type DepthProps = {duration: number; layer: 'back' | 'front'; items: DepthItem[]};

const FONT = "'Tajawal Black', 'Tajawal', 'Cairo', sans-serif";
const DEFAULT_COLORS = ['#FFD60A', '#ff3b4a', '#22d3ee', '#a855f7'];

const cycle = (colors: string[], t: number, period = 1.6) => {
  if (colors.length === 1) return colors[0];
  const pos = ((t / period) % 1) * colors.length;
  const i = Math.floor(pos);
  return interpolateColors(pos - i, [0, 1], [colors[i], colors[(i + 1) % colors.length]]);
};

const Behind: React.FC<{it: DepthItem; t: number; fps: number; frame: number}> = ({it, t, fps, frame}) => {
  const local = t - it.start;
  const inn = spring({frame: frame - Math.round(it.start * fps), fps, config: {damping: 14, stiffness: 120}});
  const out = interpolate(t, [it.end - 0.35, it.end], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const colors = it.colors ?? DEFAULT_COLORS;
  const size = it.size ?? 260;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: (it.y ?? 520) - size * 0.6,
        textAlign: 'center',
        direction: 'rtl',
        fontFamily: fontOf(it),
        fontWeight: it.font === 'ruqaa' ? 700 : 900,
        fontSize: size,
        lineHeight: it.font === 'ruqaa' ? 1.5 : 1.1,
        ...paint(it, cycle(colors, local)),
        textShadow: it.fill ? undefined : '0 10px 40px rgba(0,0,0,0.35)',
        transform: `translateY(${(1 - inn) * 260}px) scale(${0.85 + 0.15 * inn})`,
        opacity: Math.min(inn, out),
        whiteSpace: 'nowrap',
      }}
    >
      {it.text}
    </div>
  );
};

const Rise: React.FC<{it: DepthItem; t: number}> = ({it, t}) => {
  // comes up from below, holds, keeps drifting up and fades out
  const d = it.end - it.start;
  const p = (t - it.start) / d;
  const y = interpolate(p, [0, 0.25, 0.75, 1], [420, 0, -40, -360]);
  const op = interpolate(p, [0, 0.2, 0.75, 1], [0, 1, 1, 0]);
  const colors = it.colors ?? DEFAULT_COLORS;
  const size = it.size ?? 150;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: (it.y ?? 700) - size * 0.6,
        textAlign: 'center',
        direction: 'rtl',
        fontFamily: fontOf(it),
        fontWeight: 900,
        fontSize: size,
        color: cycle(colors, t - it.start),
        WebkitTextStroke: `${size / 22}px rgba(0,0,0,0.6)`,
        paintOrder: 'stroke fill',
        transform: `translateY(${y}px)`,
        opacity: op,
        filter: `blur(${interpolate(op, [0, 1], [8, 0])}px)`,
        whiteSpace: 'nowrap',
      }}
    >
      {it.text}
    </div>
  );
};

const Orbit: React.FC<{it: DepthItem; t: number; layer: 'back' | 'front'}> = ({it, t, layer}) => {
  const count = it.count ?? 5;
  const cx = it.cx ?? 540;
  const cy = it.cy ?? 560;
  const rx = it.rx ?? 430;
  const ry = it.ry ?? 110;
  const size = it.size ?? 84;
  const tilt = ((it.tilt ?? -8) * Math.PI) / 180;
  const local = t - it.start;
  const fadeIn = interpolate(local, [0, 0.35], [0, 1], {extrapolateRight: 'clamp'});
  const fadeOut = interpolate(t, [it.end - 0.35, it.end], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const colors = it.colors ?? DEFAULT_COLORS;
  const spin = local * (it.speed ?? 0.35) * Math.PI * 2;
  return (
    <>
      {Array.from({length: count}).map((_, k) => {
        const a = spin + (k / count) * Math.PI * 2;
        const depth = Math.cos(a); // +1 nearest to camera, -1 behind the head
        if ((layer === 'front') !== depth >= 0) return null;
        const x0 = rx * Math.sin(a);
        const y0 = ry * depth;
        const x = cx + x0 * Math.cos(tilt) - y0 * Math.sin(tilt);
        const y = cy + x0 * Math.sin(tilt) + y0 * Math.cos(tilt);
        const scale = 0.62 + 0.38 * (depth + 1) / 2;
        const edge = Math.min(1, Math.abs(Math.sin(a)) < 0.98 ? 1 : 0.6);
        return (
          <div
            key={k}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              transform: `translate(-50%, -50%) scale(${scale}) scaleX(${0.55 + 0.45 * Math.abs(depth)})`,
              direction: 'rtl',
              fontFamily: fontOf(it),
              fontWeight: 900,
              fontSize: size,
              color: cycle(colors, local + k * 0.25),
              WebkitTextStroke: `${size / 20}px rgba(0,0,0,0.55)`,
              paintOrder: 'stroke fill',
              opacity: fadeIn * fadeOut * edge * (0.55 + 0.45 * (depth + 1) / 2),
              whiteSpace: 'nowrap',
            }}
          >
            {it.text}
          </div>
        );
      })}
    </>
  );
};

export const DepthText: React.FC<DepthProps> = ({layer, items}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{backgroundColor: 'transparent'}}>
      {items.map((it, i) => {
        if (t < it.start || t > it.end) return null;
        if (it.mode === 'orbit') return <Orbit key={i} it={it} t={t} layer={layer} />;
        const onFront = !!it.front;
        if ((layer === 'front') !== onFront) return null;
        if (it.mode === 'rise') return <Rise key={i} it={it} t={t} />;
        return <Behind key={i} it={it} t={t} fps={fps} frame={frame} />;
      })}
    </AbsoluteFill>
  );
};
