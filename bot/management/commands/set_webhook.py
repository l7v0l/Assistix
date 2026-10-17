import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Register (or --delete) the Telegram webhook."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Remove the webhook")
        parser.add_argument("--info", action="store_true", help="Show current webhook info")

    def handle(self, *args, **opts):
        base = f"https://api.telegram.org/bot{settings.BOT_TOKEN}"

        if opts["info"]:
            self.stdout.write(requests.get(f"{base}/getWebhookInfo", timeout=15).text)
            return
        if opts["delete"]:
            self.stdout.write(requests.post(f"{base}/deleteWebhook", timeout=15).text)
            return

        if not settings.WEBHOOK_BASE_URL.startswith("https://"):
            raise CommandError("WEBHOOK_BASE_URL must be a public https:// URL")

        payload = {
            "url": f"{settings.WEBHOOK_BASE_URL}/bot/webhook/",
            "allowed_updates": ["message", "edited_message"],
            "drop_pending_updates": True,
        }
        if settings.WEBHOOK_SECRET:
            payload["secret_token"] = settings.WEBHOOK_SECRET
        resp = requests.post(f"{base}/setWebhook", json=payload, timeout=15)
        self.stdout.write(resp.text)
