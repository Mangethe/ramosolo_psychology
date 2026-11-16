"""Public official-link probes only. No logins, cookies, records or submissions."""
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from policy_info import OFFICIAL_LINKS


def check(item):
    name,url=item
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 (official-link-review)'}),timeout=12) as response:
            # Metadata only; do not copy website bodies/cookies into artifacts.
            return {'name':name,'url':url,'status':response.status,'final_url':response.url}
    except HTTPError as error:
        return {'name':name,'url':url,'status':error.code,'result':'http_error'}
    except (URLError,TimeoutError,OSError):
        return {'name':name,'url':url,'status':None,'result':'unverified_connection_or_timeout'}


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=9) as pool:results=list(pool.map(check,OFFICIAL_LINKS.items()))
    result={'checked_date':'2026-11-16','method':'public HTTPS GET; status/redirect metadata only','links':results}
    Path('verification/policy-official-links.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
