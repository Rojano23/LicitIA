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
let imported=false, mode='populated';let watching=false,ack=false,workflowState='NEW',disabled=false;
const tender={id:'ui-r2-tender',title:'Expediente sintético UI-R2',external_reference:'UIR2-LOCAL',institution_profile:'General',status:'DRAFT',created_at:'2026-10-23T12:00:00Z',updated_at:'2026-10-23T12:00:00Z'};
const sources=['PEMEX','CFE','COMPRAS_MX'].map(id=>({id,name:id==='COMPRAS_MX'?'Compras MX':id,enabled:id!=='COMPRAS_MX',last_scan_state:id==='CFE'?'PARTIAL':id==='PEMEX'?'SUCCESS':null,last_error:null,areas:id==='COMPRAS_MX'?[]:[{key:id==='CFE'?'public':'support',label:'Área pública'}],configuration:{areas:id==='CFE'?['public']:['support']},capabilities:{automation_status:id==='COMPRAS_MX'?'DEFERRED_SOURCE_AUTOMATION_RESTRICTED':'AVAILABLE'}}));
const base={description:'Objeto público sintético de revisión visual',business_area:'Área industrial',published_date:'2026-10-23',event_type:'Nacional',supply_type:'Bienes',source_status:'Publicado',revision:1,document_count:2,public_url:'https://www.pemex.com/public',first_seen:'2026-10-23',last_seen:'2026-10-23',match:null,unread_document_changes:1};
const row=()=>({...base,id:'new',source_id:'PEMEX',external_id:'PROC-001',title:'Controladores PLC e instrumentación para mantenimiento industrial — revisión sintética',procedure_number:'PROC-001',internal_state:imported?'IMPORTED':workflowState,watching,unread_changes:ack?0:50,linked_tender:imported?{id:tender.id,available:true}:null});
const scan={id:'completed',source_id:'PEMEX',status:'SUCCESS',started_at:'2026-10-24T12:00:00Z',finished_at:'2026-10-24T12:03:00Z',query:{areas:['support'],published_from:'2026-09-25',published_to:'2026-10-24',event_type:null,supply_type:null,page_size:100},metrics:{pages_attempted:4,pages_completed:4,unique_opportunities:111,rows_retrieved:111}};
function fixture(url,method='GET',body='{}') {
 const u=new URL(url),p=u.pathname,q=u.searchParams;
 if(p==='/health')return {status:'ok'};if(p==='/ocr/providers')return [];if(p==='/vision/providers')return {runtime_available:false,model_available:false};
 if(p==='/discovery/opportunities/opportunity-0')return {...row(),id:'opportunity-0',match:q.get('profile_id')?{matched:true,include_hits:[{term:'PLC',matched_text:'PLC',field:'title',kind:'EXACT'}],exclude_hits:[],restrictions:[]}:null};
 if(p.endsWith('/opportunity-0/tender-preview'))return {opportunity_id:'opportunity-0',source_id:'PEMEX',source_fingerprint:'private',binding:'private',internal_state:workflowState,suggested_title:row().title,context:{},documents:[{id:'document',name:'Bases.pdf',public_url:'https://www.pemex.com/file',metadata_fingerprint:'private',last_import:null}],linked_tender:null,selection_default:'NONE',analysis_automatic:false};
 if(p.endsWith('/opportunity-0/changes'))return {items:Array.from({length:50},(_,i)=>({id:'private-event-'+i,category:i===0?'NEW_OPPORTUNITY':'DOCUMENT_ADDED',origin:'SOURCE',detected_at:'2026-10-24T12:00:00.12345Z',summary:'RAW_PRIVATE',changed_fields:{document:{name:'Bases_'+i+'.pdf'},private:'SECRET'},acknowledged_at:ack?'2026-10-24':null})),total:50,offset:0,limit:100};
 if(p.endsWith('/opportunity-0/following')){watching=JSON.parse(body).following;return {...row(),id:'opportunity-0'};}
 if(p.endsWith('/opportunity-0/state')){workflowState=JSON.parse(body).internal_state;return {...row(),id:'opportunity-0'};}
 if(p.endsWith('/opportunity-0/changes/acknowledge')){ack=true;return {};}
 if(p==='/tenders')return mode==='empty'?[]:[tender];
 if(p==='/companies'||p.endsWith('/documents')||p.endsWith('/providers')||p.endsWith('/scope-review')||p.endsWith('/technical-alternatives'))return [];
 if(p.endsWith('/workspace'))return {tender_id:tender.id,processing:{status:'NOT_PROCESSED'},scopes:[],requirements:{scope_note:'TEST ONLY',requirements:[]},semantics:{scope_note:'TEST ONLY',requirements:[]},warnings:[]};
 if(p==='/discovery/sources')return sources.map(s=>s.id==='PEMEX'?{...s,enabled:!disabled,areas:[{key:'support',label:'Servicios y Bienes de Soporte'},{key:'logistics',label:'Logística'}],configuration:{areas:['support','logistics']}}:{...s,enabled:false});
 if(p==='/discovery/profiles')return [{id:'profile',name:'Instrumentación',revision:1,include_keywords:['PLC'],exclude_keywords:[],synonyms:{},source_ids:[],business_areas:[],active:true}];
 if(p==='/discovery/monitoring/summary')return {new_opportunities:mode==='empty'?0:1,followed_with_changes:mode==='empty'?0:1,changed_opportunities:2,unread_changes:3,new_documents:1};
 if(p==='/discovery/scans')return Array.from({length:100},(_,i)=>({...scan,id:'scan-'+i}));
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
  await call('Fetch.fulfillRequest',{requestId,responseCode:request.method==='OPTIONS'?204:value===undefined?503:200,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'*'},{name:'Access-Control-Allow-Headers',value:'*'},{name:'Access-Control-Allow-Methods',value:'GET,POST,PATCH,OPTIONS'}],body:Buffer.from(JSON.stringify(value??{detail:'TEST_ISOLATED_UNAVAILABLE'})).toString('base64')});
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
async function click(label){await evaluate(`Array.from(document.querySelectorAll('button,a,summary')).find(e=>e.textContent.trim()===${JSON.stringify(label)}&&e.getClientRects().length)?.click()`);await new Promise(r=>setTimeout(r,160));}
async function select(label,value){await evaluate(`(()=>{const e=Array.from(document.querySelectorAll('label')).find(e=>e.textContent.trim().startsWith(${JSON.stringify(label)}))?.querySelector('select');if(!e)throw new Error('Missing select');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await new Promise(r=>setTimeout(r,160));}
async function stripLines(){return await evaluate(`Array.from(document.querySelector('.source-strip').children).map(block=>{const name=block.querySelector('strong').getBoundingClientRect();const state=block.querySelector('small,.ui-badge').getBoundingClientRect();return {name:name.y,state:state.y,height:Math.max(name.height,state.height)};})`);}
try{
 await size(1440,900);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/discovery'});await until(`document.querySelectorAll('.source-strip > span').length===3`);await shot('01-strip-desktop');for(const row of await stripLines())assert.ok(Math.abs(row.name-row.state)<row.height/2);checks.push('desktop name/status same visual line for each source');
 await size(1366,768);await evaluate('window.scrollTo(0,0)');await shot('02-strip-1366');for(const row of await stripLines())assert.ok(Math.abs(row.name-row.state)<row.height/2);
 await size(390,844);await evaluate('window.scrollTo(0,0)');assert.ok(await evaluate('document.documentElement.scrollWidth<=390'));await shot('03-strip-narrow');checks.push('1366 compact / narrow wraps with no page overflow');
 await size(1440,900);await evaluate(`document.getElementById('source-consultation').scrollIntoView({block:'start'})`);await shot('04-step1-pemex');assert.equal(await evaluate(`document.getElementById('source-consultation').textContent.includes('Deshabilitar fuente con áreas')`),false);
 await evaluate(`Array.from(document.querySelectorAll('label')).find(e=>e.textContent==='Servicios y Bienes de Soporte').querySelector('input').click()`);await shot('05-selected-areas');await click('Consultar fuente');await until(`Array.from(document.querySelectorAll('button')).some(e=>e.textContent==='Consultar fuente'&&!e.disabled)`);
 assert.equal(writes.filter(u=>u.endsWith('/PEMEX/scans')).length,1);assert.equal(writes.filter(u=>u.endsWith('/sources/PEMEX')).length,0);checks.push('explicit scan works with area subset / no administrative PATCH');
 disabled=true;await call('Page.reload',{ignoreCache:true});await until(`document.querySelector('#source-consultation')?.textContent.includes('Esta fuente está deshabilitada')`);await evaluate(`document.getElementById('source-consultation').scrollIntoView({block:'start'})`);await shot('06-disabled-source');assert.equal(await evaluate(`Array.from(document.querySelectorAll('button')).find(e=>e.textContent==='Consultar fuente').disabled`),true);
 await click('Configurar fuente');await until(`document.activeElement?.id==='source-settings'`);await shot('07-settings-sources');assert.ok(await evaluate(`document.querySelector('.support-product').textContent.includes('Configurar PEMEX')`));checks.push('disabled guidance / settings deep link and administration preserved');
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',checks,errors,writes,fixture:'TEST_ISOLATED_SYNTHETIC_API'},null,2));console.log(JSON.stringify({status:'PASS',groups:checks.length}));
}finally{ws.close();}
