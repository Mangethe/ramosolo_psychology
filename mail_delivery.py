"""Gmail transports. Credentials are read by the server-side worker only."""
import base64
import hashlib
import smtplib
import ssl
from email.headerregistry import Address
from email.message import EmailMessage
from urllib.parse import quote

import requests


GMAIL_FROM = 'clickfoundation.gp@gmail.com'
GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
SEND_URL = f'https://gmail.googleapis.com/gmail/v1/users/{quote(GMAIL_FROM, safe="")}/messages/send'


class DeliveryFailure(Exception):
    def __init__(self, reason, *, outcome='failed', retry_after=0):
        super().__init__(reason)
        self.reason = reason
        self.outcome = outcome
        self.retry_after = retry_after


def address(value):
    if not isinstance(value, str) or len(value) > 254 or any(char.isspace() for char in value):
        raise ValueError('Expected one mailbox.')
    parsed = Address(addr_spec=value)
    if not parsed.username or '.' not in parsed.domain or parsed.addr_spec != value:
        raise ValueError('Expected one mailbox.')
    return parsed


def client():
    connection = requests.Session()
    connection.trust_env = False
    return connection


class GmailProvider:
    live = True

    def __init__(self, config, *, http=None, smtp=None):
        self.mode = config['MAIL_PROVIDER']
        self.recipients = {address(value.strip()).addr_spec.lower()
                           for value in config['MAIL_PILOT_RECIPIENTS'].split(',') if value.strip()}
        self.daily_limit = config['GMAIL_DAILY_LIMIT']
        if not config['MAIL_LIVE_ENABLED'] or not self.recipients or not 1 <= self.daily_limit <= 100:
            raise ValueError('Live Gmail requires approval, a recipient allowlist and a daily pilot limit.')
        self.display_name = config['MAIL_DISPLAY_NAME']
        self.reply_to = address(config['MAIL_REPLY_TO']) if config['MAIL_REPLY_TO'] else None
        self.sender = Address(display_name=self.display_name, addr_spec=GMAIL_FROM)
        self.http = http if http is not None else client()
        self.smtp = smtp or smtplib.SMTP_SSL
        self.access_token = None
        if self.mode == 'gmail-oauth':
            self.refresh = {field: config['GMAIL_OAUTH_' + field.upper()]
                            for field in ('client_id', 'client_secret', 'refresh_token')}
            if not all(self.refresh.values()):
                raise ValueError('Gmail OAuth worker configuration is incomplete.')
        elif self.mode == 'gmail-smtp-app-password':
            self.password = (config['GMAIL_APP_PASSWORD'] or '').replace(' ', '')
            if not self.password:
                raise ValueError('Configure a dedicated Gmail app password.')
        else:
            raise ValueError('Unknown live email transport.')

    def accepts(self, recipient):
        return recipient.lower() in self.recipients

    def envelope(self, message):
        mail = EmailMessage()
        mail['From'] = self.sender
        mail['To'] = address(message.recipient)
        if self.reply_to:
            mail['Reply-To'] = self.reply_to
        mail['Subject'] = message.subject
        identity = hashlib.sha256(message.idempotency_key.encode()).hexdigest()
        mail['Message-ID'] = f'<{identity}@ramosolo.invalid>'
        mail.set_content(message.body)
        return mail

    def refresh_token(self):
        try:
            response = self.http.post(TOKEN_URL, data={**self.refresh, 'grant_type': 'refresh_token'},
                                      timeout=(4, 10), allow_redirects=False)
            if response.status_code == 429:
                raise DeliveryFailure('oauth_quota', outcome='quota', retry_after=300)
            if response.status_code >= 500:
                raise DeliveryFailure('oauth_unavailable', outcome='retry')
            if response.status_code != 200:
                raise DeliveryFailure('oauth_rejected')
            grant = response.json()
            if not isinstance(grant, dict):
                raise DeliveryFailure('oauth_invalid_response')
            scope = grant.get('scope')
            if scope is not None and (not isinstance(scope, str) or set(scope.split()) != {GMAIL_SCOPE}):
                raise DeliveryFailure('oauth_scope')
            token = grant.get('access_token')
            if not isinstance(token, str) or not token:
                raise DeliveryFailure('oauth_invalid_response')
            self.access_token = token
        except requests.RequestException:
            raise DeliveryFailure('oauth_unavailable', outcome='retry') from None
        except (TypeError, ValueError):
            raise DeliveryFailure('oauth_invalid_response') from None

    def send_api(self, mail):
        raw = base64.urlsafe_b64encode(mail.as_bytes()).decode('ascii')
        for _ in range(2):
            if self.access_token is None:
                self.refresh_token()
            try:
                response = self.http.post(SEND_URL, json={'raw': raw},
                    headers={'Authorization': 'Bearer ' + self.access_token}, timeout=(4, 12),
                    allow_redirects=False)
            except requests.ConnectTimeout:
                raise DeliveryFailure('gmail_connect_timeout', outcome='retry') from None
            except requests.RequestException:
                raise DeliveryFailure('gmail_outcome_unknown', outcome='uncertain') from None
            if response.status_code != 401:
                break
            self.access_token = None
        try:
            result = response.json()
        except (ValueError, TypeError):
            result = {}
        if not isinstance(result, dict):
            result = {}
        if response.status_code == 200 and isinstance(result.get('id'), str) and result['id']:
            return
        error = result.get('error')
        entries = error.get('errors', []) if isinstance(error, dict) else []
        reasons = {entry.get('reason') for entry in (entries or []) if isinstance(entry, dict)}
        if response.status_code == 429 or reasons & {'rateLimitExceeded', 'userRateLimitExceeded',
                                                      'dailyLimitExceeded', 'quotaExceeded'}:
            value = response.headers.get('Retry-After', '')
            seconds = int(value) if value.isascii() and value.isdecimal() and len(value) <= 6 else 3600
            raise DeliveryFailure('gmail_quota', outcome='quota', retry_after=max(300, min(86400, seconds)))
        if response.status_code >= 500 or 200 <= response.status_code < 300:
            raise DeliveryFailure('gmail_outcome_unknown', outcome='uncertain')
        raise DeliveryFailure('gmail_rejected')

    def send_smtp(self, mail, recipient):
        transport = None
        transmitting = False
        try:
            transport = self.smtp('smtp.gmail.com', 465, timeout=12, context=ssl.create_default_context())
            transport.login(GMAIL_FROM, self.password)
            transmitting = True
            transport.send_message(mail, from_addr=GMAIL_FROM, to_addrs=[recipient])
        except smtplib.SMTPRecipientsRefused as error:
            code, _ = error.recipients.get(recipient, (550, b''))
            raise DeliveryFailure('smtp_recipient_rejected', outcome='retry' if 400 <= code < 500 else 'failed') from None
        except smtplib.SMTPResponseException as error:
            if error.smtp_code in (421, 450, 452) or (error.smtp_code == 550 and b'5.4.5' in error.smtp_error):
                raise DeliveryFailure('smtp_throttled', outcome='quota', retry_after=3600) from None
            raise DeliveryFailure('smtp_rejected',
                outcome='retry' if 400 <= error.smtp_code < 500 else 'failed') from None
        except (OSError, smtplib.SMTPException):
            raise DeliveryFailure('smtp_outcome_unknown' if transmitting else 'smtp_unavailable',
                                  outcome='uncertain' if transmitting else 'retry') from None
        finally:
            if transport is not None:
                transport.close()

    def send(self, message):
        if not self.accepts(message.recipient):
            raise DeliveryFailure('outside_gmail_pilot', outcome='hold', retry_after=3600)
        try:
            mail = self.envelope(message)
        except ValueError:
            raise DeliveryFailure('invalid_mailbox') from None
        if self.mode == 'gmail-oauth':
            self.send_api(mail)
        else:
            self.send_smtp(mail, message.recipient)
