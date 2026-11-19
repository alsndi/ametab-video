import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type TitleCardProps = {
  seconds: number;
  title: string; // white part
  highlight: string; // yellow word(s), placed after the title (RTL)
  sub?: string; // optional smaller line
  emoji?: string; // optional big icon in the middle
  bg?: [string, string]; // gradient colors
};

const YELLOW = '#FFD60A';
const FONT = "'Tajawal Black', 'Tajawal', 'Cairo', sans-serif";
const stroke = (px: number) => ({WebkitTextStroke: `${px}px #000`, paintOrder: 'stroke fill' as const});

export const TitleCard: React.FC<TitleCardProps> = ({title, highlight, sub, emoji, bg = ['#5b21b6', '#0d0418']}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const flash = interpolate(frame, [0, 6], [0.85, 0], {extrapolateRight: 'clamp'});
  const titleIn = spring({frame: frame - 3, fps, config: {damping: 12, stiffness: 140}});
  const hiIn = spring({frame: frame - 10, fps, config: {damping: 9, stiffness: 180}});
  const subIn = spring({frame: frame - 18, fps, config: {damping: 14}});
  const iconIn = spring({frame: frame - 6, fps, config: {damping: 10, stiffness: 120}});
  const float = Math.sin(frame / 8) * 12;
  const exit = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 1.15], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 50% 40%, ${bg[0]} 0%, ${bg[1]} 75%)`}}>
      <AbsoluteFill style={{transform: `scale(${exit})`, alignItems: 'center', direction: 'rtl'}}>
        {emoji ? (
          <div
            style={{
              position: 'absolute',
              top: 330,
              fontSize: 360,
              transform: `translateY(${float}px) scale(${iconIn})`,
              filter: 'drop-shadow(0 20px 40px rgba(0,0,0,0.5))',
            }}
          >
            {emoji}
          </div>
        ) : null}
        <div
          style={{
            position: 'absolute',
            top: emoji ? 820 : 640,
            width: '90%',
            textAlign: 'center',
            fontFamily: FONT,
            fontWeight: 900,
            fontSize: 124,
            lineHeight: 1.25,
            color: '#fff',
            ...stroke(10),
            textShadow: '0 8px 0 rgba(0,0,0,0.45)',
            transform: `translateY(${(1 - titleIn) * 80}px)`,
            opacity: titleIn,
          }}
        >
          {title}{' '}
          <span style={{color: YELLOW, display: 'inline-block', transform: `scale(${0.4 + 0.6 * hiIn})`}}>
            {highlight}
          </span>
        </div>
        {sub ? (
          <div
            style={{
              position: 'absolute',
              top: emoji ? 1110 : 930,
              width: '86%',
              textAlign: 'center',
              fontFamily: FONT,
              fontWeight: 900,
              fontSize: 64,
              color: '#fff',
              ...stroke(6),
              opacity: subIn,
              transform: `translateY(${(1 - subIn) * 40}px)`,
            }}
          >
            {sub}
          </div>
        ) : null}
      </AbsoluteFill>
      <AbsoluteFill style={{backgroundColor: '#fff', opacity: flash}} />
    </AbsoluteFill>
  );
};
