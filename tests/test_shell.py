"""Template/route checks; these do not claim browser layout verification."""
from html.parser import HTMLParser
from xml.etree import ElementTree
from urllib.parse import urlsplit
from pathlib import Path
import pytest
from policy_info import CARD
from test_medical import env,as_user


class Page(HTMLParser):
    def __init__(self,body):
        super().__init__();self.links=[];self.ids=[];self.scripts=[];self.styles=[];self.forms=[]
        self.feed(body)

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get('id'):self.ids.append(attrs['id'])
        if tag=='a':self.links.append(attrs)
        if tag=='script':self.scripts.append(attrs)
        if tag=='link' and attrs.get('rel')=='stylesheet':self.styles.append(attrs)
        if tag=='form':self.forms.append(attrs)


@pytest.mark.parametrize('role',['patient','dr_assist','nurse','dr','admin','edu'])
def test_shell_role_navigation_and_public_appointment_are_separate(env,role):
    client=as_user(env,role);r=client.get('/med')
    assert r.status_code==200
    text=r.get_data(as_text=True);page=Page(text)
    assert page.ids.count('main')==1
    assert len(page.ids)==len(set(page.ids))
    assert any(a.get('href')=='#main' for a in page.links)
    assert any(a.get('href')=='/book' and 'appointment-action' in a.get('class','') for a in page.links)
    assert text.count('partials/_chat')==0 and 'ls-launcher' not in text
    assert page.scripts == [{'src': '/static/js/session-warning.js', 'defer': None}]
    assert len(page.styles)==1 and page.styles[0]['href'].endswith('/static/css/style.css')
    assert any(f.get('action')=='/auth/logout' and f.get('method')=='post' for f in page.forms)
    assert 'name="csrf_token"' in text
    assert 'Other Doctor Patient' not in text if role in ('dr','dr_assist','nurse','patient') else True
    assert 'FOREIGN PRIVATE PATIENT' not in text
    hrefs={a.get('href') for a in page.links}
    if role=='patient':
        assert '/med/my-care-plan' in hrefs and '/med/preferences' in hrefs
        assert '/med/patients' not in hrefs and '/admin/users' not in hrefs and '/med/calendar' not in hrefs
    if role=='dr_assist':assert '/med/calendar' in hrefs and '/med/admissions' not in hrefs and '/admin/users' not in hrefs
    if role=='nurse':assert '/med/calendar' not in hrefs and '/med/exports' not in hrefs
    if role=='admin':assert '/admin/users' in hrefs
    if role=='edu':assert '/med/patients' not in hrefs and '/med/appointments' not in hrefs
    active=[a for a in page.links if a.get('aria-current')=='page']
    assert any(a.get('href')=='/med' for a in active)
    # Navigation exposes only GET routes that the current role is authorized to open.
    for path in hrefs:
        if path and path.startswith('/') and urlsplit(path).path not in ('/','/book','/auth/login'):
            response=client.get(path)
            assert response.status_code==200,(role,path,response.status_code)


@pytest.mark.parametrize('path',['/','/inpatient','/governance','/book','/auth/login'])
def test_public_shell_links_contact_details_and_no_external_dependencies(env,path):
    r=env[0].test_client().get(path);assert r.status_code==200
    text=r.get_data(as_text=True);page=Page(text)
    assert 'Ponky Ramosolo' in text
    for old in ['Ramasolo','Ms. P.','374 Francis','clinicalpsychologistp@gmail.com','Akeso']:
        assert old not in text
    footer = text.split('<footer class="site-footer">', 1)[1].split('</footer>', 1)[0]
    assert all(CARD[field] in footer for field in ('address', 'cell', 'telephone', 'fax', 'email'))
    expected_scripts = [{'src': '/static/js/general-questions.js', 'defer': None}] if path in ('/', '/inpatient') else []
    assert page.scripts == expected_scripts
    assert ('general-questions' in page.ids) == bool(expected_scripts)
    assert all(not a.get('href','').startswith(('https://fonts.','https://cdn.')) for a in page.links)
    assert all(link['href'].startswith('/static/') for link in page.styles)
    assert 'ls-launcher' not in text and 'chat.message' not in text and '<style' not in text
    assert 'id="main"' in text and 'tabindex="-1"' in text
    assert 'mobile-public-menu' in text and '<summary>Menu</summary>' in text
    for a in page.links:
        href=a.get('href','')
        if href.startswith('/') and '#' in href:
            route,fragment=href.split('#',1)
            target=Page(env[0].test_client().get(route).get_data(as_text=True))
            assert fragment in target.ids,(href,path)


def test_css_asset_focus_motion_and_disclosures(env):
    response=env[0].test_client().get('/static/css/style.css')
    assert response.status_code==200 and response.mimetype=='text/css'
    css=response.get_data(as_text=True)
    assert ':focus-visible' in css and 'prefers-reduced-motion' in css
    assert 'mobile-public-menu' in css and 'mobile-workspace-menu' in css
    assert '@import' not in css and 'fonts.googleapis' not in css
    assert 'font-family:system-ui' in css and '#002f4a' in css
    for filename in ['base.html','portal.html']:
        source=(Path('templates')/filename).read_text(encoding='utf-8')
        assert source.index('block framework_css')<source.index('css/style.css')
        for block in ['title','content','head','extra_css','scripts']:assert 'block '+block in source
        assert "include 'partials/_navbar.html'" in source and "include 'partials/_footer.html'" in source
        assert "include 'partials/flashes.html'" in source


def test_sitemap_uses_configured_origin_and_public_routes(env):
    app = env[0]
    app.config['AUTH_PUBLIC_URL'] = 'https://portal.example.test/'
    client = app.test_client()
    response = client.get('/sitemap.xml?example=synthetic', headers={'Host': 'untrusted.example.test'})
    assert response.status_code == 200 and response.mimetype == 'application/xml'
    namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locations = [item.text for item in ElementTree.fromstring(response.data).findall('s:url/s:loc', namespace)]
    assert set(locations) == {'https://portal.example.test' + path for path in
                              ('/', '/book', '/inpatient', '/governance', '/sitemap')}

    html_links = {link.get('href') for link in Page(client.get('/sitemap').get_data(as_text=True)).links}
    assert {'/cookies-policy', '/privacy-notice', '/sitemap.xml', '/#general-questions'} <= html_links
    assert b'general-questions.js' not in as_user(env, 'patient').get('/').data
