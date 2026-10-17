import hmac
import json
import logging
import threading

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .utils import BOT_NAME, extract_tiktok_url, process_link, send_message

logger = logging.getLogger(__name__)

WELCOME = (
    f"👋 أهلاً بك في <b>{BOT_NAME}</b>!\n\n"
    "أنا بوت متخصص في تحميل فيديوهات <b>تيك توك</b> بأعلى جودة وبدون علامة مائية.\n\n"
    "📌 <b>طريقة الاستخدام:</b>\n"
    "أرسل لي رابط الفيديو (الكامل أو المختصر مثل vm.tiktok.com) وسأرسله لك مباشرة.\n\n"
    "🚀 جرّب الآن!"
)
HELP = (
    f"ℹ️ <b>{BOT_NAME}</b>\n"
    "أرسل رابط فيديو تيك توك وسأحمّله لك بدون علامة مائية.\n"
    "الحد الأقصى للحجم: 50MB."
)
INVALID = "❌ لم أجد رابط تيك توك صالحًا. أرسل رابط فيديو مثل:\nhttps://vm.tiktok.com/XXXXXXX/"


def _handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    message_id = message.get("message_id")
    text = (message.get("text") or message.get("caption") or "").strip()

    if text.startswith("/start"):
        send_message(chat_id, WELCOME)
    elif text.startswith("/help"):
        send_message(chat_id, HELP)
    else:
        url = extract_tiktok_url(text)
        if url:
            process_link(chat_id, message_id, url)
        else:
            send_message(chat_id, INVALID, reply_to=message_id)


def _safe_handle(update):
    try:
        _handle_update(update)
    except Exception:
        logger.exception("update handling failed")


def health(request):
    """Keep-alive endpoint for uptime pingers."""
    return HttpResponse("ok")


@csrf_exempt
@require_POST
def webhook(request):
    secret = settings.WEBHOOK_SECRET
    if secret:
        received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(received, secret):
            return HttpResponseForbidden("forbidden")

    try:
        update = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)

    if settings.SYNC_PROCESSING:
        # Serverless hosts (Cloud Run) throttle CPU after the response is sent, so work inline.
        _safe_handle(update)
    else:
        # Answer Telegram fast (it retries on slow replies); the download runs in the background.
        threading.Thread(target=_safe_handle, args=(update,), daemon=True).start()
    return HttpResponse("ok")
