import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';

export type CoverProps = {
  image: string; // file name inside public/
  title: string; // white words
  highlight: string; // yellow word(s)
  tag?: string; // small pill above the title, e.g. "حركة مخفية"
  faceX?: number; // 0..1 face center in the source image
  faceY?: number;
  layout?: 'side' | 'bold' | 'split'; // YouTube layouts
  emoji?: string;
  look?: 'classic' | 'studio'; // classic: yellow word + black stroke. studio: word on an accent box, accent tag
  accent?: string; // studio accent colour
  rec?: boolean; // studio: green REC corners on the reel cover
};

const LookCtx = React.createContext<{studio: boolean; accent: string}>({studio: false, accent: '#FFD60A'});

const YELLOW = '#FFD60A';
const PURPLE = '#4c1d95';
const FONT = "'Tajawal Black', 'Tajawal', 'Cairo', sans-serif";
const stroke = (px: number) => ({WebkitTextStroke: `${px}px #000`, paintOrder: 'stroke fill' as const});

const Title: React.FC<{title: string; highlight: string; size: number; boxed?: boolean}> = ({
  title,
  highlight,
  size,
  boxed,
}) => {
  const look = React.useContext(LookCtx);
  const hi: React.CSSProperties = look.studio
    ? {background: look.accent, color: '#fff', WebkitTextStroke: '0', padding: '0 0.2em', borderRadius: size / 5, textShadow: 'none', display: 'inline-block', marginTop: size * 0.08}
    : boxed
      ? {background: YELLOW, color: '#000', WebkitTextStroke: '0', padding: '0 0.18em', borderRadius: size / 6, textShadow: 'none'}
      : {color: YELLOW};
  return (
  <div
    style={{
      direction: 'rtl',
      fontFamily: FONT,
      fontWeight: 900,
      fontSize: size,
      lineHeight: look.studio ? 1.2 : 1.12,
      color: '#fff',
      ...stroke(size / 11),
      textShadow: `0 ${size / 14}px 0 rgba(0,0,0,0.55)`,
    }}
  >
    {title}{' '}
    {look.studio ? <br /> : null}
    <span style={hi}>{highlight}</span>
  </div>
  );
};

const Tag: React.FC<{text: string; size: number}> = ({text, size}) => {
  const look = React.useContext(LookCtx);
  return (
  <div
    style={{
      display: 'inline-block',
      direction: 'rtl',
      fontFamily: FONT,
      fontWeight: 900,
      fontSize: size,
      color: look.studio ? look.accent : '#000',
      background: look.studio ? 'rgba(6,10,8,0.82)' : YELLOW,
      padding: `${size * 0.12}px ${size * 0.5}px`,
      borderRadius: look.studio ? size * 0.35 : size,
      border: look.studio ? `${size / 12}px solid ${look.accent}` : `${size / 10}px solid #000`,
      marginBottom: size * 0.4,
    }}
  >
    {text}
  </div>
  );
};

const RecCorners: React.FC = () => {
  const c = (pos: React.CSSProperties, b: React.CSSProperties) => (
    <div style={{position: 'absolute', width: 110, height: 110, borderColor: '#22c55e', borderStyle: 'solid', borderWidth: 0, ...pos, ...b}} />
  );
  return (
    <AbsoluteFill>
      {c({left: 60, top: 300}, {borderTopWidth: 10, borderLeftWidth: 10})}
      {c({right: 60, top: 300}, {borderTopWidth: 10, borderRightWidth: 10})}
      {c({left: 60, top: 1520}, {borderBottomWidth: 10, borderLeftWidth: 10})}
      {c({right: 60, top: 1520}, {borderBottomWidth: 10, borderRightWidth: 10})}
      <div style={{position: 'absolute', left: 95, top: 335, display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(0,0,0,0.6)', borderRadius: 30, padding: '8px 22px'}}>
        <div style={{width: 24, height: 24, borderRadius: 12, background: '#ef4444'}} />
        <div style={{fontFamily: 'Arial', fontWeight: 900, fontSize: 34, color: '#fff'}}>REC</div>
      </div>
    </AbsoluteFill>
  );
};

// 1080x1920 reel cover. Title block sits in y 1000..1480 so it is inside both the 1:1 (y 420..1500)
// and 3:4 (y 240..1680) profile-grid crops; keep the face in the upper half of the frame.
export const ReelCover: React.FC<CoverProps> = ({image, title, highlight, tag, faceY = 0.3, look = 'classic', accent = '#ff3b4a', rec}) => (
  <LookCtx.Provider value={{studio: look === 'studio', accent}}>
  <AbsoluteFill style={{backgroundColor: '#000'}}>
    <Img
      src={staticFile(image)}
      style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: `50% ${faceY * 100}%`}}
    />
    <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(0,0,0,0.75) 78%)'}} />
    <div style={{position: 'absolute', top: 1000, left: 60, right: 60, textAlign: 'center'}}>
      {tag ? <Tag text={tag} size={58} /> : null}
      <Title title={title} highlight={highlight} size={look === 'studio' ? 140 : 150} />
    </div>
    {look === 'studio' && rec ? <RecCorners /> : null}
  </AbsoluteFill>
  </LookCtx.Provider>
);

// 1280x720 YouTube thumbnail, three layouts.
export const YouTubeThumb: React.FC<CoverProps> = ({
  image,
  title,
  highlight,
  tag,
  faceX = 0.5,
  faceY = 0.3,
  layout = 'side',
  emoji,
  look = 'classic',
  accent = '#ff3b4a',
}) => (
  <LookCtx.Provider value={{studio: look === 'studio', accent}}>
    <YouTubeInner {...{image, title, highlight, tag, faceX, faceY, layout, emoji}} />
  </LookCtx.Provider>
);

const YouTubeInner: React.FC<CoverProps> = ({image, title, highlight, tag, faceX = 0.5, faceY = 0.3, layout = 'side', emoji}) => {
  const pos = `${faceX * 100}% ${faceY * 100}%`;
  if (layout === 'split') {
    return (
      <AbsoluteFill style={{background: `radial-gradient(circle at 25% 50%, #7c3aed, ${PURPLE} 70%)`}}>
        <Img
          src={staticFile(image)}
          style={{position: 'absolute', left: 0, top: 0, width: 600, height: 720, objectFit: 'cover', objectPosition: pos}}
        />
        <div style={{position: 'absolute', left: 600, top: 0, width: 22, height: 720, background: YELLOW}} />
        <div style={{position: 'absolute', left: 650, right: 40, top: 0, bottom: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center'}}>
          {emoji ? <div style={{fontSize: 130, marginBottom: 10}}>{emoji}</div> : null}
          <Title title={title} highlight={highlight} size={104} />
        </div>
      </AbsoluteFill>
    );
  }
  if (layout === 'bold') {
    return (
      <AbsoluteFill style={{backgroundColor: '#000'}}>
        <Img src={staticFile(image)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: pos, transform: 'scale(1.08)', transformOrigin: pos}} />
        <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(0,0,0,0.8) 100%)'}} />
        <div style={{position: 'absolute', left: 40, right: 40, bottom: 34, textAlign: 'center'}}>
          <Title title={title} highlight={highlight} size={118} boxed />
        </div>
        {tag ? (
          <div style={{position: 'absolute', top: 30, right: 36}}>
            <Tag text={tag} size={48} />
          </div>
        ) : null}
      </AbsoluteFill>
    );
  }
  // side: face on the right, text on a dark left panel
  return (
    <AbsoluteFill style={{background: `linear-gradient(90deg, #0d0418 0%, ${PURPLE} 100%)`}}>
      <Img
        src={staticFile(image)}
        style={{position: 'absolute', right: 0, top: 0, width: 640, height: 720, objectFit: 'cover', objectPosition: pos}}
      />
      <div style={{position: 'absolute', left: 560, top: 0, width: 160, height: 720, background: 'linear-gradient(90deg, #0d0418, rgba(13,4,24,0))'}} />
      <div style={{position: 'absolute', left: 50, width: 640, top: 0, bottom: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center'}}>
        {tag ? <Tag text={tag} size={50} /> : null}
        <Title title={title} highlight={highlight} size={112} />
      </div>
    </AbsoluteFill>
  );
};
