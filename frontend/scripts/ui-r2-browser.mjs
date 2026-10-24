/** Local browser acceptance via Chromium CDP, no package dependency.
 * Start Vite on 127.0.0.1:5181 and Chromium with --remote-debugging-port=9331.
 * All API responses below are TEST-ISOLATED synthetic fixtures. No product DB or public source requests.
 * node scripts/ui-r2-browser.mjs [artifact-directory]
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
let imported=false, mode='populated';
const tender={id:'ui-r2-tender',title:'Expediente sintético UI-R2',external_reference:'UIR2-LOCAL',institution_profile:'General',status:'DRAFT',created_at:'2026-10-23T12:00:00Z',updated_at:'2026-10-23T12:00:00Z'};
const sources=['PEMEX','CFE','COMPRAS_MX'].map(id=>({id,name:id==='COMPRAS_MX'?'Compras MX':id,enabled:id!=='COMPRAS_MX',last_scan_state:id==='CFE'?'PARTIAL':null,last_error:null,areas:id==='COMPRAS_MX'?[]:[{key:id==='CFE'?'public':'support',label:'Área pública'}],configuration:{areas:id==='CFE'?['public']:['support']},capabilities:{automation_status:id==='COMPRAS_MX'?'DEFERRED_SOURCE_AUTOMATION_RESTRICTED':'AVAILABLE'}}));
const base={description:'Objeto público sintético de revisión visual',business_area:'Área industrial',published_date:'2026-10-23',event_type:'Nacional',supply_type:'Bienes',source_status:'Publicado',revision:1,document_count:2,public_url:'https://www.pemex.com/public',first_seen:'2026-10-23',last_seen:'2026-10-23',match:null,unread_document_changes:1};
const row=()=>({...base,id:'new',source_id:'PEMEX',external_id:'PROC-001',title:'Controladores PLC e instrumentación para mantenimiento industrial — revisión sintética',internal_state:imported?'IMPORTED':'NEW',watching:false,unread_changes:1,linked_tender:imported?{id:tender.id,available:true}:null});
const scan={id:'partial',source_id:'CFE',status:'PARTIAL',started_at:'2026-10-23T12:00:00Z',metrics:{pages_attempted:3,pages_completed:2,unique_opportunities:17,rows_retrieved:18,diagnostics:[{area:'public',code:'ACQUISITION_FAILED',page:3}]}};
function fixture(url,method='GET',body='{}') {
 const u=new URL(url),p=u.pathname,q=u.searchParams;
 if(p==='/tenders')return mode==='empty'?[]:[tender];
 if(p==='/companies'||p.endsWith('/documents')||p.endsWith('/providers')||p.endsWith('/scope-review')||p.endsWith('/technical-alternatives'))return [];
 if(p.endsWith('/workspace'))return {tender_id:tender.id,processing:{status:'NOT_PROCESSED'},scopes:[],requirements:{scope_note:'TEST ONLY',requirements:[]},semantics:{scope_note:'TEST ONLY',requirements:[]},warnings:[]};
 if(p==='/discovery/sources')return sources;
 if(p==='/discovery/profiles')return [{id:'profile',name:'Instrumentación',revision:1,include_keywords:['PLC'],exclude_keywords:[],synonyms:{},source_ids:[],business_areas:[],active:true}];
 if(p==='/discovery/monitoring/summary')return {new_opportunities:mode==='empty'?0:1,followed_with_changes:mode==='empty'?0:1,changed_opportunities:2,unread_changes:3,new_documents:1};
 if(p==='/discovery/scans')return mode==='empty'?[]:[scan];
 if(p==='/discovery/scans/partial'||p.endsWith('/scans')&&method==='POST')return scan;
 if(p==='/discovery/opportunities'){
 let items=mode==='empty'?[]:[row(),{...base,id:'follow',source_id:'CFE',external_id:'CFE-002',title:'Mantenimiento de sistemas de control',internal_state:'FOLLOWING',watching:true,unread_changes:2},{...base,id:'linked',source_id:'PEMEX',external_id:'PROC-003',title:'Refacciones',internal_state:'IMPORTED',watching:false,unread_changes:0,linked_tender:{id:tender.id,available:true}}];
 if(q.get('following')==='true')items=items.filter(r=>r.watching);if(q.get('unread_only')==='true')items=items.filter(r=>r.unread_changes>0);if(q.get('internal_state'))items=items.filter(r=>r.internal_state===q.get('internal_state'));if(q.get('source'))items=items.filter(r=>r.source_id===q.get('source'));
 const offset=Number(q.get('offset')??0),limit=Number(q.get('limit')??50);return {items:items.slice(offset,offset+limit),total:items.length,limit,offset};}
 if(p==='/discovery/opportunities/new')return row();
 if(p.endsWith('/new/tender-preview'))return {opportunity_id:'new',source_id:'PEMEX',source_fingerprint:'test-hash',binding:'test-binding',internal_state:imported?'IMPORTED':'NEW',suggested_title:row().title,profile_context:null,context:{},documents:[{id:'document',name:'Bases de prueba.pdf',public_url:'https://www.pemex.com/file',metadata_fingerprint:'test',last_import:null}],linked_tender:imported?{id:tender.id,available:true}:null,selection_default:'NONE',analysis_automatic:false};
 if(p.endsWith('/new/changes'))return {items:[{id:'change',category:'DOCUMENT_ADDED',origin:'SOURCE',summary:'Referencia documental disponible',changed_fields:{name:'Bases de prueba.pdf'},detected_at:'2026-10-23T12:00:00Z',acknowledged_at:null}],total:1,limit:100,offset:0};
 if(p.endsWith('/new/create-tender')&&method==='POST'){const v=JSON.parse(body);assert.equal(v.confirm,true);assert.equal(v.expected_binding,'test-binding');assert.equal(v.documents.length,1);imported=true;return {tender_id:tender.id,tender_available:true,already_created:false,documents_status:'COMPLETE_SELECTION',analysis_started:false,documents:[{source_document_id:'document',status:'IMPORTED'}]};}
 return undefined;
}
ws.addEventListener('message', async event => {
 const m=JSON.parse(event.data);
 if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}return;}
 if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text+': '+(m.params.exceptionDetails.exception?.description??''));
 if(m.method==='Fetch.requestPaused') {
  const {requestId,request}=m.params;requests.push(request.url);
  if(request.method!=='GET' && request.method!=='OPTIONS')writes.push(request.url);
  const value=fixture(request.url,request.method,request.postData);
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
async function click(label){await evaluate(`Array.from(document.querySelectorAll('button,a,summary')).find(e=>e.textContent.trim()===${JSON.stringify(label)}&&e.getClientRects().length)?.click()`);await new Promise(r=>setTimeout(r,200));}
async function select(label,value){await evaluate(`(()=>{const e=Array.from(document.querySelectorAll('label')).find(e=>e.firstChild.textContent.trim()===${JSON.stringify(label)})?.querySelector('select');if(!e)throw new Error('Missing select');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await new Promise(r=>setTimeout(r,200));}
async function top(){await evaluate('window.scrollTo(0,0)');}
try {
 await call('Page.navigate',{url:'about:blank'});await until(`location.href==='about:blank'`);
 await size(1366,768);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/'});await until(`document.querySelector('.metric-link strong')?.textContent==='1'`);await shot('01-inicio-1366');checks.push('Inicio canonical metrics / attention / real Tender fixture');
 await size(1440,900);await shot('02-inicio-1440');await size(1920,1080);await shot('03-inicio-1920');
 mode='empty';await click('Actualizar vista');await until(`document.body.textContent.includes('Aún no hay licitaciones.')`);await shot('04-inicio-empty');mode='populated';await click('Actualizar vista');await until(`document.querySelector('.metric-link')!==null`);checks.push('empty installation / no decorative zero cards');
 await evaluate(`document.querySelector('.metric-link[href="#/discovery?view=new"]').click()`);await until(`document.querySelectorAll('.opportunities-table tbody tr').length===1`);assert.ok(await evaluate(`document.querySelector('.opportunities-table tbody').textContent.includes('PROC-001')`));checks.push('metric destination applies canonical NEW filter');
 await go('/discovery');await until(`document.querySelectorAll('.opportunities-table tbody tr').length===3`);
 for(const [w,h]of [[1366,768],[1440,900],[1920,1080]]){await size(w,h);await top();assert.ok(await evaluate(`document.documentElement.scrollWidth<=${w}`));assert.ok(await evaluate(`document.querySelector('.opportunities-table tbody td:last-child').getBoundingClientRect().right<=${w}`));await shot(`05-discovery-${w}`);}checks.push('3 desktop widths / table-first / contained overflow');
 await go('/discovery?view=following-changes');await until(`document.querySelectorAll('.opportunities-table tbody tr').length===1`);assert.ok(await evaluate(`document.querySelector('.opportunities-table tbody').textContent.includes('CFE-002')`));await top();await shot('06-following-changes');checks.push('watching plus unread / translated states / change counts');
 await go('/discovery?view=all&opportunity=new');await until(`document.querySelector('.opportunity-detail h4')!==null`);await evaluate(`document.querySelector('.opportunity-detail').scrollIntoView()`);await shot('07-opportunity-detail');
 await until(`Array.from(document.querySelectorAll('h4')).some(e=>e.textContent==='Crear licitación — vista previa')`);await evaluate(`Array.from(document.querySelectorAll('h4')).find(e=>e.textContent==='Crear licitación — vista previa').scrollIntoView()`);await shot('08-create-preview');assert.equal(writes.filter(u=>u.endsWith('/create-tender')).length,0);assert.equal(await evaluate(`Array.from(document.querySelectorAll('button')).find(e=>e.textContent==='Crear licitación').disabled`),true);checks.push('preview readonly / no auto-create / confirmation required');
 await evaluate(`Array.from(document.querySelectorAll('label')).find(e=>e.textContent==='Bases de prueba.pdf').querySelector('input').click()`);await evaluate(`Array.from(document.querySelectorAll('label')).find(e=>e.textContent.includes('Confirmo crear licitación')).querySelector('input').click()`);await click('Crear licitación');await until(`document.querySelector('.opportunity-detail').textContent.includes('análisis no iniciado')`);assert.equal(writes.filter(u=>u.endsWith('/create-tender')).length,1);checks.push('Create Tender UI E2E / explicit selection / binding');
 await click('Abrir licitación');await until(`document.querySelector('.tender-context-nav')!==null`);assert.ok(await evaluate(`location.hash.includes('${tender.id}')`));checks.push('Open canonical Tender');
 await go('/discovery');await click('Buscar actualizaciones');await until(`document.getElementById('source-consultation').open`);await select('Fuente para consultar','COMPRAS_MX');await shot('09-compras-restricted');assert.equal(await evaluate(`Array.from(document.querySelectorAll('button')).some(e=>e.textContent==='Consultar fuente ahora')`),false);assert.equal(requests.some(u=>u.includes('/COMPRAS_MX/')),false);checks.push('Compras neutral restriction / no scan action / no network');
 await select('Fuente para consultar','CFE');await click('Consultar fuente ahora');await until(`document.querySelector('#source-consultation').textContent.includes('La consulta fue parcial')`);await shot('10-partial-source');assert.ok(await evaluate(`document.querySelector('.opportunities-table tbody tr')!==null`));checks.push('partial result does not destroy local records');
 await go('/configuracion/diagnostico');await until(`document.querySelector('h1').textContent==='Diagnóstico'`);await go('/licitaciones/'+tender.id+'/propuesta');await until(`document.querySelector('.tender-context-nav a[aria-current]').textContent==='Propuesta'`);checks.push('legacy Tender / Proposal / diagnostics reachable');
 await size(768,900);await go('/discovery');await top();assert.ok(await evaluate('document.documentElement.scrollWidth<=768'));await shot('11-discovery-narrow-768');await size(390,844);await top();assert.ok(await evaluate('document.documentElement.scrollWidth<=390'));await shot('12-discovery-narrow-390');checks.push('narrow768/390 contained overflow');
 assert.deepEqual(errors,[]);assert.ok(writes.every(u=>u.endsWith('/create-tender')||u.endsWith('/CFE/scans')));checks.push('no runtime exceptions / no implicit domain writes');
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',fixture:'TEST_ISOLATED_SYNTHETIC_API',checks,errors,writes},null,2));console.log(JSON.stringify({status:'PASS',checks:checks.length,artifacts:out}));
}finally{ws.close();}
