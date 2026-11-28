"""Validate the public, institution-specific display configuration."""
import hashlib
import json
import re
from decimal import Decimal

from medical_services import SERVICES


def booking_terms_sha256(raw, institution_id):
    return hashlib.sha256(f'{institution_id}\n{raw}'.encode('utf-8')).hexdigest()


def approved_booking_terms(raw, institution_id, approved_sha256):
    if not raw or not institution_id or not approved_sha256:
        return {}
    if booking_terms_sha256(raw, institution_id) != approved_sha256.strip().lower():
        return {}
    return booking_terms(raw, institution_id)


def booking_terms(raw, institution_id):
    if not raw:
        return {}
    if not institution_id:
        raise RuntimeError('Booking terms require an explicit PUBLIC_INSTITUTION_ID.')
    try:
        schedules = json.loads(raw)
        if not isinstance(schedules, dict) or not schedules or schedules.keys() - set(SERVICES):
            raise ValueError
        for terms in schedules.values():
            if not isinstance(terms, dict) or set(terms) != {
                'currency', 'fee', 'deposit', 'cancellation', 'no_show', 'refund'
            }:
                raise ValueError
            if terms['currency'] != 'ZAR':
                raise ValueError
            fee, deposit = (terms[field] for field in ('fee', 'deposit'))
            if any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,9}\.[0-9]{2}', value)
                   for value in (fee, deposit)) or Decimal(deposit) > Decimal(fee):
                raise ValueError
            if any(not isinstance(terms[field], str) or not 1 <= len(terms[field].strip()) <= 800
                   for field in ('cancellation', 'no_show', 'refund')):
                raise ValueError
    except ValueError:
        raise RuntimeError('Configure valid public booking fees and terms.') from None
    return schedules
