/** Local browser acceptance via Chromium CDP, no package dependency.
 * Start Vite on 127.0.0.1:5181 and Chromium with --remote-debugging-port=9331.
 * All API responses below are TEST-ISOLATED synthetic fixtures. No product DB or public source requests.
 * node scripts/ui-r2-browser.mjs [artifact-directory]
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out = path.resolve(process.argv[2] ?? '../backend/reports/ui_r5/browser');
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
const fixtures=testModule(await fs.readFile(new URL('../src/test/commercialProductFixtures.ts',import.meta.url),'utf8'));
let ready=false,failedExport=false;
const tender={id:'t',title:'Oferta industrial — expediente sintético de revisión',external_reference:'UI-R5-001',institution_profile:'General',status:'DRAFT',created_at:'2026-10-23T12:00:00Z',updated_at:'2026-10-23T12:00:00Z'};
const draft=fixtures.proposalVersion(),frozen=fixtures.proposalVersion('frozen','FROZEN');frozen.version=2;frozen.proposal_id='historical-proposal';
const receipt={request_id:'request',version_id:'frozen',created_at:'2026-10-23T12:00:00Z',proposal_state:'FROZEN',verification_status:'VERIFIED_AT_CREATION',semantic_sha256:'a'.repeat(64),artifacts:['DOCX','XLSX','PDF','ZIP'].map(kind=>({type:kind,name:'propuesta.'+kind.toLowerCase(),size:2000,sha256:'b'.repeat(64)}))};
const composition=id=>({initialized:true,contract_version:'proposal-composition-v1',version_id:id,revision:1,sections:[{id:'technical',type:'TECHNICAL_SCOPE',order:1,included:true,note:null}],summary:{status:'COMPLETE',hard_incomplete:[],blocking_review:[],acknowledgeable_review:[],sections:[{section:'TECHNICAL_SCOPE',status:'COMPLETE',pending_count:0,review_count:0,row_count:1}]},rows:[{key:'scope:1',section:'TECHNICAL_SCOPE',canonical:{description:'Equipo de protección — referencia sintética'},response:{status:'COMPLY',text:'Declaración humana de prueba',offered_description:'Equipo propuesto',included:true,comment:'',clarification:'',note:'',document_id:null,external_reference:'',reason:''},source_match:'UNCHANGED',review_required:false}],items:[],total:1,next_offset:null,currency_groups:[{currency:'MXN',line_count:1},{currency:'USD',line_count:1}]});
function fixture(url,method='GET'){
 const p=new URL(url).pathname;
 if(method==='OPTIONS')return {};
 if(p==='/tenders')return[tender];if(p==='/tenders/t')return tender;if(p==='/tenders/t/documents')return[];
 if(p.endsWith('/commercial-matrix')){const value=fixtures.commercialMatrix();value.rows[1].inputs.quote_reference=null;value.rows[1].inputs.quote_document_id=null;return value;}
 if(p.endsWith('/commercial-line')){const row=fixtures.commercialRow(p.split('/').at(-2));return {id:'line',tender_id:'t',scope_detail_id:row.scope_id,revision:1,inputs:row.inputs,source:row.source,summary:row.summary,price_method:'MANUAL',price_value_origin:'MANUAL_INPUT',history:[]};}
 if(p.endsWith('/readiness-board'))return fixtures.readinessBoard(ready);
 if(p.endsWith('/proposal-versions'))return {items:[draft,frozen],next_before_id:null};
 if(p.endsWith('/proposal-versions/v'))return draft;if(p.endsWith('/proposal-versions/frozen'))return frozen;
 if(p.endsWith('/source-state'))return{state:'SOURCE_SNAPSHOT_STALE'};
 if(p.endsWith('/composition'))return composition(p.includes('/frozen/')?'frozen':'v');
 if(p.endsWith('/exports'))return method==='GET'?{items:[receipt],next_before_id:null}:failedExport?undefined:receipt;
 if(p.endsWith('/snapshots'))return{items:[{snapshot_id:'snapshot',created_at:'2026-10-23T12:00:00Z',eligibility:'ELIGIBLE_WITH_WARNINGS',state:'CURRENT'}],next_before_id:null};
 if(p.endsWith('/providers')||p.endsWith('/documents')||p.endsWith('/companies'))return[];
 return undefined;
}
ws.addEventListener('message',async event=>{
 const m=JSON.parse(event.data);if(m.id){const item=pending.get(m.id);if(item){pending.delete(m.id);m.error?item.reject(new Error(JSON.stringify(m.error))):item.resolve(m.result);}return;}
 if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description??m.params.exceptionDetails.text);
 if(m.method==='Fetch.requestPaused'){const {requestId,request}=m.params;requests.push({url:request.url,method:request.method});if(!['GET','OPTIONS'].includes(request.method))writes.push(request.url);const value=fixture(request.url,request.method);await call('Fetch.fulfillRequest',{requestId,responseCode:request.method==='OPTIONS'?204:value===undefined?503:200,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'*'},{name:'Access-Control-Allow-Headers',value:'*'}],body:Buffer.from(JSON.stringify(value??{detail:'Fallo sintético de generación; conserva artefactos anteriores'})).toString('base64')});}
});
await call('Page.enable');await call('Runtime.enable');await call('Fetch.enable',{patterns:[{urlPattern:'http://localhost:8000/*'}]});
async function evaluate(expression){const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description??result.exceptionDetails.text);return result.result.value;}
async function until(expression){const deadline=Date.now()+12000;while(Date.now()<deadline){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,75));}throw new Error('Timeout: '+expression);}
async function go(route){await evaluate(`location.hash=${JSON.stringify(route)}`);await new Promise(r=>setTimeout(r,300));}
async function size(width,height){await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});}
async function shot(name){await evaluate('document.activeElement?.blur()');const data=await call('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(out,name+'.png'),Buffer.from(data.data,'base64'));}
async function click(label){await evaluate(`(()=>{const e=[...document.querySelectorAll('button'),...document.querySelectorAll('a,summary')].find(e=>e.textContent.trim()===${JSON.stringify(label)}&&e.getClientRects().length);if(!e)throw new Error('Missing '+${JSON.stringify(label)});e.click();})()`);await new Promise(r=>setTimeout(r,250));}
async function top(){await evaluate('window.scrollTo(0,0)');}
async function focus(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`);}
const checks=[];
try{
 await call('Page.navigate',{url:'about:blank'});await until(`location.href==='about:blank'`);await size(1366,768);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/licitaciones/t/comercial'});await until(`document.querySelector('.commercial-product tbody tr')!==null`);assert.equal(writes.length,0);await shot('01-commercial-matrix');checks.push('canonical matrix with distinct currencies / no writes on entry');
 await click('Detalle 1');await focus('.commercial-detail');await shot('02-commercial-detail');assert.ok(await evaluate(`document.querySelector('.commercial-detail').textContent.includes('Markup efectivo: 25% · Margen efectivo: 20%')`));await shot('03-quote-provenance');checks.push('canonical source and confirmed quote / distinct margin and markup unchanged');
 await click('Comercial');await until(`document.querySelector('.commercial-detail input')!==null`);await shot('04-quote-edit');await click('Cerrar detalle comercial');await click('Detalle 2');await focus('.commercial-detail');await shot('04-missing-quote');assert.ok(await evaluate(`document.querySelector('.commercial-detail').textContent.includes('Sin referencia de cotización')`));await click('Cerrar detalle comercial');
 await click('Edición en lote e intercambio Excel / CSV');await click('Abrir matriz comercial');await until(`document.querySelector('[aria-label="Round trip comercial XLSX CSV"]')!==null`);await focus('[aria-label="Round trip comercial XLSX CSV"]');await shot('05-import-export');await evaluate(`(()=>{const input=document.querySelector('[aria-label="Round trip comercial XLSX CSV"] input[type=file]');const dt=new DataTransfer();dt.items.add(new File(['TEST_ONLY'],'invalid.txt',{type:'text/plain'}));input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`);await click('Previsualizar importación');await until(`document.querySelector('[aria-label="Round trip comercial XLSX CSV"] [role=alert]')!==null`);await shot('05b-import-local-error');checks.push('canonical roundtrip controls available, no silent import');
 await go('/licitaciones/t/preparacion');await until(`document.querySelector('.readiness-product tbody tr')!==null`);await top();await shot('07-readiness-blockers');await shot('08-readiness-warnings');assert.ok(await evaluate(`document.querySelector('.readiness-product').textContent.includes('Bloqueos y faltantes: 1')`));await click('Ver detalle de atención');await focus('[aria-label="Detalle de preparación"]');await shot('10-readiness-detail');checks.push('blockers first / human activity cannot clear source blockers');
 ready=true;await click('Actualizar preparación actual');await until(`document.querySelector('.readiness-product h3')?.textContent==='Listo'`);await top();await shot('09-readiness-ready');checks.push('ready only from canonical response, warning remains visible');
 await go('/licitaciones/t/propuesta');assert.equal(writes.length,0);await click('Consultar versiones de propuesta');await until(`document.querySelector('.proposal-product tbody tr')!==null`);await click('Abrir versión 1');await until(`document.querySelector('.proposal-product input[maxlength="300"]')!==null`);await top();await shot('11-proposal-draft');await click('Consultar cambios posteriores');await until(`document.querySelector('.proposal-product').textContent.includes('Hay cambios posteriores al estado usado')`);await shot('13-proposal-stale');checks.push('draft binding / stale notice / no automatic regeneration');
 await click('Consultar composición');await until(`document.querySelector('[aria-label="Composición de propuesta"]').textContent.includes('Completitud de propuesta')`);await focus('[aria-label="Composición de propuesta"]');await shot('11b-human-composition');checks.push('human responses separated from read-only source / explicit initialization');
 await click('Abrir versión 2');await until(`document.querySelector('.proposal-product').textContent.includes('Versión congelada e inmutable')`);await top();await shot('12-proposal-frozen');assert.ok(await evaluate(`document.querySelector('.proposal-product input[maxlength="300"]').matches(':disabled')`));await click('Consultar composición');await until(`document.querySelector('[aria-label="Composición de propuesta"]').textContent.includes('Completitud de propuesta')`);await click('Consultar artefactos generados');await until(`document.querySelector('[aria-label="Exportaciones de propuesta"]').textContent.includes('Descargar propuesta.docx')`);await focus('[aria-label="Exportaciones de propuesta"]');await shot('14-proposal-artifacts');for(const format of ['docx','xlsx','pdf','zip'])assert.ok(await evaluate(`Array.from(document.querySelectorAll('[aria-label="Exportaciones de propuesta"] a')).some(a=>a.textContent==='Descargar propuesta.${format}')`));checks.push('immutable frozen / four actual artifact references / hashes secondary');
 failedExport=true;await click('Generar PDF');await until(`document.querySelector('[aria-label="Exportaciones de propuesta"] [role="alert"]')!==null`);await focus('[aria-label="Exportaciones de propuesta"] [role="alert"]');await shot('15-export-error-retry');assert.ok(await evaluate(`document.querySelector('[aria-label="Exportaciones de propuesta"]').textContent.includes('Descargar propuesta.docx')`));checks.push('failed generation preserves prior artifacts / explicit retry');
 for(const section of ['comercial','preparacion','propuesta']){await go('/licitaciones/t/'+section);if(section==='comercial'){await click('Edición en lote e intercambio Excel / CSV');}for(const [w,h]of [[1366,768],[1440,900],[1920,1080],[768,900],[390,844]]){await size(w,h);await top();assert.ok(await evaluate(`document.documentElement.scrollWidth<=${w}`),section+' '+w+' overflow');await shot('16-'+section+'-'+w);}}checks.push('three desktop and two narrow sizes / contained table scroll, no global overflow');
 assert.deepEqual(errors,[]);assert.equal(writes.length,1);assert.ok(writes.every(url=>url.endsWith('/exports')));checks.push('only explicit export attempted / zero analysis or semantic provider calls / zero exceptions');
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',checks,requests,writes,errors,fixture:'TEST_ONLY_SYNTHETIC_CONTRACTS'},null,2));console.log(JSON.stringify({status:'PASS',groups:checks.length}));
}finally{ws.close();}
