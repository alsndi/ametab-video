import React from 'react';
import {Composition} from 'remotion';
import {BatteryBoost} from './BatteryBoost';
import {TitleCard, TitleCardProps} from './TitleCard';
import {CoverProps, ReelCover, YouTubeThumb} from './Cover';
import {Explainer, ExplainerProps} from './Explainer';

const explainerDefaults: ExplainerProps = {
  duration: 6,
  scenes: [
    {type: 'title', start: 0, end: 2.5, title: 'حركة', highlight: 'قوية', emoji: '⚡'},
    {type: 'number', start: 2.5, end: 6, value: '٥س', label: 'استخدام يومي', emoji: '📱'},
  ],
};

const coverDefaults: CoverProps = {image: 'cover_src.png', title: 'حركة', highlight: 'قوية', tag: 'جرّبها', faceX: 0.5, faceY: 0.3};

const FPS = 30;
// Every clip takes `seconds` so its length matches the gap it fills in the reel.
const frames = ({props}: {props: {seconds: number}}) => ({durationInFrames: Math.round(props.seconds * FPS)});

export const Root: React.FC = () => (
  <>
    <Composition
      id="TitleCard"
      component={TitleCard}
      fps={FPS}
      width={1080}
      height={1920}
      durationInFrames={90}
      defaultProps={{seconds: 3, title: 'حركة', highlight: 'قوية', sub: 'لازم تعرفها', emoji: '⚡'} as TitleCardProps}
      calculateMetadata={frames}
    />
    <Composition
      id="BatteryBoost"
      component={BatteryBoost}
      fps={FPS}
      width={1080}
      height={1920}
      durationInFrames={108}
      defaultProps={{seconds: 3.6}}
      calculateMetadata={frames}
    />
    <Composition
      id="Explainer"
      component={Explainer}
      fps={FPS}
      width={1080}
      height={1920}
      durationInFrames={180}
      defaultProps={explainerDefaults}
      calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.round(props.duration * FPS))})}
    />
    {/* stills: render with `npx remotion still` */}
    <Composition id="ReelCover" component={ReelCover} fps={FPS} width={1080} height={1920} durationInFrames={1} defaultProps={coverDefaults} />
    <Composition id="YouTubeThumb" component={YouTubeThumb} fps={FPS} width={1280} height={720} durationInFrames={1} defaultProps={coverDefaults} />
  </>
);
