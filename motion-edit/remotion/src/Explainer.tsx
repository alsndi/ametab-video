import React from 'react';
import {AbsoluteFill, Audio, Img, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

// ---------- types ----------
type Word = {w: string; s: number; e: number; brk?: boolean};
type Tap = {x: number; y: number; at?: number}; // x,y: 0..1 inside the screenshot, at: seconds into the scene

export type Scene =
  | {type: 'title'; start: number; end: number; title: string; highlight?: string; emoji?: string}
  | {type: 'bullets'; start: number; end: number; title?: string; items: string[]}
  | {type: 'number'; start: number; end: number; value: string; label: string; emoji?: string}
  | {type: 'compare'; start: number; end: number; left: {label: string; value: string}; right: {label: string; value: string}}
  | {type: 'phone'; start: number; end: number; image: string; caption?: string; taps?: Tap[]}
  | {type: 'icon'; start: number; end: number; emoji: string; text: string};

export type ExplainerProps = {
  duration: number;
  scenes: Scene[];
  voice?: string;
  words?: Word[];
  music?: string;
  musicVol?: number;
};

const YELLOW = '#FFD60A';
const FONT = "'Tajawal Black', 'Tajawal', 'Cairo', sans-serif";
const stroke = (px: number) => ({WebkitTextStroke: `${px}px #000`, paintOrder: 'stroke fill' as const});
const text = (size: number, extra: React.CSSProperties = {}): React.CSSProperties => ({
  fontFamily: FONT,
  fontWeight: 900,
  fontSize: size,
  color: '#fff',
  direction: 'rtl',
  textAlign: 'center',
  lineHeight: 1.2,
  ...stroke(size / 12),
  textShadow: `0 ${size / 14}px 0 rgba(0,0,0,0.45)`,
  ...extra,
});

// ---------- pieces ----------
const Background: React.FC = () => {
  const f = useCurrentFrame();
  const blob = (i: number) => ({
    position: 'absolute' as const,
    width: 700,
    height: 700,
    borderRadius: '50%',
    filter: 'blur(120px)',
    opacity: 0.55,
    left: 200 + Math.sin(f / 60 + i * 2) * 260 - 350 + i * 300,
    top: 300 + Math.cos(f / 70 + i) * 300 + i * 500,
    background: ['#7c3aed', '#db2777', '#2563eb'][i % 3],
  });
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #12061f 0%, #2a0d52 55%, #0d0418 100%)', overflow: 'hidden'}}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={blob(i)} />
      ))}
    </AbsoluteFill>
  );
};

const useEnter = (delay = 0) => {
  const f = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const inn = spring({frame: f - delay, fps, config: {damping: 13, stiffness: 140}});
  const out = interpolate(f, [durationInFrames - 6, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {inn, out, f, fps};
};

const TitleScene: React.FC<Extract<Scene, {type: 'title'}>> = ({title, highlight, emoji}) => {
  const {inn, out, f} = useEnter();
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingBottom: 560, opacity: out}}>
      {emoji ? <div style={{fontSize: 300, transform: `scale(${inn}) translateY(${Math.sin(f / 9) * 14}px)`}}>{emoji}</div> : null}
      <div style={{...text(140), width: '88%', transform: `translateY(${(1 - inn) * 80}px)`, opacity: inn}}>
        {title} {highlight ? <span style={{color: YELLOW}}>{highlight}</span> : null}
      </div>
    </AbsoluteFill>
  );
};

const BulletsScene: React.FC<Extract<Scene, {type: 'bullets'}>> = ({title, items}) => {
  const {out, f, fps} = useEnter();
  const {durationInFrames} = useVideoConfig();
  const gap = Math.min(18, Math.floor((durationInFrames - 20) / Math.max(1, items.length)));
  return (
    <AbsoluteFill style={{alignItems: 'center', paddingTop: 240, opacity: out}}>
      {title ? <div style={{...text(110), marginBottom: 60}}>{title}</div> : null}
      {items.map((it, i) => {
        const s = spring({frame: f - 6 - i * gap, fps, config: {damping: 14}});
        return (
          <div key={i} style={{display: 'flex', direction: 'rtl', alignItems: 'center', gap: 30, width: '84%', marginBottom: 46, opacity: s, transform: `translateX(${(1 - s) * -120}px)`}}>
            <div style={{flex: '0 0 90px', height: 90, borderRadius: 45, background: YELLOW, border: '6px solid #000', ...text(60, {color: '#000', WebkitTextStroke: '0', textShadow: 'none', lineHeight: '78px'})}}>
              {i + 1}
            </div>
            <div style={text(78, {textAlign: 'right'})}>{it}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const NumberScene: React.FC<Extract<Scene, {type: 'number'}>> = ({value, label, emoji}) => {
  const {inn, out, f, fps} = useEnter();
  const pop = spring({frame: f - 4, fps, config: {damping: 7, stiffness: 160}});
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingBottom: 560, opacity: out}}>
      {emoji ? <div style={{fontSize: 200, marginBottom: 20, transform: `scale(${inn})`}}>{emoji}</div> : null}
      <div style={{...text(300, {color: YELLOW}), transform: `scale(${0.5 + 0.5 * pop})`}}>{value}</div>
      <div style={{...text(90), width: '86%', marginTop: 30, opacity: inn}}>{label}</div>
    </AbsoluteFill>
  );
};

const CompareScene: React.FC<Extract<Scene, {type: 'compare'}>> = ({left, right}) => {
  const {out, f, fps} = useEnter();
  const a = spring({frame: f - 2, fps, config: {damping: 13}});
  const b = spring({frame: f - 12, fps, config: {damping: 13}});
  const card = (s: number, side: {label: string; value: string}, good: boolean, dir: number) => (
    <div
      style={{
        width: 410,
        padding: '50px 16px',
        borderRadius: 48,
        background: good ? 'rgba(52,199,89,0.25)' : 'rgba(255,59,48,0.22)',
        border: `8px solid ${good ? '#34C759' : '#FF3B30'}`,
        transform: `translateX(${(1 - s) * dir * 300}px)`,
        opacity: s,
      }}
    >
      <div style={text(70)}>{side.label}</div>
      <div style={{...text(130, {color: good ? YELLOW : '#fff'}), marginTop: 30}}>{side.value}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{flexDirection: 'row-reverse', alignItems: 'center', justifyContent: 'center', gap: 24, paddingBottom: 560, opacity: out}}>
      {card(a, right, false, 1)}
      <div style={text(72, {color: YELLOW})}>VS</div>
      {card(b, left, true, -1)}
    </AbsoluteFill>
  );
};

const PhoneScene: React.FC<Extract<Scene, {type: 'phone'}>> = ({image, caption, taps = []}) => {
  const {inn, out, f, fps} = useEnter();
  const rotY = interpolate(inn, [0, 1], [-45, -14]) + Math.sin(f / 40) * 3;
  const rotX = 6 + Math.cos(f / 50) * 2;
  const PW = 470;
  const PH = 990;
  return (
    <AbsoluteFill style={{alignItems: 'center', opacity: out, perspective: 2200}}>
      {caption ? <div style={{...text(92), position: 'absolute', top: 130, width: '88%', opacity: inn}}>{caption}</div> : null}
      <div
        style={{
          position: 'absolute',
          top: 330,
          width: PW,
          height: PH,
          borderRadius: 86,
          background: '#0a0a0a',
          border: '14px solid #2b2b2e',
          boxShadow: '0 60px 120px rgba(0,0,0,0.6), inset 0 0 0 3px #555',
          transform: `rotateY(${rotY}deg) rotateX(${rotX}deg) scale(${0.7 + 0.3 * inn})`,
          overflow: 'hidden',
        }}
      >
        <Img src={staticFile(image)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        <div style={{position: 'absolute', top: 18, left: '50%', marginLeft: -80, width: 160, height: 44, borderRadius: 22, background: '#000'}} />
        {taps.map((t, i) => {
          const at = Math.round((t.at ?? 0.8 + i * 0.9) * fps);
          const local = f - at;
          if (local < 0) return null;
          const ring = interpolate(local, [0, 18], [0.3, 2.2], {extrapolateRight: 'clamp'});
          const fade = interpolate(local, [0, 18], [1, 0], {extrapolateRight: 'clamp'});
          const glow = spring({frame: local, fps, config: {damping: 12}});
          return (
            <React.Fragment key={i}>
              <div style={{position: 'absolute', left: `${t.x * 100}%`, top: `${t.y * 100}%`, width: 120, height: 120, marginLeft: -60, marginTop: -60, borderRadius: 60, border: `10px solid ${YELLOW}`, boxShadow: `0 0 40px ${YELLOW}`, transform: `scale(${glow})`}} />
              <div style={{position: 'absolute', left: `${t.x * 100}%`, top: `${t.y * 100}%`, width: 80, height: 80, marginLeft: -40, marginTop: -40, borderRadius: 40, border: '6px solid #fff', transform: `scale(${ring})`, opacity: fade}} />
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const IconScene: React.FC<Extract<Scene, {type: 'icon'}>> = ({emoji, text: t}) => {
  const {inn, out, f} = useEnter();
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingBottom: 560, opacity: out}}>
      <div style={{fontSize: 420, transform: `scale(${inn}) rotate(${Math.sin(f / 12) * 4}deg)`}}>{emoji}</div>
      <div style={{...text(110), width: '86%', marginTop: 40, opacity: inn}}>{t}</div>
    </AbsoluteFill>
  );
};

// ---------- captions (same look as talk-reel: white, spoken words turn yellow) ----------
const chunk = (words: Word[], max = 4, maxSec = 2.0) => {
  const out: Word[][] = [];
  let cur: Word[] = [];
  words.forEach((w, i) => {
    const prev = words[i - 1];
    if (cur.length && (w.brk || cur.length >= max || w.e - cur[0].s > maxSec || (prev && w.s - prev.e > 0.45) || /[.!?؟،,]$/.test(prev?.w ?? ''))) {
      out.push(cur);
      cur = [];
    }
    cur.push(w);
  });
  if (cur.length) out.push(cur);
  return out;
};

const Captions: React.FC<{words: Word[]}> = ({words}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = f / fps;
  const chunks = React.useMemo(() => chunk(words), [words]);
  const idx = chunks.findIndex((c, i) => t >= c[0].s && t < Math.min(c[c.length - 1].e + 0.25, chunks[i + 1]?.[0].s ?? 1e9));
  if (idx < 0) return null;
  const c = chunks[idx];
  return (
    <div style={{position: 'absolute', top: 1380, width: '100%', ...text(92)}}>
      {c.map((w, i) => (
        <span key={i} style={{color: t >= w.s ? YELLOW : '#fff'}}>
          {w.w}
          {i < c.length - 1 ? ' ' : ''}
        </span>
      ))}
    </div>
  );
};

const SceneView: React.FC<{scene: Scene}> = ({scene}) => {
  switch (scene.type) {
    case 'title':
      return <TitleScene {...scene} />;
    case 'bullets':
      return <BulletsScene {...scene} />;
    case 'number':
      return <NumberScene {...scene} />;
    case 'compare':
      return <CompareScene {...scene} />;
    case 'phone':
      return <PhoneScene {...scene} />;
    case 'icon':
      return <IconScene {...scene} />;
  }
};

export const Explainer: React.FC<ExplainerProps> = ({scenes, voice, words, music, musicVol = 0.15}) => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill>
      <Background />
      {scenes.map((s, i) => (
        <Sequence key={i} from={Math.round(s.start * fps)} durationInFrames={Math.max(1, Math.round((s.end - s.start) * fps))}>
          <SceneView scene={s} />
        </Sequence>
      ))}
      {words?.length ? <Captions words={words} /> : null}
      {voice ? <Audio src={staticFile(voice)} /> : null}
      {music ? <Audio src={staticFile(music)} volume={musicVol} /> : null}
    </AbsoluteFill>
  );
};
