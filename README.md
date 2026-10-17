# Assistix (@AssistixBot)

بوت تليجرام لتحميل فيديوهات تيك توك بدون علامة مائية. Django + yt-dlp + Webhook.

## الهيكل

```
manage.py
requirements.txt
.env.example
config/            # إعدادات Django (settings, urls, wsgi)
bot/
  views.py         # webhook (@csrf_exempt) + منطق الأوامر
  urls.py          # /bot/webhook/
  utils.py         # التحقق من الروابط، yt-dlp، Telegram API
  management/commands/set_webhook.py
```

## التشغيل

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Linux: cp .env.example .env
```

عبّئ `.env`:

- `BOT_TOKEN` من @BotFather
- `WEBHOOK_SECRET` نص عشوائي (حروف/أرقام/`_`/`-`)
- `WEBHOOK_BASE_URL` رابط HTTPS العام للسيرفر
- `DJANGO_SECRET_KEY` مفتاح عشوائي طويل
- `DJANGO_ALLOWED_HOSTS` دومين السيرفر

توليد مفتاح:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## ربط الـ Webhook

تليجرام يقبل HTTPS فقط على دومين عام. للتجربة المحلية استخدم ngrok:

```bash
python manage.py runserver 8000
ngrok http 8000
```

ضع رابط ngrok في `WEBHOOK_BASE_URL` (وأضف دومينه إلى `DJANGO_ALLOWED_HOSTS`)، ثم:

```bash
python manage.py set_webhook          # تسجيل
python manage.py set_webhook --info   # فحص الحالة
python manage.py set_webhook --delete # إزالة
```

## الإنتاج

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 120
```

ضع nginx/Caddy أمامه مع شهادة HTTPS. أعد تسجيل الـ webhook بعد أي تغيير في الرابط.

## ملاحظات

- الـ webhook يرد فورًا ويعالج التحميل في thread خلفي (تليجرام يعيد الإرسال إذا تأخر الرد).
- الحد الأقصى للرفع عبر Bot API هو 50MB.
- تيك توك يغيّر واجهته كثيرًا: حدّث yt-dlp باستمرار: `pip install -U yt-dlp`.
- لا توجد قاعدة بيانات؛ البوت بدون حالة.
