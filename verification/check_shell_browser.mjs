// Headless browser regression harness. Node core APIs only; no frontend package.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';

const output=fs.mkdtempSync('C:/Temp/ramosolo-shell-');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const server=spawn('python',['-u','verification/shell_preview.py'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
let chrome,ws,diagnose;
let serverDiagnostics='';
server.stderr.on('data',data=>{serverDiagnostics=(serverDiagnostics+data.toString()).slice(-2000);});
const report={synthetic:true,externalRequests:[],checks:[],screenshots:[],output,authRequestOrigins:[]};
try {
  const port=await new Promise((resolve,reject)=>{
    let buffer='';const timer=setTimeout(()=>reject(new Error('Synthetic preview startup timed out')),25000);
    server.stdout.on('data',data=>{buffer+=data;const line=buffer.split('\n').find(x=>x.startsWith('{'));
      if(line){clearTimeout(timer);resolve(JSON.parse(line).port);}});
    server.on('exit',code=>reject(new Error('Synthetic preview exited '+code)));
  });
  const origin='http://127.0.0.1:'+port;
  const profile=path.join(output,'isolated-chrome-profile');
  chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
    '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
    '--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'
  ],{windowsHide:true,stdio:'ignore'});
  let debugPort;
  for(let attempt=0;attempt<100;attempt++){
    const portFile=path.join(profile,'DevToolsActivePort');
    if(fs.existsSync(portFile)){debugPort=fs.readFileSync(portFile,'utf8').split('\n')[0];break;}
    await pause(150);
  }
  assert(debugPort,'Isolated headless Chrome did not start');
  const targets=await (await fetch('http://127.0.0.1:'+debugPort+'/json/list')).json();
  const target=targets.find(t=>t.type==='page');assert(target);
  ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  let seq=0;const pending=new Map();
  function cdp(method,params={}){return new Promise((resolve,reject)=>{
    const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));
  });}
  ws.onmessage=async event=>{
    const data=JSON.parse(event.data);
    if(data.id){const task=pending.get(data.id);pending.delete(data.id);
      if(data.error)task.reject(new Error(data.error.message));else task.resolve(data.result);}
    if(data.method==='Fetch.requestPaused'){
      const {requestId,request}=data.params;
      if(request.method==='POST'&&request.url.endsWith('/auth/login'))report.authRequestOrigins.push({
        destination:new URL(request.url).origin,origin:request.headers.Origin,site:request.headers['Sec-Fetch-Site']});
      if(request.url.startsWith(origin+'/')||request.url.startsWith('data:'))await cdp('Fetch.continueRequest',{requestId});
      else{report.externalRequests.push(new URL(request.url).origin);await cdp('Fetch.failRequest',{requestId,errorReason:'BlockedByClient'});}
    }
  };
  await cdp('Page.enable');await cdp('Runtime.enable');
  await cdp('Fetch.enable',{patterns:[{urlPattern:'*'}]});
  async function evaluate(expression){const result=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(result.exceptionDetails)throw new Error('Browser evaluation failed');return result.result.value;}
  diagnose=()=>evaluate('({path:location.pathname,text:document.body.innerText.slice(0,2000)})');
  async function until(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await pause(50);}throw new Error('Browser condition timed out: '+expression);}
  async function navigate(route){
    const previous=await evaluate('performance.timeOrigin');
    await cdp('Page.navigate',{url:origin+route});
    await until(`performance.timeOrigin!==${previous} && location.pathname===${JSON.stringify(route)} && document.readyState==='complete'`);
  }
  async function viewport(width,height){await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<768});}
  async function screenshot(name){await evaluate('window.scrollTo(0,0)');await pause(100);const metrics=await cdp('Page.getLayoutMetrics');
    const result=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,
      clip:{x:0,y:0,width:metrics.cssContentSize.width,height:metrics.cssContentSize.height,scale:1}});
    const filename=path.join(output,name+'.png');fs.writeFileSync(filename,Buffer.from(result.data,'base64'));report.screenshots.push(filename);}
  async function fit(label){const dimensions=await evaluate('({viewport:innerWidth,scroll:document.documentElement.scrollWidth})');
    assert(dimensions.scroll<=dimensions.viewport+1,label+' overflows viewport '+JSON.stringify(dimensions));report.checks.push(label+': no document horizontal overflow');}
  async function key(key,code=key){const virtualCode={Enter:13,Tab:9,ArrowRight:39}[key];assert(virtualCode);
    await cdp('Input.dispatchKeyEvent',{type:'keyDown',key,code,
      windowsVirtualKeyCode:virtualCode,...(key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{})});
    await cdp('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:virtualCode});
    await pause(50);
  }
  async function responseAudit(role){
    const result=await evaluate(`(async()=>{
      const forbidden=['SYNTHETIC_BROWSER_SECRET_8a73','SYNTHETIC_BROWSER_FOREIGN_PATIENT_2b19','SYNTHETIC_BROWSER_CLINICAL_743a'];
      const clean=text=>!forbidden.some(value=>text.includes(value));
      const links=[...new Set([...document.querySelectorAll('header a[href],nav a[href],footer a[href]')]
        .map(a=>a.href).filter(h=>new URL(h).origin===location.origin))];
      const broken=[];
      for(const href of links){const response=await fetch(href);const text=await response.text();
        if(response.status!==200||!clean(text))broken.push(new URL(href).pathname);
        const fragment=new URL(href).hash;
        if(fragment&&!new DOMParser().parseFromString(text,'text/html').getElementById(fragment.slice(1)))broken.push('fragment:'+fragment);
      }
      const denied=['/.env','/.git/config','/app.py','/console','/static/app.py','/static/.env',
        '/static/css/style.css.map','/med/patients/2','/med/patients/2/records/diagnoses'];
      const exposed=[];
      for(const href of denied){const response=await fetch(href);const text=await response.text();
        if(![302,400,403,404].includes(response.status)&&!response.redirected)exposed.push(href);
        if(!clean(text)||text.includes('Werkzeug Debugger'))exposed.push(href);
      }
      const css=await (await fetch('/static/css/style.css')).text();
      return {broken,exposed,clean:clean(document.documentElement.outerHTML)&&clean(css),
        cleanStorage:clean(JSON.stringify({...localStorage,...sessionStorage})),links:links.length};
    })()`);
    assert.deepEqual(result.broken,[],role+' navigation/footer links');
    assert.deepEqual(result.exposed,[],role+' direct URL exposure');
    assert(result.clean&&result.cleanStorage,role+' response/storage canaries');
    report.checks.push(role+': '+result.links+' local navigation/footer targets and fragments return authorized pages');
    report.checks.push(role+': HTML, CSS, denied responses and browser storage exclude synthetic secret/foreign record canaries');
  }
  await viewport(1440,1000);await navigate('/');await fit('Desktop public home');await screenshot('public-desktop');
  await responseAudit('anonymous');
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.mobile-public-menu')).display"),'none');
  await key('Tab');assert.equal(await evaluate('document.activeElement.className'),'skip');await key('Enter');
  assert.equal(await evaluate('document.activeElement.id'),'main');report.checks.push('Keyboard skip link focuses main');
  await viewport(390,844);await navigate('/');await fit('Mobile public home');await screenshot('public-mobile');
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.desktop-public-nav')).display"),'none');
  await evaluate("document.querySelector('.mobile-public-menu summary').focus()");await key('Enter');
  assert.equal(await evaluate("document.querySelector('.mobile-public-menu').open"),true);
  await key('Tab');assert.equal(await evaluate('document.activeElement.textContent.trim()'),'Home');
  await screenshot('public-mobile-menu');report.checks.push('Mobile public menu opens by Enter; Tab reaches Home');
  await cdp('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"),true);
  report.checks.push('Reduced-motion media query active');
  for(const route of ['/inpatient','/governance','/privacy-notice','/data-management','/professional-information','/book','/auth/login']){
    await navigate(route);await fit('Mobile '+route);
    if(['/privacy-notice','/data-management','/professional-information'].includes(route)){
      assert.equal(await evaluate("document.querySelector('.policy-draft strong').textContent.includes('Unpublished')"),true);
      await viewport(1440,1000);await fit('Desktop '+route);
      if(route==='/privacy-notice')await screenshot('privacy-draft-desktop');
      await viewport(390,844);
      if(route==='/professional-information')await screenshot('professional-draft-mobile');
    }
  }
  await screenshot('login-mobile');
  for(const role of ['patient','dr_assist','nurse','dr','admin']){
    await navigate('/auth/login');
    await evaluate(`document.querySelector('[name=email]').value=${JSON.stringify(role+'@example.test')};document.querySelector('[name=password]').value='Synthetic-preview-123!';document.querySelector('.login-panel form').requestSubmit();`);
    await until("location.pathname==='/med' && document.readyState==='complete' && document.querySelector('.workspace-main')!==null");
    await fit('Mobile '+role+' workspace');
    await evaluate("document.querySelector('.mobile-workspace-menu summary').focus()");await key('Enter');
    assert.equal(await evaluate("document.querySelector('.mobile-workspace-menu').open"),true);
    await key('Tab');assert.equal(await evaluate('document.activeElement.textContent.trim()'),'Overview');
    report.checks.push(role+': workspace menu keyboard navigation and authenticated CSRF login');
    await responseAudit(role);
    if(role==='dr_assist'){
      await screenshot('assistant-mobile-menu');
      await evaluate("document.querySelector('.mobile-workspace-menu summary').focus()");await key('Enter');
      assert.equal(await evaluate("document.querySelector('.mobile-workspace-menu').open"),false);
      await evaluate("document.querySelector('.table-wrap').focus()");await key('ArrowRight');
      await until("document.querySelector('.table-wrap').scrollLeft>0");
      report.checks.push('Mobile appointment table scrolls with ArrowRight when keyboard focused');
      await screenshot('assistant-mobile-table');
      await viewport(1440,1000);await screenshot('assistant-desktop');
    }
    await viewport(1440,1000);await fit('Desktop '+role+' workspace');await viewport(390,844);
    await evaluate("document.querySelector('form[action=\"/auth/logout\"]').requestSubmit()");
    await until("location.pathname==='/' && document.querySelector('.public-hero')!==null");
  }
  const accessibility=await cdp('Accessibility.getFullAXTree');
  assert(accessibility.nodes.some(n=>n.role?.value==='main'));
  report.checks.push('Browser accessibility tree includes main landmark');
  assert.equal(report.externalRequests.length,0,'Unexpected external browser request');
  report.checks.push('No external page requests or chat integration');
  report.status='passed';
  fs.writeFileSync('verification/shell-browser-results.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
} catch(error){
  report.status='failed';report.error=error.message;report.stack=error.stack;
  if(diagnose)report.syntheticBrowserState=await diagnose();
  report.syntheticServerDiagnostics=serverDiagnostics;
  fs.writeFileSync('verification/shell-browser-results.json',JSON.stringify(report,null,2)+'\n');
  console.error(error.message);process.exitCode=1;
} finally {
  ws?.close();chrome?.kill();server.kill();
}
