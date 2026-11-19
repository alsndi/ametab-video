# ametab-video

إضافة لـ Claude Code تمنتج فيديوهات عربية على جهازك. من تطوير **Ametab Alsndi**.

## السكلات
| السكل | وش يسوي |
|---|---|
| `talk-reel` | يحوّل فيديو كلام لريل 9:16: يقص السكتات، ويركّب كابشن عربي (Tajawal Black، أبيض، والكلمة اللي تنقال تصير صفراء)، ويضبط الصوت |

## المتطلبات
- [Claude Code](https://claude.com/claude-code)
- `ffmpeg` (ويندوز: `winget install Gyan.FFmpeg`، ماك: `brew install ffmpeg`)
- Python 3، و `pip install faster-whisper`

## التثبيت
في Claude Code اكتب:
```
/plugin marketplace add alsndi/ametab-video
/plugin install ametab-video@ametab-video
```
أو من التطبيق: Settings ثم Plugins ثم Add marketplace، وحط `alsndi/ametab-video`.

## الاستخدام
أرسل فيديو لـ Claude وقل: «منتج هالفيديو وسو منه ريل».

## الرخصة
MIT © 2026 Ametab Alsndi
