# Gemini Web Scraper & Generator GitHub Action 🚀

سكرايبر وتطوير أوتوميشن لـ Google Gemini يعمل بواسطة **GitHub Actions** و **Playwright**.
يتيح لك إرسال رسايل نصية، إرفاق صور، واستقبال الردود والتوليدات (صور/فيديوهات/نصوص) وتخزينها كـ Artifacts مع إمكانية ربطها بـ **n8n Webhook**.

---

## 📋 المميزات
- 💬 **إرسال برومبت (Prompt)** نصي لجمناي.
- 🖼️ **إرفاق صور** عبر رابط (`image_url`) وتحليلها.
- 🎨 **تنزيل الوسائط الموّلدة** (صور / فيديوهات) تلقائيًا وترحيلها كـ Artifacts.
- 🔔 **إرسال إشعار ونتائج لـ n8n Webhook** فور الانتهاء.
- 🔒 **تشغيل آمن بـ Base64 Cookies** بدون الحاجة لحفظ بيانات الدخول في الكود.

---

## 🛠️ كيفية استخراج الكوكيز (Cookies)

1. قم بفتح موقع [Google Gemini](https://gemini.google.com/app) وتأكد من تسجيل دخولك.
2. قم بتثبيت إضافة متصفح مثل **Cookie-Editor** أو **EditThisCookie**.
3. قم بتصدير الكوكيز بصيغة **JSON**.
4. احفظ الكوكيز في ملف باسم `cookies.json`.
5. تحويل ملف الكوكيز إلى **Base64**:
   - **في Linux / Git Bash / macOS:**
     ```bash
     cat cookies.json | base64 -w 0
     ```
   - **في PowerShell (Windows):**
     ```powershell
     [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("cookies.json"))
     ```
6. انسخ النص المشفر واستخدمه في حقل `cookies_b64`.

---

## 🚀 كيفية تشغيل الـ Workflow في GitHub Actions

### 1️⃣ التشغيل اليدوي (Workflow Dispatch)
1. اذهب إلى تبويب **Actions** في مستودع GitHub الخاص بك.
2. اختر Workflow باسم **Gemini Web Scraper & Generator**.
3. اضغط على **Run workflow** واملأ البيانات:
   - **prompt**: النص أو الطلب الذي تريد إرساله لجمناي (مثال: `أصنع صورة لقطة ترتدي نظارة`).
   - **image_url**: (اختياري) رابط صورة إذا كنت تريد تحليلها أو التعديل عليها.
   - **cookies_b64**: كود الكوكيز المشفر Base64.
   - **n8n_webhook**: (اختياري) رابط Webhook الخاص بـ n8n لاستقبال النتيجة.

---

## 🔗 ربط Workflow بـ n8n أو عبر GitHub REST API

يمكنك تشغيل الـ Action تلقائياً من n8n باستخدام عقدة **HTTP Request**:

- **Method**: `POST`
- **URL**: `https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/actions/workflows/gemini_scraper.yml/dispatches`
- **Headers**:
  - `Authorization`: `Bearer YOUR_GITHUB_PAT_TOKEN`
  - `Accept`: `application/vnd.github+json`
- **Body (JSON)**:
```json
{
  "ref": "main",
  "inputs": {
    "prompt": "اصنع صورة لغابة في الليل",
    "image_url": "https://example.com/sample.jpg",
    "cookies_b64": "YOUR_BASE64_COOKIES_HERE",
    "n8n_webhook": "https://your-n8n-instance.com/webhook/gemini-callback"
  }
}
```

---

## 📁 المخرجات والنتائج (Outputs & Artifacts)

عند الانتهاء يتم حفظ جميع المخرجات في مجلد `outputs/` ويتم رفعها كـ GitHub Artifact ينتهي اسمه بـ `gemini-output-<RUN_ID>` وتضم:
- `result.json`: يحتوي على نص الرد كاملاً، حالة العملية، وقائمة بالملفات الموّلدة.
- `response_screenshot.png`: لقطة شاشة لشاشة جمناي بعد توليد الرد.
- `generated_image_*.png`: الصور التي تم توليدها إن وجدت.
- `generated_video_*.mp4`: الفيديوهات التي تم توليدها إن وجدت.

---

## 📦 محتويات المشروع
- `.github/workflows/gemini_scraper.yml`: ملف الجت هب اكشن.
- `gemini_scraper.py`: سكربت البايثون المعتمد على Playwright للتحكم بالمتصفح.
- `requirements.txt`: المكتبات المطلوبة (`playwright`, `requests`).
- `README.md`: تعليمات الاستخدام.
