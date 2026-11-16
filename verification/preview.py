"""Immutable synthetic template snapshots for browser QA; no live database or integrations."""
import os
os.environ['PYTHON_DOTENV_DISABLED']='1'
os.environ['APP_ENV']='test'
os.environ['DATABASE_URL']='sqlite://'
os.environ['FLASK_SECRET_KEY']='synthetic-layout-review-only'
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from test_medical import env, as_user
from test_continuity import approve, create_event, submit, event, plan_form

generator=env.__wrapped__()
case=next(generator)
pages={}
try:
    with case[0].app_context():
        approve(case);create_event(case);submit(case)
        identity=event().id
        form=plan_form(case);form['share_with_patient']='on'
        as_user(case,'dr').post(f'/med/patients/{case[2][0].id}/care-plan',data=form)
        for role,paths in {
            'dr':['/med','/med/permissions','/med/continuity','/med/charts/continuity',
                  f'/med/continuity/{identity}',f'/med/patients/{case[2][0].id}/care-plan',
                  f'/med/patients/{case[2][0].id}/permissions',f'/med/patients/{case[2][0].id}/records/diagnoses'],
            'patient':['/med/my-care-plan','/med/check-in','/med/preferences'],
            'admin':['/med/exports']}.items():
            client=as_user(case,role)
            for path in paths:
                response=client.get(path)
                if response.status_code!=200:raise RuntimeError('Synthetic preview failed: '+path)
                pages[path]=response.data
finally:
    try:next(generator)
    except StopIteration:pass
css=(Path(__file__).resolve().parents[1]/'static/css/style.css').read_bytes()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlparse(self.path).path
        content=css if path=='/static/css/style.css' else pages.get(path)
        if content is None:self.send_error(404);return
        self.send_response(200)
        self.send_header('Content-Type','text/css' if path=='/static/css/style.css' else 'text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(content)
    def log_message(self,*args):pass

print('Synthetic read-only preview: http://127.0.0.1:5057/med/permissions',flush=True)
HTTPServer(('127.0.0.1',5057),Handler).serve_forever()
