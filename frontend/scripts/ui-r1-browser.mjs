/** Local browser acceptance via Chromium CDP, no package dependency.
 * Start Vite on 127.0.0.1:5181 and Chromium with --remote-debugging-port=9331.
 * All API responses below are TEST-ISOLATED synthetic fixtures. No product DB or public source requests.
 * node scripts/ui-r1-browser.mjs [artifact-directory]
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out = path.resolve(process.argv[2] ?? '../backend/reports/ui_r1/browser');
await fs.mkdir(out, { recursive: true });
const tabs = await (await fetch('http://127.0.0.1:9331/json')).json();
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));
let sequence = 0; const pending = new Map(); const errors = []; const writes = []; const requests = [];
function call(method, params = {}) {
  return new Promise((resolve, reject) => { const id = ++sequence;pending.set(id, { resolve, reject });ws.send(JSON.stringify({id,method,params})); });
}
const tender = {id:'ui-r1-synthetic',title:'Expediente sintético de revisión UI-R1',external_reference:'UIR1-LOCAL-ONLY',institution_profile:'General',status:'DRAFT',created_at:'2026-10-23T12:00:00Z',updated_at:'2026-10-23T12:00:00Z'};
function fixture(url) {
 const p = new URL(url).pathname;
 if(p === '/tenders')return [tender];
 if(p === `/tenders/${tender.id}`)return tender;
 if(p === '/companies' || p.endsWith('/documents') || p.endsWith('/providers') || p.endsWith('/scope-review') || p.endsWith('/technical-alternatives'))return [];
 if(p.endsWith('/workspace'))return {tender_id:tender.id,processing:{status:'NOT_PROCESSED',run_id:null,error_code:null,context_sha256:null},scopes:[],requirements:{scope_note:'Fixture sintética aislada',requirements:[]},semantics:{scope_note:'Fixture sintética aislada',requirements:[]},warnings:[]};
 return undefined;
}
ws.addEventListener('message', async event => {
 const m=JSON.parse(event.data);
 if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}return;}
 if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text+': '+(m.params.exceptionDetails.exception?.description??''));
 if(m.method==='Fetch.requestPaused') {
  const {requestId,request}=m.params;requests.push(request.url);
  if(request.method!=='GET' && request.method!=='OPTIONS')writes.push(request.url);
  const value=fixture(request.url);
  await call('Fetch.fulfillRequest',{requestId,responseCode:request.method==='OPTIONS'?204:value===undefined?503:200,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'*'},{name:'Access-Control-Allow-Headers',value:'*'}],body:Buffer.from(JSON.stringify(value??{detail:'TEST_ISOLATED_UNAVAILABLE'})).toString('base64')});
 }
});
await call('Page.enable');await call('Runtime.enable');
await call('Fetch.enable',{patterns:[{urlPattern:'http://localhost:8000/*'},{urlPattern:'http://127.0.0.1:8000/*'}]});
async function evaluate(expression){const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.text);return result.result.value;}
async function until(expression){const deadline=Date.now()+12000;while(Date.now()<deadline){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,75));}throw new Error('Timeout: '+expression);}
async function go(route){await evaluate(`location.hash=${JSON.stringify(route)}`);await until(`document.querySelector('h1')!==null`);await new Promise(resolve=>setTimeout(resolve,250));}
async function size(width,height){await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});}
async function shot(name){const data=await call('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(out,name+'.png'),Buffer.from(data.data,'base64'));}
const checks=[];
try {
 await size(1366,768);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/'});await until(`document.querySelector('h1')?.textContent==='Inicio'`);
 assert.equal(await evaluate('document.title'),'RX23 TuScope');assert.equal(await evaluate('document.documentElement.lang'),'es-MX');
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('.shell-menu')).display`),'none');await shot('01-inicio-1366');checks.push('branding/title/lang/Inicio');
 await evaluate('document.body.tabIndex=-1;document.body.focus()');
 await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
 assert.equal(await evaluate(`document.activeElement.textContent`),'Saltar al contenido');checks.push('keyboard skip link');
 await go('/discovery');assert.equal(await evaluate(`document.querySelector('nav[aria-label="Navegación principal"] a[aria-current]')?.textContent`),'Discovery');await shot('02-discovery-1366');
 await go(`/licitaciones/${tender.id}/resumen`);await until(`document.querySelector('h1')?.textContent===${JSON.stringify(tender.title)}`);
 assert.equal(await evaluate(`document.querySelectorAll('.tender-context-nav a').length`),8);await evaluate('window.scrollTo(0,0)');await shot('03-tender-context-1366');checks.push('Tender contextual identity / all 8 sections');
 const readsBeforeContext = requests.length;
 for(const section of ['documentos','requisitos','cumplimiento','partidas','comercial','preparacion','propuesta']){await go(`/licitaciones/${tender.id}/${section}`);assert.equal(await evaluate(`document.querySelector('.tender-context-nav a[aria-current]')?.getAttribute('href')`),`#/licitaciones/${tender.id}/${section}`);}
 assert.equal(requests.length,readsBeforeContext);checks.push('all context routes / Proposal reachable / no refetch across context tabs');
 for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]){await size(width,height);await go('/');assert.ok(await evaluate(`document.documentElement.scrollWidth<=${width}`));assert.equal(await evaluate(`getComputedStyle(document.querySelector('.shell-menu')).display`),'none');assert.equal(await evaluate(`document.querySelector('.global-sidebar').getBoundingClientRect().left`),0);assert.ok(await evaluate(`document.querySelector('.main-workspace').getBoundingClientRect().left>=250`));assert.ok(await evaluate(`document.querySelector('h1').getBoundingClientRect().right<=${width}`));await shot(`04-desktop-${width}x${height}`);checks.push(`${width}x${height}: no page overflow / header visible`);}
 await go('/configuracion');await shot('05-configuracion');await go('/configuracion/diagnostico');await shot('06-diagnostico');checks.push('configuration / diagnostics reachable');
 await size(768,900);await go('/');assert.equal(await evaluate(`getComputedStyle(document.querySelector('.global-sidebar')).display`),'none');
 await evaluate(`document.querySelector('.shell-menu').click()`);assert.equal(await evaluate(`document.querySelector('.shell-menu').getAttribute('aria-expanded')`),'true');
 assert.ok(await evaluate(`document.documentElement.scrollWidth<=768`));await shot('07-narrow-menu-768');
 await evaluate(`document.querySelector('.global-sidebar a[href="#/discovery"]').click()`);await until(`document.querySelector('h1')?.textContent==='Discovery'`);
 assert.equal(await evaluate(`document.querySelector('.shell-menu').getAttribute('aria-expanded')`),'false');checks.push('narrow menu expands / navigates / collapses without overlap');
 await go(`/licitaciones/${tender.id}/documentos`);assert.ok(await evaluate('document.documentElement.scrollWidth<=768'));await shot('08-narrow-tender-768');
 await size(390,844);await go('/');assert.ok(await evaluate('document.documentElement.scrollWidth<=390'));await shot('09-narrow-390');checks.push('390x844: navigation and content fit');
 await go('/not-a-route');assert.equal(await evaluate(`document.querySelector('h1').textContent`),'Página no encontrada');checks.push('not found fallback');
 const contrast = await evaluate(`(()=>{const rgb=h=>h.match(/../g).map(x=>parseInt(x,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);const l=h=>rgb(h).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);return [['191c1e','f7f9fb'],['eff1f3','091426'],['ffffff','1d4ed8']].map(([a,b])=>(Math.max(l(a),l(b))+.05)/(Math.min(l(a),l(b))+.05))})()`);assert.ok(contrast.every(r=>r>=4.5));checks.push('shell text/nav/action contrast >=4.5:1');
 assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);checks.push('no API writes or runtime exceptions');
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',fixture:'TEST_ISOLATED_SYNTHETIC_API',checks,errors,writes},null,2));console.log(JSON.stringify({status:'PASS',checks:checks.length,artifacts:out}));
} finally {ws.close();}
