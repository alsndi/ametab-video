import React from 'react';
import {AbsoluteFill, interpolate, interpolateColors, spring, useCurrentFrame, useVideoConfig} from 'remotion';

const YELLOW = '#FFD60A';

// interpolateColors returns "rgba(r, g, b, a)"; swap in a new alpha
const alpha = (rgba: string, a: number) => rgba.replace(/,\s*[\d.]+\)$/, `, ${a})`);
const FONT = "'Tajawal Black', 'Tajawal', 'Cairo', sans-serif";

const Bolt: React.FC<{size: number; color: string}> = ({size, color}) => (
  <svg width={size} height={size * 1.5} viewBox="0 0 40 60">
    <path d="M24 0 L4 34 H18 L14 60 L36 22 H22 Z" fill={color} stroke="#000" strokeWidth={2.5} strokeLinejoin="round" />
  </svg>
);

export const BatteryBoost: React.FC<{seconds?: number; title?: string; highlight?: string}> = ({
  title = "بطارية تدوم",
  highlight = "أطول",
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  // entrance
  const flash = interpolate(frame, [0, 6], [0.85, 0], {extrapolateRight: 'clamp'});
  const bgZoom = interpolate(frame, [0, 12], [1.25, 1], {extrapolateRight: 'clamp'});
  const titleIn = spring({frame: frame - 4, fps, config: {damping: 12, stiffness: 140}});
  const batteryIn = spring({frame: frame - 8, fps, config: {damping: 14, stiffness: 120}});

  // charge 15% -> 100% between frames 16 and 66
  const level = interpolate(frame, [16, 66], [15, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const eased = 15 + (85 * (1 - Math.pow(1 - (level - 15) / 85, 2)));
  const fillColor = interpolateColors(eased, [15, 50, 100], ['#FF3B30', YELLOW, '#34C759']);
  const done = frame >= 66;
  const donePop = spring({frame: frame - 66, fps, config: {damping: 8, stiffness: 200}});
  const boltPulse = 1 + 0.08 * Math.sin(frame / 3);

  // exit zoom into the next shot
  const exit = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 1.15], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const W = 360;
  const H = 600;
  const pad = 22;
  const innerH = H - pad * 2;

  return (
    <AbsoluteFill style={{backgroundColor: '#12061f', overflow: 'hidden'}}>
      {/* background glow */}
      <AbsoluteFill
        style={{
          transform: `scale(${bgZoom * exit})`,
          background: `radial-gradient(circle at 50% 42%, ${alpha(fillColor, 0.33)} 0%, #5b21b6 28%, #2a0d52 55%, #0d0418 100%)`,
        }}
      />
      {/* light streaks */}
      {[0, 1, 2, 3, 4, 5].map((i) => {
        const y = ((frame * (6 + i * 2) + i * 330) % 2200) - 200;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: 90 + i * 160,
              top: 1920 - y,
              width: 6,
              height: 160,
              borderRadius: 3,
              background: `linear-gradient(${alpha(fillColor, 0)}, ${alpha(fillColor, 0.67)})`,
              opacity: 0.6,
            }}
          />
        );
      })}

      <AbsoluteFill style={{transform: `scale(${exit})`, alignItems: 'center'}}>
        {/* headline */}
        <div
          style={{
            position: 'absolute',
            top: 150,
            width: '100%',
            textAlign: 'center',
            direction: 'rtl',
            fontFamily: FONT,
            fontWeight: 900,
            fontSize: 118,
            color: '#fff',
            WebkitTextStroke: '10px #000',
            paintOrder: 'stroke fill',
            textShadow: '0 8px 0 rgba(0,0,0,0.45)',
            transform: `translateY(${(1 - titleIn) * -120}px) scale(${0.6 + 0.4 * titleIn})`,
            opacity: titleIn,
          }}
        >
          {title} <span style={{color: YELLOW}}>{highlight}</span>
        </div>

        {/* battery */}
        <div
          style={{
            position: 'absolute',
            top: 380,
            transform: `scale(${batteryIn * (done ? 1 + 0.06 * donePop - 0.06 * Math.min(1, (frame - 66) / 10) : 1)})`,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <div style={{width: 130, height: 46, background: '#fff', borderRadius: '18px 18px 0 0', border: '6px solid #000', borderBottom: 'none'}} />
          <div
            style={{
              width: W,
              height: H,
              borderRadius: 64,
              border: '16px solid #fff',
              outline: '6px solid #000',
              background: 'rgba(0,0,0,0.55)',
              position: 'relative',
              boxShadow: `0 0 120px ${alpha(fillColor, 0.67)}`,
            }}
          >
            <div
              style={{
                position: 'absolute',
                left: pad,
                right: pad,
                bottom: pad,
                height: (innerH * eased) / 100,
                borderRadius: 40,
                background: `linear-gradient(180deg, ${fillColor}, ${alpha(fillColor, 0.8)})`,
              }}
            />
            <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
              <div style={{transform: `scale(${boltPulse})`}}>
                <Bolt size={150} color={done ? '#fff' : YELLOW} />
              </div>
            </AbsoluteFill>
          </div>
        </div>

        {/* percentage */}
        <div
          style={{
            position: 'absolute',
            top: 1040,
            width: '100%',
            textAlign: 'center',
            fontFamily: FONT,
            fontWeight: 900,
            fontSize: 150,
            color: done ? YELLOW : '#fff',
            WebkitTextStroke: '10px #000',
            paintOrder: 'stroke fill',
            opacity: batteryIn,
            transform: `scale(${done ? 1 + 0.25 * donePop - 0.25 * Math.min(1, (frame - 66) / 8) : 1})`,
          }}
        >
          {Math.round(eased)}%
        </div>
      </AbsoluteFill>

      <AbsoluteFill style={{backgroundColor: '#fff', opacity: flash}} />
    </AbsoluteFill>
  );
};
