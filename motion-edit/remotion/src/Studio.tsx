import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// Ametab "studio" look: dark rounded cards, one accent colour per topic, boxed captions,
// split screen (card on top, face below), picture-in-picture, thin progress bar.

type Word = {w: string; s: number; e: number; brk?: boolean};

export type Card =
  | {type: 'list'; n: number; total: number; title: string; emoji?: string; image?: string}
  | {type: 'checklist'; title: string; items: string[]; at?: number[]}
  | {type: 'score'; label?: string; home: {name: string; score: number | string; logo?: string}; away: {name: string; score: number | string; logo?: string}}
  | {type: 'person'; image: string; label: string; name?: string}
  | {type: 'table'; title: string; rows: string[][]; highlight?: number}
  | {type: 'image'; image: string; caption?: string}
  | {type: 'text'; title: string; highlight?: string; sub?: string; emoji?: string};

export type Beat = {start: number; end: number; layout: 'full' | 'split' | 'pip'; card?: Card; zoom?: number};

export type StudioProps = {
  duration: number;
  video: string; // in public/
  audio?: string; // in public/ (extracted from the video by build.py)
  faceY?: number; // 0..1 face centre in the source, for split / pip crops
  accent?: string;
  words?: Word[];
  keywords?: string[]; // words that get the accent box in captions
  beats: Beat[];
  progress?: boolean;
  rec?: number; // seconds of REC frame at the start (0 = off)
  sfx?: {src: string; at: number; vol: number}[];
  music?: string;
  musicVol?: number;
};

const FONT = "'Tajawal', 'Tajawal Black', 'Cairo', sans-serif";
const BG = '#0b0b10';
const PANEL = '#15161d';
const W = 1080;
const H = 1920;

const rgba = (hex: string, a: number) => {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

const AccentCtx = React.createContext('#ff3b4a');
const useAccent = () => React.useContext(AccentCtx);

// ---------------- face video ----------------
const Face: React.FC<{video: string; from: number; faceY: number; height: number; zoom?: number}> = ({video, from, faceY, height, zoom = 1}) => {
  const {fps} = useVideoConfig();
  // full frame: zoom in keeping the upper third (face) in place; band: show the strip around the face
  const top = height >= H ? (H * zoom - H) * 0.3 : Math.max(0, Math.min(H * zoom - height, faceY * H * zoom - height * 0.45));
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      <OffthreadVideo
        src={staticFile(video)}
        trimBefore={Math.round(from * fps)}
        muted
        style={{position: 'absolute', left: -(W * zoom - W) / 2, top: -top, width: W * zoom, height: H * zoom, objectFit: 'cover'}}
      />
    </div>
  );
};

// ---------------- card pieces ----------------
const Panel: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => {
  const accent = useAccent();
  return (
    <div
      style={{
        background: PANEL,
        borderRadius: 40,
        border: '2px solid rgba(255,255,255,0.08)',
        boxShadow: `0 30px 80px rgba(0,0,0,0.5), 0 0 0 1px ${rgba(accent, 0.12)}`,
        padding: 40,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

const T: React.FC<{size: number; color?: string; children: React.ReactNode; style?: React.CSSProperties}> = ({size, color = '#fff', children, style}) => (
  <div style={{fontFamily: FONT, fontWeight: 900, fontSize: size, color, direction: 'rtl', lineHeight: 1.25, ...style}}>{children}</div>
);

const useIn = (delay = 0) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: f - delay, fps, config: {damping: 14, stiffness: 150}});
};

const ListCard: React.FC<Extract<Card, {type: 'list'}>> = ({n, total, title, emoji, image}) => {
  const accent = useAccent();
  const a = useIn();
  const b = useIn(5);
  const f = useCurrentFrame();
  return (
    <div style={{width: 860, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      <div style={{display: 'flex', width: '100%', alignItems: 'center', gap: 10, direction: 'rtl'}}>
        <div style={{background: accent, borderRadius: 18, width: 96, height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${a})`}}>
          <T size={68} color="#06140b">{n}</T>
        </div>
        <T size={34} color="rgba(255,255,255,0.45)">/{total}</T>
        <div style={{flex: 1, display: 'flex', gap: 8, marginRight: 20}}>
          {Array.from({length: total}).map((_, i) => (
            <div key={i} style={{flex: 1, height: 8, borderRadius: 4, background: i < n ? accent : 'rgba(255,255,255,0.12)'}} />
          ))}
        </div>
      </div>
      <T size={64} style={{marginTop: 30, opacity: b, transform: `translateY(${(1 - b) * 30}px)`, textAlign: 'center'}}>{title}</T>
      {image ? (
        <Img src={staticFile(image)} style={{marginTop: 30, width: 420, height: 420, objectFit: 'contain', transform: `scale(${b})`}} />
      ) : emoji ? (
        <div style={{marginTop: 20, fontSize: 260, transform: `scale(${b}) translateY(${Math.sin(f / 10) * 8}px)`}}>{emoji}</div>
      ) : null}
    </div>
  );
};

const ChecklistCard: React.FC<Extract<Card, {type: 'checklist'}>> = ({title, items, at}) => {
  const accent = useAccent();
  const f = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const step = (durationInFrames - 15) / Math.max(1, items.length);
  return (
    <div style={{width: 880}}>
      <T size={70} style={{textAlign: 'right', marginBottom: 34}}>
        {title}
      </T>
      {items.map((it, i) => {
        const t = at?.[i] !== undefined ? Math.round(at[i] * fps) : Math.round(10 + i * step);
        const done = spring({frame: f - t, fps, config: {damping: 12, stiffness: 180}});
        const active = f >= t && f < t + step;
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              direction: 'rtl',
              alignItems: 'center',
              gap: 24,
              padding: '16px 22px',
              marginBottom: 14,
              borderRadius: 22,
              background: active ? rgba(accent, 0.16) : 'transparent',
              border: `2px solid ${active ? rgba(accent, 0.5) : 'transparent'}`,
            }}
          >
            <div
              style={{
                width: 58,
                height: 58,
                borderRadius: 29,
                flex: '0 0 58px',
                border: `4px solid ${done > 0.05 ? accent : 'rgba(255,255,255,0.25)'}`,
                background: rgba(accent, done),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="30" height="30" viewBox="0 0 24 24" style={{transform: `scale(${done})`}}>
                <path d="M4 12.5l5 5L20 6.5" stroke="#06140b" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <T size={46} color={done > 0.5 ? '#fff' : 'rgba(255,255,255,0.45)'}>
              {it}
            </T>
          </div>
        );
      })}
    </div>
  );
};

const ScoreCard: React.FC<Extract<Card, {type: 'score'}>> = ({label, home, away}) => {
  const accent = useAccent();
  const a = useIn();
  const team = (t: {name: string; score: number | string; logo?: string}, delay: number) => {
    const s = useIn(delay);
    return (
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 260, opacity: s}}>
        {t.logo ? <Img src={staticFile(t.logo)} style={{width: 150, height: 150, objectFit: 'contain'}} /> : <div style={{width: 150, height: 150}} />}
        <T size={40} style={{marginTop: 14, textAlign: 'center'}}>{t.name}</T>
      </div>
    );
  };
  return (
    <Panel style={{width: 900, display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `scale(${0.9 + 0.1 * a})`, opacity: a}}>
      {label ? (
        <div style={{background: accent, borderRadius: 16, padding: '6px 22px', marginBottom: 26}}>
          <T size={34} color="#06121a">{label}</T>
        </div>
      ) : null}
      <div style={{display: 'flex', direction: 'rtl', alignItems: 'center', justifyContent: 'space-between', width: '100%'}}>
        {team(home, 4)}
        <T size={130} style={{direction: 'ltr', whiteSpace: 'nowrap'}}>
          <span style={{color: accent}}>{home.score}</span> - {away.score}
        </T>
        {team(away, 8)}
      </div>
    </Panel>
  );
};

const PersonCard: React.FC<Extract<Card, {type: 'person'}>> = ({image, label, name}) => {
  const accent = useAccent();
  const a = useIn();
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `scale(${0.85 + 0.15 * a})`, opacity: a}}>
      <div style={{width: 520, height: 640, borderRadius: 40, overflow: 'hidden', border: `6px solid ${accent}`, boxShadow: `0 0 60px ${rgba(accent, 0.35)}`}}>
        <Img src={staticFile(image)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 20%'}} />
      </div>
      {name ? <T size={44} style={{marginTop: 18}}>{name}</T> : null}
      <div style={{marginTop: 18, background: accent, borderRadius: 18, padding: '8px 30px'}}>
        <T size={46} color="#fff" style={{textShadow: '0 2px 0 rgba(0,0,0,0.3)'}}>{label}</T>
      </div>
    </div>
  );
};

const TableCard: React.FC<Extract<Card, {type: 'table'}>> = ({title, rows, highlight}) => {
  const accent = useAccent();
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Panel style={{width: 900}}>
      <T size={54} style={{textAlign: 'center', marginBottom: 26}}>{title}</T>
      {rows.map((r, i) => {
        const s = spring({frame: f - 4 - i * 4, fps, config: {damping: 15}});
        const hi = i === highlight;
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              direction: 'rtl',
              justifyContent: 'space-between',
              padding: '18px 24px',
              marginBottom: 10,
              borderRadius: 18,
              background: hi ? accent : 'rgba(255,255,255,0.05)',
              opacity: s,
              transform: `translateX(${(1 - s) * -60}px)`,
            }}
          >
            {r.map((c, j) => (
              <T key={j} size={40} color={hi ? '#fff' : j === 0 ? '#fff' : 'rgba(255,255,255,0.75)'}>
                {c}
              </T>
            ))}
          </div>
        );
      })}
    </Panel>
  );
};

const ImageCard: React.FC<Extract<Card, {type: 'image'}>> = ({image, caption}) => {
  const accent = useAccent();
  const a = useIn();
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: a, transform: `scale(${0.9 + 0.1 * a})`}}>
      <div style={{borderRadius: 34, overflow: 'hidden', border: `4px solid ${rgba(accent, 0.6)}`, boxShadow: `0 0 50px ${rgba(accent, 0.25)}`, maxWidth: 900}}>
        <Img src={staticFile(image)} style={{display: 'block', maxWidth: 900, maxHeight: 700, objectFit: 'contain'}} />
      </div>
      {caption ? <T size={48} style={{marginTop: 24, textAlign: 'center'}}>{caption}</T> : null}
    </div>
  );
};

const TextCard: React.FC<Extract<Card, {type: 'text'}>> = ({title, highlight, sub, emoji}) => {
  const accent = useAccent();
  const a = useIn();
  const b = useIn(6);
  return (
    <div style={{width: 900, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center'}}>
      {emoji ? <div style={{fontSize: 200, transform: `scale(${a})`}}>{emoji}</div> : null}
      <T size={96} style={{textAlign: 'center', opacity: a, transform: `translateY(${(1 - a) * 40}px)`}}>
        {title}{' '}
        {highlight ? (
          <span style={{background: accent, borderRadius: 20, padding: '0 18px', display: 'inline-block', transform: `scale(${0.6 + 0.4 * b})`}}>{highlight}</span>
        ) : null}
      </T>
      {sub ? <T size={46} color="rgba(255,255,255,0.7)" style={{marginTop: 20, opacity: b, textAlign: 'center'}}>{sub}</T> : null}
    </div>
  );
};

const CardView: React.FC<{card: Card}> = ({card}) => {
  switch (card.type) {
    case 'list':
      return <ListCard {...card} />;
    case 'checklist':
      return <ChecklistCard {...card} />;
    case 'score':
      return <ScoreCard {...card} />;
    case 'person':
      return <PersonCard {...card} />;
    case 'table':
      return <TableCard {...card} />;
    case 'image':
      return <ImageCard {...card} />;
    case 'text':
      return <TextCard {...card} />;
  }
};

// ---------------- backgrounds / overlays ----------------
const Stage: React.FC<{children?: React.ReactNode}> = ({children}) => {
  const accent = useAccent();
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.035) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,0.035) 2px, transparent 2px)',
          backgroundSize: '90px 90px',
          backgroundPosition: `0 ${(f * 0.6) % 90}px`,
        }}
      />
      <div style={{position: 'absolute', left: 140, top: 160, width: 800, height: 800, borderRadius: '50%', background: rgba(accent, 0.16), filter: 'blur(140px)'}} />
      {children}
    </AbsoluteFill>
  );
};

const Rec: React.FC = () => {
  const f = useCurrentFrame();
  const c = (pos: React.CSSProperties, b: React.CSSProperties) => (
    <div style={{position: 'absolute', width: 90, height: 90, borderColor: '#22c55e', borderStyle: 'solid', borderWidth: 0, ...pos, ...b}} />
  );
  return (
    <AbsoluteFill>
      {c({left: 50, top: 70}, {borderTopWidth: 8, borderLeftWidth: 8})}
      {c({right: 50, top: 70}, {borderTopWidth: 8, borderRightWidth: 8})}
      {c({left: 50, bottom: 70}, {borderBottomWidth: 8, borderLeftWidth: 8})}
      {c({right: 50, bottom: 70}, {borderBottomWidth: 8, borderRightWidth: 8})}
      <div style={{position: 'absolute', left: 80, top: 100, display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(0,0,0,0.6)', borderRadius: 30, padding: '8px 20px'}}>
        <div style={{width: 22, height: 22, borderRadius: 11, background: '#ef4444', opacity: Math.floor(f / 15) % 2 ? 0.3 : 1}} />
        <div style={{fontFamily: 'Arial', fontWeight: 900, fontSize: 30, color: '#fff'}}>REC</div>
      </div>
    </AbsoluteFill>
  );
};

const Progress: React.FC = () => {
  const accent = useAccent();
  const f = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 10, background: 'rgba(255,255,255,0.12)'}}>
      <div style={{position: 'absolute', right: 0, top: 0, bottom: 0, width: `${(f / durationInFrames) * 100}%`, background: accent}} />
    </div>
  );
};

// ---------------- captions: dark rounded box, spoken word in accent, keywords on an accent pill ----------------
const chunkWords = (words: Word[], max = 5, maxSec = 2.4) => {
  const out: Word[][] = [];
  let cur: Word[] = [];
  words.forEach((w, i) => {
    const prev = words[i - 1];
    if (cur.length && (w.brk || cur.length >= max || w.e - cur[0].s > maxSec || (prev && w.s - prev.e > 0.5) || /[.!?؟،,]$/.test(prev?.w ?? ''))) {
      out.push(cur);
      cur = [];
    }
    cur.push(w);
  });
  if (cur.length) out.push(cur);
  return out;
};

const Captions: React.FC<{words: Word[]; keywords: string[]; y: number}> = ({words, keywords, y}) => {
  const accent = useAccent();
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = f / fps;
  const chunks = React.useMemo(() => chunkWords(words), [words]);
  const idx = chunks.findIndex((c, i) => t >= c[0].s - 0.05 && t < Math.min(c[c.length - 1].e + 0.3, chunks[i + 1]?.[0].s ?? 1e9));
  if (idx < 0) return null;
  const c = chunks[idx];
  const pop = spring({frame: f - Math.round(c[0].s * fps), fps, config: {damping: 14, stiffness: 220}});
  const clean = (s: string) => s.replace(/[.,،!?؟]/g, '');
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: y, display: 'flex', justifyContent: 'center', transform: `translateY(-50%) scale(${0.92 + 0.08 * pop})`}}>
      <div
        style={{
          maxWidth: 900,
          background: 'rgba(12,12,16,0.88)',
          border: '2px solid rgba(255,255,255,0.08)',
          borderRadius: 26,
          padding: '14px 30px 18px',
          direction: 'rtl',
          textAlign: 'center',
          fontFamily: FONT,
          fontWeight: 900,
          fontSize: 54,
          lineHeight: 1.45,
          color: '#fff',
          boxShadow: '0 12px 30px rgba(0,0,0,0.45)',
        }}
      >
        {c.map((w, i) => {
          const key = keywords.includes(clean(w.w));
          const said = t >= w.s;
          return (
            <React.Fragment key={i}>
              <span
                style={
                  key
                    ? {background: accent, color: '#fff', borderRadius: 12, padding: '0 10px'}
                    : {color: said && t < w.e + 0.15 ? accent : '#fff'}
                }
              >
                {w.w}
              </span>
              {i < c.length - 1 ? ' ' : ''}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

// ---------------- one beat ----------------
const BeatView: React.FC<{beat: Beat; video: string; faceY: number}> = ({beat, video, faceY}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: f, fps, config: {damping: 16, stiffness: 160}});
  if (beat.layout === 'full' || !beat.card) {
    return (
      <AbsoluteFill>
        <Face video={video} from={beat.start} faceY={0.5} height={H} zoom={beat.zoom ?? 1} />
      </AbsoluteFill>
    );
  }
  if (beat.layout === 'split') {
    return (
      <AbsoluteFill>
        <div style={{position: 'absolute', left: 0, top: 0, width: W, height: 1000, overflow: 'hidden'}}>
          <Stage>
            <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', transform: `translateY(${(1 - enter) * -60}px)`, opacity: enter}}>
              <CardView card={beat.card} />
            </AbsoluteFill>
          </Stage>
        </div>
        <div style={{position: 'absolute', left: 0, top: 1000, width: W, height: 920, overflow: 'hidden'}}>
          <Face video={video} from={beat.start} faceY={faceY} height={920} zoom={beat.zoom ?? 1} />
        </div>
      </AbsoluteFill>
    );
  }
  // pip: card full screen, small face window at the bottom
  return (
    <AbsoluteFill>
      <Stage>
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingBottom: 620, opacity: enter, transform: `scale(${0.94 + 0.06 * enter})`}}>
          <CardView card={beat.card} />
        </AbsoluteFill>
      </Stage>
      <div style={{position: 'absolute', left: (W - 380) / 2, top: 1330, width: 380, height: 470, borderRadius: 34, overflow: 'hidden', border: '4px solid rgba(255,255,255,0.15)', boxShadow: '0 20px 50px rgba(0,0,0,0.6)', transform: `translateY(${(1 - enter) * 80}px)`}}>
        <div style={{position: 'relative', width: 380, height: 470, overflow: 'hidden'}}>
          <OffthreadVideo
            src={staticFile(video)}
            trimBefore={Math.round(beat.start * fps)}
            muted
            style={{position: 'absolute', width: 380, height: 676, top: -Math.max(0, Math.min(676 - 470, faceY * 676 - 470 * 0.45)), objectFit: 'cover'}}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const captionY = (layout: Beat['layout'] | undefined, hasCard: boolean) =>
  !hasCard || layout === 'full' ? 1330 : layout === 'split' ? 1000 : 1240;

export const Studio: React.FC<StudioProps> = ({
  video,
  audio,
  faceY = 0.35,
  accent = '#ff3b4a',
  words = [],
  keywords = [],
  beats,
  progress = true,
  rec = 0,
  sfx = [],
  music,
  musicVol = 0.08,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = f / fps;
  const cur = beats.find((b) => t >= b.start && t < b.end);
  return (
    <AccentCtx.Provider value={accent}>
      <AbsoluteFill style={{background: BG}}>
        {beats.map((b, i) => (
          <Sequence key={i} from={Math.round(b.start * fps)} durationInFrames={Math.max(1, Math.round((b.end - b.start) * fps))}>
            <BeatView beat={b} video={video} faceY={faceY} />
          </Sequence>
        ))}
        {rec > 0 ? (
          <Sequence from={0} durationInFrames={Math.round(rec * fps)}>
            <Rec />
          </Sequence>
        ) : null}
        {words.length ? <Captions words={words} keywords={keywords} y={captionY(cur?.layout, !!cur?.card)} /> : null}
        {progress ? <Progress /> : null}
        {audio ? <Audio src={staticFile(audio)} /> : null}
        {music ? <Audio src={staticFile(music)} volume={musicVol} /> : null}
        {sfx.map((s, i) => (
          <Sequence key={`s${i}`} from={Math.round(s.at * fps)}>
            <Audio src={staticFile(s.src)} volume={s.vol} />
          </Sequence>
        ))}
      </AbsoluteFill>
    </AccentCtx.Provider>
  );
};
