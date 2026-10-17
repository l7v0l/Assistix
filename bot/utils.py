import logging
import re
import shutil
import tempfile
import time
from pathlib import Path

import requests
import yt_dlp
from django.conf import settings

logger = logging.getLogger(__name__)

BOT_NAME = "Assistix"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # Telegram Bot API upload limit

# Full links (tiktok.com/@user/video/ID) and short links (vm./vt.tiktok.com/XXXX, tiktok.com/t/XXXX).
TIKTOK_URL_RE = re.compile(
    r"https?://(?:(?:www|m|vm|vt)\.)?tiktok\.com/[^\s<>\"']+",
    re.IGNORECASE,
)


class DownloadError(Exception):
    """Error with a message safe to show to the user."""


def extract_tiktok_url(text):
    """Return the first TikTok URL in text, or None."""
    if not text:
        return None
    match = TIKTOK_URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,;:!?)]}")


# ---------- Telegram Bot API ----------

def _api(method):
    return f"https://api.telegram.org/bot{settings.BOT_TOKEN}/{method}"


def send_message(chat_id, text, reply_to=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    try:
        resp = requests.post(_api("sendMessage"), json=payload, timeout=15)
        data = resp.json()
        return data.get("result", {}).get("message_id") if data.get("ok") else None
    except requests.RequestException:
        logger.exception("sendMessage failed")
        return None


def delete_message(chat_id, message_id):
    if not message_id:
        return
    try:
        requests.post(_api("deleteMessage"), json={"chat_id": chat_id, "message_id": message_id}, timeout=15)
    except requests.RequestException:
        logger.warning("deleteMessage failed", exc_info=True)


def send_video(chat_id, video_path, caption, width=None, height=None, duration=None, reply_to=None):
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML", "supports_streaming": "true"}
    if width:
        data["width"] = width
    if height:
        data["height"] = height
    if duration:
        data["duration"] = int(duration)
    if reply_to:
        data["reply_to_message_id"] = reply_to
        data["allow_sending_without_reply"] = "true"
    try:
        with open(video_path, "rb") as f:
            resp = requests.post(_api("sendVideo"), data=data, files={"video": f}, timeout=180)
    except requests.RequestException as exc:
        logger.exception("sendVideo network error")
        raise DownloadError("تعذر إرسال الفيديو إلى الدردشة.") from exc
    if not resp.ok:
        logger.error("sendVideo failed: %s", resp.text[:300])
        raise DownloadError("تعذر إرسال الفيديو إلى الدردشة.")


# ---------- yt-dlp ----------

def _friendly_error(exc):
    msg = str(exc).lower()
    if any(k in msg for k in ("private", "log in", "login")):
        return "🔒 هذا الفيديو خاص أو يتطلب تسجيل الدخول."
    if any(k in msg for k in ("not available", "unavailable", "removed", "deleted", "404", "not found")):
        return "🗑️ الفيديو غير متاح أو تم حذفه."
    if "region" in msg or "country" in msg:
        return "🌍 الفيديو غير متاح في منطقة السيرفر."
    return "⚠️ تعذر تحميل الفيديو. تأكد من الرابط وحاول مرة أخرى."


def download_tiktok(url, workdir):
    """Download best no-watermark video into workdir. Returns (path, info dict)."""
    opts = {
        "outtmpl": str(Path(workdir) / "%(id)s.%(ext)s"),
        # TikTok marks the watermarked stream with format_id "download"; skip it.
        "format": "best[format_id!*=download]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 3,
        "max_filesize": MAX_UPLOAD_BYTES,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as exc:
        logger.warning("yt-dlp failed for %s: %s", url, exc)
        raise DownloadError(_friendly_error(exc)) from exc
    except Exception as exc:
        logger.exception("unexpected download error")
        raise DownloadError("⚠️ حدث خطأ غير متوقع أثناء التحميل.") from exc

    if not path.exists():
        # max_filesize skips the file silently.
        raise DownloadError("📦 حجم الفيديو أكبر من 50MB، ولا يمكن إرساله عبر تليجرام.")
    return path, info


URL_SEND_LIMIT = 20 * 1024 * 1024  # Telegram fetches remote files up to 20MB itself


def extract_direct_url(url):
    """Resolve the direct no-watermark stream URL without downloading. Returns info dict."""
    opts = {
        "format": "best[format_id!*=download]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        logger.warning("yt-dlp failed for %s: %s", url, exc)
        raise DownloadError(_friendly_error(exc)) from exc


def try_send_by_url(chat_id, info, caption, reply_to):
    """Fast path: Telegram's servers pull the video, nothing is uploaded from here."""
    direct = info.get("url")
    size = info.get("filesize") or info.get("filesize_approx") or 0
    headers = info.get("http_headers") or {}
    # Cookies/special headers can't be forwarded to Telegram, so only plain CDN URLs qualify.
    if not direct or size > URL_SEND_LIMIT or "Cookie" in headers:
        return False
    payload = {
        "chat_id": chat_id, "video": direct, "caption": caption, "parse_mode": "HTML",
        "supports_streaming": True,
    }
    for key in ("width", "height"):
        if info.get(key):
            payload[key] = info[key]
    if info.get("duration"):
        payload["duration"] = int(info["duration"])
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    try:
        resp = requests.post(_api("sendVideo"), json=payload, timeout=60)
    except requests.RequestException:
        return False
    if not resp.ok:
        logger.info("send by URL rejected, falling back: %s", resp.text[:200])
    return resp.ok


def process_link(chat_id, message_id, url):
    """Full flow for one link. Never raises."""
    started = time.monotonic()
    status_id = send_message(chat_id, f"🤖 {BOT_NAME} يقوم بمعالجة الرابط الآن... ⏳", reply_to=message_id)
    workdir = tempfile.mkdtemp(prefix="assistix_")
    caption = f"✅ تم التحميل بدون علامة مائية\n🤖 {BOT_NAME}"
    try:
        info = extract_direct_url(url)
        logger.info("extract done in %.1fs", time.monotonic() - started)
        if try_send_by_url(chat_id, info, caption, message_id):
            logger.info("sent by URL in %.1fs", time.monotonic() - started)
            return
        path, info = download_tiktok(url, workdir)
        logger.info("downloaded in %.1fs", time.monotonic() - started)
        send_video(
            chat_id, path, caption,
            width=info.get("width"), height=info.get("height"),
            duration=info.get("duration"), reply_to=message_id,
        )
        logger.info("uploaded in %.1fs", time.monotonic() - started)
    except DownloadError as exc:
        send_message(chat_id, str(exc), reply_to=message_id)
    except Exception:
        logger.exception("process_link crashed")
        send_message(chat_id, "⚠️ حدث خطأ غير متوقع. حاول لاحقًا.", reply_to=message_id)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        delete_message(chat_id, status_id)
