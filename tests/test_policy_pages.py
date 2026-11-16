"""Policy drafts must describe evidence, not fabricate approval or contacts."""
from html.parser import HTMLParser
from pathlib import Path
import re
import pytest
from sqlalchemy import select,func
from test_medical import env,as_user
from test_security import seed_canaries,SECRET,CLINICAL
from extensions import db
from models import BookingRequest,CommunicationDecision,PatientPreference
from medical_services import utcnow
from datetime import timedelta
from policy_info import POLICY,OFFICIAL_LINKS,CARD


PAGES=('/privacy-notice','/data-management','/professional-information')


@pytest.mark.parametrize('role',[None,'patient','dr_assist','nurse','dr','admin'])
def test_drafts_public_for_all_roles_without_private_data(env,role):
    seed_canaries(env)
    client=as_user(env,role) if role else env[0].test_client()
    for path in PAGES:
        r=client.get(path);assert r.status_code==200
        body=r.get_data(as_text=True)
        assert 'Unpublished policy draft' in body and '0.1-draft' in body
        assert 'Effective date: Not effective' in body
        assert 'Approved privacy contact: not yet supplied' in body if path=='/privacy-notice' else True
        assert SECRET not in body and CLINICAL not in body
        assert 'FOREIGN PRIVATE PATIENT' not in body
        assert r.headers['Cache-Control']=='no-store'
        assert r.headers['X-Content-Type-Options']=='nosniff'
        assert '<script' not in body and '<iframe' not in body
        assert 'ls-launcher' not in body
        for typo in ('HSPCA','HPSCA','HPCAS'):assert typo not in body
        assert not re.search(r'(fully POPIA compliant|HPCSA approved)',body,re.I)


def test_footer_links_policy_pages_and_official_resources(env):
    for path in ['/','/book','/auth/login',*PAGES]:
        body=env[0].test_client().get(path).get_data(as_text=True)
        for target in PAGES:assert 'href="'+target+'"' in body
        for name in ('hpcsa','regulator'):assert 'href="'+OFFICIAL_LINKS[name]+'"' in body
        assert 'rel="noreferrer noopener external"' in body
    # External links carry no record/name/registration query payloads and are not embeds.
    for value in OFFICIAL_LINKS.values():
        assert value.startswith('https://') and '?' not in value


def test_card_attribution_numbers_and_privacy_contact_not_conflated(env):
    body=env[0].test_client().get('/professional-information').get_data(as_text=True)
    assert CARD['name'] in body and CARD['title'] in body and CARD['qualification'] in body
    assert 'Health Professions Council of South Africa' in body
    assert 'Prac. No.' in body and 'withheld pending practice confirmation' in body
    assert 'not an independent qualification or registration verification' in body
    assert 'No operating hours appear' in body
    assert 'Frances Baard' in body
    for text in CARD['services']:assert text in body
    for field in ('cell','telephone','fax','email'):assert CARD[field] in body
    assert 'mailto:' not in body and 'href="tel:' not in body
    assert POLICY['privacy_contact'] is None and POLICY['legal_entity'] is None
    assert not any('registration' in key or 'practice_number' in key for key in CARD)
    # A suspected number from the image must not accidentally be promoted to public content.
    assert '0338842' not in body


def test_declaration_preserves_unknowns_and_actual_integration_limits(env):
    body=env[0].test_client().get('/data-management').get_data(as_text=True)
    for expected in ('Supabase PostgreSQL','processing region','have not been confirmed',
        'No country or region is asserted','No approved practice retention schedule',
        'not production backup or disaster-recovery tests','not continuously monitored',
        'synthetic delivery','sandbox notification','no external AI service',
        'does not call a live payment gateway','no automated regulatory filing'):
        assert expected in body,expected
    assert 'end-to-end encryption or guarantee confidentiality' in body  # explicit non-claim


def test_privacy_required_optional_recipients_requests_children_and_complaints(env):
    body=env[0].test_client().get('/privacy-notice').get_data(as_text=True)
    for expected in ('Required and optional information','Who may receive information','withdrawal',
        'Proposed process for owner approval','verify identity','retention restrictions',
        'approved child/guardian-consent and access policy has not been provided',
        'does not automatically erase care records','No Information Officer',
        'Optional communication consent is not presented as the basis for every healthcare-processing activity'):
        assert expected in body,expected
    assert OFFICIAL_LINKS['complaints'] in body and OFFICIAL_LINKS['popia_forms'] in body


def test_booking_privacy_link_and_narrow_contact_agreement_does_not_grant_optional_consent(env):
    client=env[0].test_client();body=client.get('/book').get_data(as_text=True)
    assert 'href="/privacy-notice"' in body
    assert 'appointment enquiry only' in body
    assert 'does not opt me into marketing or referral-information sharing' in body
    assert 'unpublished draft' in body
    form={'full_name':'Synthetic policy enquiry','email':'policy@example.test','phone':'0000000000',
        'service_type':'Individual therapy','preferred_at':(utcnow()+timedelta(days=3)).isoformat(timespec='minutes'),
        'consent':'on','marketing':'on','referral_sharing':'on'}
    assert client.post('/book',data=form).status_code==302
    assert db.session.scalar(select(func.count(BookingRequest.id)))==1
    assert db.session.scalar(select(func.count(CommunicationDecision.id)))==0
    assert db.session.scalar(select(func.count(PatientPreference.id)))==0
    form.pop('consent');assert client.post('/book',data=form).status_code==400
    assert db.session.scalar(select(func.count(BookingRequest.id)))==1


def test_booking_csrf_and_policy_route_methods(env):
    env[0].config['WTF_CSRF_ENABLED']=True;client=env[0].test_client()
    assert client.post('/book',data={'consent':'on'}).status_code==400
    for path in PAGES:assert client.post(path).status_code==405  # read-only routes have no POST handler
    env[0].config['WTF_CSRF_ENABLED']=False
    for path in PAGES:assert client.post(path).status_code==405
    assert client.get('/docs/privacy-owner-checklist.md').status_code==404
    assert client.get('/static/privacy-owner-checklist.md').status_code==404
