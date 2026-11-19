# ametab-video

إضافة لـ Claude Code تمنتج فيديوهات عربية على جهازك. من تطوير **Ametab Alsndi**.

## السكلات
| السكل | وش يسوي |
|---|---|
| `talk-reel` | يحوّل فيديو كلام لريل 9:16: يقص السكتات، ويركّب كابشن عربي (Tajawal Black، أبيض، والكلمة اللي تنقال تصير صفراء)، ويضبط الصوت |
| `motion-edit` | مونتاج كامل بالموشن: زوم على الوجه، انتقالات فلاش، إشارات مرقّمة تنبض على الأزرار والإعدادات اللي تشرحها، مؤثرات صوتية من حزمتك، وكليبات موشن بـ Remotion وسط الفيديو |

## المتطلبات
- [Claude Code](https://claude.com/claude-code)
- `ffmpeg` (ويندوز: `winget install Gyan.FFmpeg`، ماك: `brew install ffmpeg`)
- Python 3، و `pip install faster-whisper`
- خط [Tajawal](https://fonts.google.com/specimen/Tajawal) مثبت على جهازك
- للموشن: [Node.js](https://nodejs.org) 18 أو أحدث
- للأصوات: حزمة مؤثرات صوتية من عندك (الإضافة ما فيها أصوات)

## التثبيت
في Claude Code اكتب:
```
/plugin marketplace add alsndi/ametab-video
/plugin install ametab-video@ametab-video
```
أو من التطبيق: Settings ثم Plugins ثم Add marketplace، وحط `alsndi/ametab-video`.

## الاستخدام
- كابشن بس: أرسل فيديو لـ Claude وقل «منتج هالفيديو وسو منه ريل».
- مونتاج كامل: أرسل الفيديو مع حزمة الأصوات وقل «سو مونتاج كامل بأصوات وانتقالات، وأشّر على الإعدادات». وتقدر تضيف «وحط موشن بعد جملة كذا».

## الرخصة
MIT © 2026 Ametab Alsndi
