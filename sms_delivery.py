"""Outbound SMS provider contract. No inbound provider callbacks are used."""
import re
import secrets
import time
from typing import Protocol

import requests

from mail_delivery import client


class ProviderUnavailable(Exception):
    """The provider did not make a trustworthy decision."""


class VerificationProvider(Protocol):
    def send(self, number: str) -> str: ...

    def check(self, reference: str, number: str, code: str) -> bool: ...

    def notify_change(self, number: str) -> None: ...


class FakeSMSProvider:
    """In-process fixture adapter. Resends keep the same code until approval."""
    def __init__(self, clock=time.time, validity=600):
        self.challenges = {}
        self.notices = []
        self.clock = clock
        self.validity = validity

    def send(self, number):
        existing = self.challenges.get(number)
        if existing and existing[2] > self.clock():
            return existing[0]
        reference = secrets.token_urlsafe(24)
        self.challenges[number] = reference, f'{secrets.randbelow(1_000_000):06d}', self.clock() + self.validity
        return reference

    def check(self, reference, number, code):
        current = self.challenges.get(number)
        if not current or current[:2] != (reference, code) or current[2] <= self.clock():
            return False
        self.challenges.pop(number)
        return True

    def notify_change(self, number):
        self.notices.append(number)


class TwilioVerifyProvider:
    def __init__(self, config, *, http=None):
        self.account = self.sid(config['TWILIO_ACCOUNT_SID'], 'AC')
        self.service = self.sid(config['TWILIO_VERIFY_SERVICE_SID'], 'VA')
        self.messaging = self.sid(config['TWILIO_SECURITY_MESSAGING_SERVICE_SID'], 'MG')
        self.auth = (self.sid(config['TWILIO_API_KEY'], 'SK'), config['TWILIO_API_SECRET'])
        if not self.auth[1]:
            raise ValueError('Twilio API configuration is incomplete.')
        self.http = http if http is not None else client()
        self.base = f'https://verify.twilio.com/v2/Services/{self.service}/'

    @staticmethod
    def sid(value, prefix):
        if not isinstance(value, str) or not re.fullmatch(prefix + r'[0-9a-fA-F]{32}', value):
            raise ValueError('Invalid Twilio configuration identifier.')
        return value

    def post(self, url, data):
        try:
            response = self.http.post(url, data=data, auth=self.auth, timeout=(4, 10), allow_redirects=False)
            if response.status_code not in (200, 201):
                raise ProviderUnavailable()
            result = response.json()
            if not isinstance(result, dict):
                raise ProviderUnavailable()
            return result
        except (requests.RequestException, ValueError):
            raise ProviderUnavailable() from None

    def send(self, number):
        result = self.post(self.base + 'Verifications', {'To': number, 'Channel': 'sms', 'RiskCheck': 'enable'})
        if (result.get('status') != 'pending' or result.get('to') != number or result.get('account_sid') != self.account or
                result.get('service_sid') != self.service or result.get('channel') != 'sms'):
            raise ProviderUnavailable()
        return self.sid(result.get('sid'), 'VE')

    def check(self, reference, number, code):
        result = self.post(self.base + 'VerificationCheck', {'VerificationSid': self.sid(reference, 'VE'), 'Code': code})
        if (result.get('sid') != reference or result.get('to') != number or result.get('account_sid') != self.account or
                result.get('service_sid') != self.service or result.get('channel') != 'sms'):
            raise ProviderUnavailable()
        return result.get('status') == 'approved' and result.get('valid') is not False

    def notify_change(self, number):
        result = self.post(f'https://api.twilio.com/2010-04-01/Accounts/{self.account}/Messages.json',
            {'To': number, 'MessagingServiceSid': self.messaging,
             'Body': 'A change to your Ramosolo account phone was requested. Contact the practice if unexpected.'})
        if result.get('to') != number or result.get('status') not in ('accepted', 'queued', 'sending', 'sent'):
            raise ProviderUnavailable()
