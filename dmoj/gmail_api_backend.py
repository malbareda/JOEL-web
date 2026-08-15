import base64

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class GmailAPIBackend(BaseEmailBackend):
    """Sends mail through the Gmail API, authenticated as GMAIL_API_SENDER via
    domain-wide delegation of the service account at GMAIL_API_SERVICE_ACCOUNT_FILE."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._service = None

    def _get_service(self):
        if self._service is None:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GMAIL_API_SERVICE_ACCOUNT_FILE, scopes=SCOPES,
            ).with_subject(settings.GMAIL_API_SENDER)
            self._service = build('gmail', 'v1', credentials=credentials, cache_discovery=False)
        return self._service

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        try:
            service = self._get_service()
        except Exception:
            if self.fail_silently:
                return 0
            raise

        sent_count = 0
        for message in email_messages:
            try:
                self._send_one(service, message)
                sent_count += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent_count

    def _send_one(self, service, message):
        raw = base64.urlsafe_b64encode(message.message().as_bytes()).decode('ascii')
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
