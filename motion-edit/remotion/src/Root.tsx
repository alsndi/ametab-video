import React from 'react';
import {Composition} from 'remotion';
import {BatteryBoost} from './BatteryBoost';
import {TitleCard, TitleCardProps} from './TitleCard';

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
  </>
);
