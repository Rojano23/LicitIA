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
let imported=false, mode='empty';
const tender={id:'ui-r2-tender',title:'Expediente sintético UI-R2',external_reference:'UIR2-LOCAL',institution_profile:'General',status:'DRAFT',created_at:'2026-10-23T12:00:00Z',updated_at:'2026-10-23T12:00:00Z'};
const sources=['PEMEX','CFE','COMPRAS_MX'].map(id=>({id,name:id==='COMPRAS_MX'?'Compras MX':id,enabled:id!=='COMPRAS_MX',last_scan_state:id==='CFE'?'PARTIAL':null,last_error:null,areas:id==='COMPRAS_MX'?[]:[{key:id==='CFE'?'public':'support',label:'Área pública'}],configuration:{areas:id==='CFE'?['public']:['support']},capabilities:{automation_status:id==='COMPRAS_MX'?'DEFERRED_SOURCE_AUTOMATION_RESTRICTED':'AVAILABLE'}}));
const base={description:'Objeto público sintético de revisión visual',business_area:'Área industrial',published_date:'2026-10-23',event_type:'Nacional',supply_type:'Bienes',source_status:'Publicado',revision:1,document_count:2,public_url:'https://www.pemex.com/public',first_seen:'2026-10-23',last_seen:'2026-10-23',match:null,unread_document_changes:1};
const row=()=>({...base,id:'new',source_id:'PEMEX',external_id:'PROC-001',title:'Controladores PLC e instrumentación para mantenimiento industrial — revisión sintética',internal_state:imported?'IMPORTED':'NEW',watching:false,unread_changes:1,linked_tender:imported?{id:tender.id,available:true}:null});
const scan={id:'completed',source_id:'PEMEX',status:'SUCCESS',started_at:'2026-10-24T12:00:00Z',finished_at:'2026-10-24T12:03:00Z',query:{areas:['support'],published_from:'2026-09-25',published_to:'2026-10-24',event_type:null,supply_type:null,page_size:100},metrics:{pages_attempted:4,pages_completed:4,unique_opportunities:111,rows_retrieved:111}};
function fixture(url,method='GET',body='{}') {
 const u=new URL(url),p=u.pathname,q=u.searchParams;
 if(p==='/tenders')return mode==='empty'?[]:[tender];
 if(p==='/companies'||p.endsWith('/documents')||p.endsWith('/providers')||p.endsWith('/scope-review')||p.endsWith('/technical-alternatives'))return [];
 if(p.endsWith('/workspace'))return {tender_id:tender.id,processing:{status:'NOT_PROCESSED'},scopes:[],requirements:{scope_note:'TEST ONLY',requirements:[]},semantics:{scope_note:'TEST ONLY',requirements:[]},warnings:[]};
 if(p==='/discovery/sources')return sources;
 if(p==='/discovery/profiles')return [{id:'profile',name:'Instrumentación',revision:1,include_keywords:['PLC'],exclude_keywords:[],synonyms:{},source_ids:[],business_areas:[],active:true}];
 if(p==='/discovery/monitoring/summary')return {new_opportunities:mode==='empty'?0:1,followed_with_changes:mode==='empty'?0:1,changed_opportunities:2,unread_changes:3,new_documents:1};
 if(p==='/discovery/scans')return mode==='empty'?[]:[scan];
 if(p==='/discovery/scans/completed')return scan;if(p.endsWith('/scans')&&method==='POST'){mode='populated';return scan;}
 if(p==='/discovery/opportunities'){
 let items=mode==='empty'?[]:Array.from({length:111},(_,i)=>({...row(),id:'opportunity-'+i,external_id:'PROC-'+String(i+1).padStart(3,'0'),title:i===0?row().title:'Procedimiento público sintético '+(i+1),match:q.get('profile_id')?{matched:i===0,include_hits:i===0?[{term:'PLC',matched_text:'PLC',field:'title',kind:'EXACT'}]:[],exclude_hits:[],restrictions:[]}:null}));
 if(q.get('matched_only')==='true')items=items.filter(r=>r.match?.matched);if(q.get('source'))items=items.filter(r=>r.source_id===q.get('source'));
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
await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Network.setBlockedURLs',{urlPatterns:[{urlPattern:'https://*',block:true},{urlPattern:'http://*',block:true},{urlPattern:'http://127.0.0.1:*',block:false},{urlPattern:'http://localhost:*',block:false}]});
await call('Fetch.enable',{patterns:[{urlPattern:'http://localhost:8000/*'},{urlPattern:'http://127.0.0.1:8000/*'}]});
async function evaluate(expression){const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.text);return result.result.value;}
async function until(expression){const deadline=Date.now()+12000;while(Date.now()<deadline){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,75));}throw new Error('Timeout: '+expression);}
async function go(route){await evaluate(`location.hash=${JSON.stringify(route)}`);await until(`document.querySelector('h1')!==null`);await new Promise(resolve=>setTimeout(resolve,250));}
async function size(width,height){await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});}
async function shot(name){if(name!=='02-query-expanded')await evaluate('document.activeElement?.blur()');const data=await call('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(out,name+'.png'),Buffer.from(data.data,'base64'));}
const checks=[];
async function click(label){await evaluate(`Array.from(document.querySelectorAll('button,a,summary')).find(e=>(e.getAttribute('aria-label')??e.textContent.trim())===${JSON.stringify(label)}&&e.getClientRects().length)?.click()`);await new Promise(r=>setTimeout(r,180));}
async function select(label,value){await evaluate(`(()=>{const e=Array.from(document.querySelectorAll('label')).find(e=>e.firstChild.textContent.trim()===${JSON.stringify(label)})?.querySelector('select');if(!e)throw new Error('Missing select '+${JSON.stringify(label)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await new Promise(r=>setTimeout(r,180));}
async function focus(id){await evaluate(`document.getElementById(${JSON.stringify(id)}).scrollIntoView({block:'start'})`);}
try{
 await call('Page.addScriptToEvaluateOnNewDocument',{source:`const NativeDate=Date;window.Date=class extends NativeDate{constructor(...args){super(...(args.length?args:['2026-10-24T12:00:00']));}static now(){return new NativeDate('2026-10-24T12:00:00').getTime();}};`});
 await size(1440,900);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/discovery'});await until(`document.querySelector('#stored-filters')&&Array.from(document.querySelectorAll('button')).some(e=>e.textContent==='Aplicar filtros'&&!e.disabled)`);await shot('01-initial');
 await click('Nueva consulta');await until(`document.activeElement.id==='source-consultation'`);assert.equal(writes.length,0);await shot('02-query-expanded');checks.push('Nueva consulta opens/focuses Step1 without scan');
 await select('Periodo de publicación','7');await shot('03-query-preset');await select('Periodo de publicación','custom');await shot('04-query-custom');await select('Periodo de publicación','30');
 await click('Consultar fuente');await until(`document.querySelector('#scan-result').textContent.includes('111 oportunidades únicas')`);await focus('scan-result');await shot('05-success-summary');assert.equal(writes.length,1);checks.push('explicit synthetic query / canonical summary111 and4');
 await click('Ver resultados');await until(`document.activeElement.id==='stored-filters'`);assert.equal(await evaluate(`document.querySelector('#stored-filters select').value`),'PEMEX');await shot('06-results-context');
 const context=new URL(requests.filter(u=>new URL(u).pathname==='/discovery/opportunities').at(-1));assert.equal(context.searchParams.get('source'),'PEMEX');assert.equal(context.searchParams.get('published_from'),'2026-09-25');assert.equal(context.searchParams.get('matched_only'),'false');checks.push('Ver resultados explicit source/publication context / no profile-only autoenable');
 await select('Perfil de búsqueda','profile');await click('Aplicar filtros');await focus('opportunity-results');await shot('07-profile-off');assert.equal(await evaluate(`document.querySelectorAll('.opportunities-table tbody tr').length`),50);
 await evaluate(`Array.from(document.querySelectorAll('label')).find(e=>e.textContent==='Sólo coincidencias del perfil').querySelector('input').click()`);await click('Aplicar filtros');await until(`document.querySelectorAll('.opportunities-table tbody tr').length===1`);await focus('opportunity-results');await shot('08-profile-on');checks.push('111stored versus1matching / server totals and pagination');
 await focus('stored-filters');await shot('09-advanced-collapsed');await click('Más filtros');await click('Ayuda: Área o entidad');await click('Ayuda: Tipo de evento');await click('Ayuda: Tipo de suministro');await evaluate(`document.querySelector('[aria-label="Ayuda: Área o entidad"]').focus()`);await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await until(`!document.querySelector('[aria-label="Ayuda: Área o entidad"]').parentElement.open`);await click('Ayuda: Área o entidad');await shot('10-advanced-help');assert.ok(await evaluate(`document.querySelector('#stored-filters').textContent.includes('Internacional bajo TLC')`));checks.push('advanced filters3 / accessible click help / verified examples');
 await click('Administrar perfiles');await until(`document.activeElement.id==='search-profiles'`);await shot('11-settings-profiles');await select('Editar perfil','profile');assert.equal(await evaluate(`document.querySelector('#search-profiles textarea').value`),'PLC');checks.push('direct Settings link / complete existing editor / focus');
 await go('/discovery');await click('Ver historial');await focus('scan-result');await click('Diagnóstico de la consulta');await shot('12-history-diagnostic');checks.push('secondary history / real fields diagnostic');
 for(const[w,h]of[[1366,768],[390,844]]){await size(w,h);await focus('stored-filters');assert.ok(await evaluate(`document.documentElement.scrollWidth<=${w}`));await shot('13-filters-'+w);}
 await size(1366,768);await click('Nueva consulta');await select('Fuente para consultar','COMPRAS_MX');await shot('14-compras-restricted');assert.equal(await evaluate(`Array.from(document.querySelectorAll('button')).some(e=>e.textContent==='Consultar fuente')`),false);checks.push('Compras restriction preserved / no bypass');
 assert.deepEqual(errors,[]);assert.ok(writes.every(u=>u.endsWith('/PEMEX/scans')));checks.push('no runtime exception / no Tender or analysis writes / API fully synthetic');
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',fixture:'TEST_ISOLATED_SYNTHETIC_API',checks,errors,writes,requests},null,2));console.log(JSON.stringify({status:'PASS',checks:checks.length,artifacts:out}));
}finally{ws.close();}
