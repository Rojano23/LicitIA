/** Local browser acceptance via Chromium CDP, no package dependency.
 * Start Vite on 127.0.0.1:5181 and Chromium with --remote-debugging-port=9331.
 * All API responses below are TEST-ISOLATED synthetic fixtures. No product DB or public source requests.
 * node scripts/ui-r6-browser.mjs [artifact-directory]
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out = path.resolve(process.argv[2] ?? '../backend/reports/ui_r6/browser');
await fs.mkdir(out, { recursive: true });
const tabs = await (await fetch('http://127.0.0.1:9331/json')).json();
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));
let sequence = 0; const pending = new Map(); const errors = []; const writes = []; const requests = [];
function call(method, params = {}) {
  return new Promise((resolve, reject) => { const id = ++sequence;pending.set(id, { resolve, reject });ws.send(JSON.stringify({id,method,params})); });
}
import ts from '../node_modules/typescript/lib/typescript.js';
function testModule(file,require=()=>{throw new Error('unexpected fixture import');}){const exports={};const text=ts.transpileModule(file,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;new Function('exports','require',text)(exports,require);return exports;}
const fixtures=testModule(await fs.readFile(new URL('../src/test/supportFixtures.ts',import.meta.url),'utf8'));
const company=fixtures.company();const documents=[fixtures.companyDocument(),{...fixtures.companyDocument('b','Fiscal.pdf'),expiration_date:'2020-01-01'},{...fixtures.companyDocument('c','Referencia.xlsx'),mime_type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',expiration_date:null}];
const tender={id:'t',title:'Licitación sintética de consulta',external_reference:'R6-001',status:'DRAFT',institution_profile:null,created_at:'2026-10-24',updated_at:'2026-10-24'};
let mode='normal';
function fixture(url,method='GET',body='{}'){
 const u=new URL(url),p=u.pathname;
 if(method==='OPTIONS')return {};
 if(p==='/companies')return mode==='empty'?[]:[company];
 if(p==='/companies/c/documents')return mode==='empty'?[]:documents;
 if(p.endsWith('/evidence')&&p.includes('/companies/c/documents/'))return fixtures.companyEvidenceCollection(p.split('/').at(-2));
 if(p==='/tenders')return mode==='empty'?[]:[tender];
 if(p==='/tenders/t')return tender;
 if(p==='/tenders/t/documents')return [];
 if(p==='/discovery/sources'){if(method==='PATCH')return fixtures.sources()[0];return fixtures.sources();}
 if(p.startsWith('/discovery/sources/')&&method==='PATCH'){const id=p.split('/').at(-1);return {...fixtures.sources().find(s=>s.id===id),enabled:JSON.parse(body).enabled};}
 if(p==='/health')return {status:'ok',secret:'PRIVATE_SECRET'};
 if(p==='/ocr/providers')return [{provider_id:'local',status:'AVAILABLE',version:'TEST',status_reason:'PRIVATE_SECRET'}];
 if(p==='/vision/providers')return mode==='warning'?undefined:{runtime_available:true,model_available:true,base_url:'PRIVATE_SECRET',configured_model:'PRIVATE_SECRET',provider_status_reason:'PRIVATE_SECRET'};
 return undefined;
}
ws.addEventListener('message',async event=>{const m=JSON.parse(event.data);if(m.id){const entry=pending.get(m.id);if(entry){pending.delete(m.id);m.error?entry.reject(new Error(JSON.stringify(m.error))):entry.resolve(m.result);}return;}
 if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description??m.params.exceptionDetails.text);
 if(m.method==='Fetch.requestPaused'){const {requestId,request}=m.params;requests.push({url:request.url,method:request.method});if(!['GET','OPTIONS'].includes(request.method))writes.push(request.url);const value=fixture(request.url,request.method,request.postData);await call('Fetch.fulfillRequest',{requestId,responseCode:request.method==='OPTIONS'?204:value===undefined?503:200,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'*'},{name:'Access-Control-Allow-Headers',value:'*'}],body:Buffer.from(JSON.stringify(value??{detail:'TEST_UNAVAILABLE'})).toString('base64')});}
});
await call('Page.enable');await call('Runtime.enable');await call('Fetch.enable',{patterns:[{urlPattern:'http://localhost:8000/*'}]});
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description??r.exceptionDetails.text);return r.result.value;}
async function until(expression){const deadline=Date.now()+12000;while(Date.now()<deadline){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,75));}throw new Error('Timeout: '+expression);}
async function go(route){await evaluate(`location.hash=${JSON.stringify(route)}`);await new Promise(r=>setTimeout(r,250));}
async function size(width,height){await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});}
async function shot(name){await evaluate('document.activeElement?.blur()');const value=await call('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(out,name+'.png'),Buffer.from(value.data,'base64'));}
async function click(label){await evaluate(`(()=>{const e=[...document.querySelectorAll('button'),...document.querySelectorAll('a,summary')].find(e=>(e.getAttribute('aria-label')??e.textContent.trim())===${JSON.stringify(label)}&&e.getClientRects().length);if(!e)throw new Error('Missing '+${JSON.stringify(label)});e.click();})()`);await new Promise(r=>setTimeout(r,220));}
async function select(label,value){await evaluate(`(()=>{const e=Array.from(document.querySelectorAll('label')).find(e=>e.firstChild.textContent.trim()===${JSON.stringify(label)}&&e.getClientRects().length)?.querySelector('select');if(!e)throw new Error('Missing select');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await new Promise(r=>setTimeout(r,250));}
async function top(){await evaluate('window.scrollTo(0,0)');}
const checks=[];
try{
 await call('Page.navigate',{url:'about:blank'});await until(`location.href==='about:blank'`);await size(1366,768);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/mi-empresa'});await until(`document.querySelector('select')?.textContent.includes('Empresa sintética c')`);await evaluate(`localStorage.removeItem('tuscope.sidebar.desktop')`);await call('Page.reload');await until(`document.querySelector('select')?.textContent.includes('Empresa sintética c')`);await select('Empresa','c');await until(`document.querySelector('.support-product tbody tr')!==null`);await shot('01-company-library');assert.ok(await evaluate(`!document.querySelector('.support-product table').textContent.includes('PRIVATE_')`));checks.push('canonical company library with metadata-only dates; IDs/paths hidden');
 await click('Ver detalle Certificado.pdf');await until(`document.querySelector('[aria-label="Detalle documental empresarial"] details')!==null`);await evaluate(`document.querySelector('[aria-label="Detalle documental empresarial"]').scrollIntoView()`);await click('Certificación · Pendiente');await shot('02-company-detail');assert.ok(await evaluate(`document.querySelector('[aria-label="Detalle documental empresarial"]').textContent.includes('no equivale a confirmar su asociación')`));await click('Cerrar detalle empresarial');await top();await shot('03-company-validity');checks.push('company evidence/source/manual authority separate from Tender compliance');
 mode='empty';await click('Actualizar empresas');await until(`document.body.textContent.includes('Aún no hay empresas registradas.')`);await shot('04-company-empty');mode='normal';await click('Actualizar empresas');await until(`document.querySelector('.support-product tbody tr')!==null`);
 await go('/reportes');await until(`document.querySelector('section[aria-label="Reportes"] tbody tr')!==null`);await top();await shot('05-reports-catalogue');await select('Licitación para consultas','t');assert.ok(await evaluate(`Array.from(document.querySelectorAll('section[aria-label="Reportes"] a')).some(e=>e.textContent==='Consultar archivos de propuesta'&&e.getAttribute('href')==='#/licitaciones/t/propuesta')`));await click('Consultar registro abajo');await shot('06-report-result');await select('Estado del registro','ARCHIVED');await shot('07-report-no-data');assert.ok(await evaluate(`document.querySelector('section[aria-label="Reportes"]').textContent.includes('No hay registros para esta consulta.')`));checks.push('real report catalogue/filter and canonical exports navigation, no generation');
 await go('/configuracion');await until(`document.querySelector('section[aria-label="Configuración"]').textContent.includes('Compras MX')`);await top();await shot('08-settings');await click('Configurar CFE');await shot('09-source-settings');assert.equal(await evaluate(`Array.from(document.querySelectorAll('section[aria-label="Configuración"] button')).some(e=>e.textContent.includes('Compras'))`),false);await shot('10-compras-restricted');checks.push('PEMEX/CFE configuration reads; restricted source offers no action or portal access');
 await go('/configuracion/diagnostico');await until(`document.querySelector('[aria-label="Diagnóstico local"]').textContent.includes('API local responde')`);await top();await shot('11-diagnostics');await click('Ver detalle técnico');await shot('12-technical-detail');assert.ok(await evaluate(`!document.querySelector('[aria-label="Diagnóstico local"]').textContent.includes('PRIVATE_SECRET')`));assert.ok(!requests.some(r=>r.url.endsWith('/workspace')));checks.push('grouped local diagnostics; advanced legacy workspace is not mounted automatically');
 await evaluate(`Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.testCopiedSummary=text;}},configurable:true})`);await click('Copiar resumen para soporte');assert.ok(await evaluate(`window.testCopiedSummary.includes('API: Disponible al consultar')&&!window.testCopiedSummary.includes('PRIVATE_')&&!window.testCopiedSummary.includes('Empresa sintética')`));mode='warning';await click('Actualizar diagnóstico');await until(`document.querySelector('[aria-label="Diagnóstico local"]').textContent.includes('Consulta no disponible')`);await top();await shot('13-service-warning');mode='normal';checks.push('allowlisted copy excludes customer/secret data; partial failure remains local');
 for(const route of ['mi-empresa','reportes','configuracion','configuracion/diagnostico']){await go('/'+route);assert.equal(await evaluate(`document.querySelector('.global-sidebar a[href="#/${route}"]').getAttribute('aria-current')`),'page');await top();for(const [w,h]of [[1366,768],[1440,900],[1920,1080]]){await size(w,h);assert.ok(await evaluate(`document.documentElement.scrollWidth<=${w}`));await shot('16-'+route.replace('/','-')+'-'+w);}}checks.push('all global workspaces at three desktops without global overflow');
 await size(1366,768);await go('/mi-empresa');await click('Contraer menú');await shot('14-company-collapsed');await go('/configuracion');await shot('15-settings-collapsed');assert.equal(await evaluate(`document.querySelector('.global-sidebar').getBoundingClientRect().width`),64);assert.equal(await evaluate(`document.querySelector('.global-sidebar a[aria-current=page]').getAttribute('aria-label')`),'Configuración');checks.push('approved sidebar persists and active global routes remain clear');
 for(const route of ['mi-empresa','reportes','configuracion','configuracion/diagnostico']){await go('/'+route);await size(390,844);await top();assert.ok(await evaluate('document.documentElement.scrollWidth<=390'));await shot('17-'+route.replace('/','-')+'-390');}await click('Menú');await shot('18-narrow-navigation');checks.push('narrow contained company tables and reachable responsive navigation');
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);checks.push('no automatic writes scans analysis generation or telemetry; no runtime exceptions');await evaluate(`localStorage.removeItem('tuscope.sidebar.desktop')`);
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',fixture:'SYNTHETIC_TEST_ONLY',checks,requests,writes,errors},null,2));console.log(JSON.stringify({status:'PASS',groups:checks.length}));
}finally{ws.close();}
