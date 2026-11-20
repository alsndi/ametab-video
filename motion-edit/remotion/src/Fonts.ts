import {continueRender, delayRender, staticFile} from 'remotion';

// Bundled OFL fonts (ametab-video/fonts, copied to public/fonts by the build scripts).
// Loaded before the first frame renders, so templates can use them without installing anything.
// If a file is missing the template simply falls back to the next font in its font-family list.
const FONTS: [string, string, string, string][] = [
  ['Aref Ruqaa', 'ArefRuqaa-Bold.ttf', '700', 'normal'],
  ['Reem Kufi', 'ReemKufi-Variable.ttf', '400 700', 'normal'],
  ['Alexandria', 'Alexandria-Variable.ttf', '100 900', 'normal'],
  ['Amiri', 'Amiri-BoldItalic.ttf', '700', 'italic'],
];

const handle = delayRender('Loading bundled fonts');
Promise.all(
  FONTS.map(([family, file, weight, style]) =>
    new FontFace(family, `url(${staticFile(`fonts/${file}`)})`, {weight, style})
      .load()
      .then((f) => document.fonts.add(f))
      .catch(() => undefined),
  ),
).then(() => continueRender(handle));

export const RUQAA = "'Aref Ruqaa', 'Amiri', serif";
export const KUFI = "'Reem Kufi', 'Tajawal', sans-serif";
