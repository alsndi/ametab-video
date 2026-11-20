---
name: soft-captions
description: ستايل كابشن ناعم وأنيق — كلام أبيض رفيع (Tajawal Medium) بتوهّج خفيف بدل الحافة السودا، الكلمات اللي ما انقالت باهتة، والكلمة اللي تنقال تتحوّل لخط Amiri مائل بلون وردي ناعم. للفيديوهات الهادية، الجمال، اللايف ستايل، والكلام الشخصي. Use when the user says "كابشن ناعم"، "ستايل أنيق"، "كابشن هادي"، "خط مزخرف"، "soft captions"، "aesthetic captions"، "مثل كابشن البنات"، "مو عريض"، or wants a softer look than the bold yellow captions.
---

# soft-captions — كابشن ناعم

نفس محرك `talk-reel`، والفرق في ملف الستايل `talk-reel/brand_soft.json`:

| الجزء | الشكل |
|---|---|
| الكلام | **Tajawal Medium** أبيض رفيع، حجمه 84 |
| بدال الحافة السودا | توهّج غامق ناعم (`outline_alpha` و`glow_blur`)، عشان الكلام ينقرا فوق أي خلفية |
| الكلمات اللي للحين ما انقالت | باهتة (`unsaid_alpha`) |
| الكلمة اللي تنقال الحين | تتحوّل لخط **Amiri** مائل بلون وردي فاتح (`#F7C6D3`)، وتكبر 165% لأن حروف Amiri صغيرة بطبيعتها |

## المتطلبات
مثل `talk-reel`، ومعه خط **Amiri** مثبت. إذا ما كان موجود، نزّله من Google Fonts، أو غيّر `accent_font` لخط ثاني أنيق.

## الخطوات
1. فرّغ الكلام إذا ما كان مفرّغ:
   ```
   python "<skill>/../talk-reel/scripts/transcribe.py" "<video>" "<work>/words.json" --model medium --lang ar
   ```
2. ارندر بالستايل الناعم:
   ```
   python "<skill>/../talk-reel/scripts/render.py" "<video>" "<work>/words.json" "<work>/soft.mp4" --brand "<skill>/../talk-reel/brand_soft.json"
   ```
   أضف `--no-cut` إذا ما تبي تقص السكتات.
3. **تغيير اللون أو الخط:** انسخ `brand_soft.json` لمجلد الشغل وعدّل فيه:
   - `fill_color`: لون الكلمة اللي تنقال. ذهبي `#E8C27A`، أو أبيض كريمي `#FFF3E0`، أو سماوي فاتح `#BDE7F5`.
   - `accent_font`: خط الكلمة اللي تنقال.
   
   بعدها مرّر الملف المعدّل بـ `--brand`.
4. **افحص:**
   - طلّع 3 أو 4 فريمات من منطقة الكابشن.
   - تأكد إن الكلام مقروء فوق الخلفية. إذا الخلفية مزحومة، زِد `glow_blur` أو `outline`.
   - تأكد إن كلمة Amiri مو صغيرة مقارنة بالباقي.

## نسخة الرقعة الذهبية
`talk-reel/brand_ruqaa.json` نفس الستايل الناعم، بس الكلمة اللي تنقال تطلع بخط **Aref Ruqaa** بلون ذهبي (`#E8C27A`). تستخدمها كذا: `--brand "<skill>/../talk-reel/brand_ruqaa.json"`. والخط يجي مع الإضافة في مجلد `fonts/`، وما يحتاج تثبيت.

**ينفع مع:** `trial-reels` (اختار `"style": "soft"`)، و`motion-edit` (بـ `"brand"` في الخطة).
