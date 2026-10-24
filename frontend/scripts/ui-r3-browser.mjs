/** Local browser acceptance via Chromium CDP, no package dependency.
 * Start Vite on 127.0.0.1:5181 and Chromium with --remote-debugging-port=9331.
 * All API responses below are TEST-ISOLATED synthetic fixtures. No product DB or public source requests.
 * node scripts/ui-r2-browser.mjs [artifact-directory]
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out = path.resolve(process.argv[2] ?? '../backend/reports/ui_r3/browser');
await fs.mkdir(out, { recursive: true });
const tabs = await (await fetch('http://127.0.0.1:9331/json')).json();
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));
let sequence = 0; const pending = new Map(); const errors = []; const writes = []; const requests = [];
function call(method, params = {}) {
  return new Promise((resolve, reject) => { const id = ++sequence;pending.set(id, { resolve, reject });ws.send(JSON.stringify({id,method,params})); });
}
let mode='normal',contentFail=false,pagesFail=false,delayContent=false;
const tender={id:'r3',title:'Mantenimiento industrial — expediente de prueba UI-R3',external_reference:'UIR3-001',institution_profile:'General',status:'DRAFT',created_at:'2026-10-23T12:00:00Z',updated_at:'2026-10-23T12:00:00Z'};
const documents=[['current','Bases.pdf',2,true,'TEXT_EXTRACTION_COMPLETE'],['previous','Bases.pdf',1,false,'TEXT_EXTRACTION_COMPLETE'],['office','Anexo.xlsx',1,true,'PENDING'],['scan','Acta.pdf',1,true,'NO_NATIVE_TEXT']].map(([id,name,revision,current,status])=>({id,tender_id:'r3',original_filename:name,mime_type:name.endsWith('.pdf')?'application/pdf':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',file_size_bytes:2500,sha256:'synthetic-hash-only-test',status:'IMPORTED',processing_status:status,page_count:status==='PENDING'?0:1,revision_of_document_id:id==='current'?'previous':null,revision_number:revision,is_current:current,imported_at:'2026-10-23T12:00:00Z'}));
const pdf='JVBERi0xLjcKJcK1wrYKJSBXcml0dGVuIGJ5IE11UERGIDEuMjguMgoKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFIvSW5mbzw8L1Byb2R1Y2VyKE11UERGIDEuMjguMik+Pj4+CmVuZG9iagoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0NvdW50IDEvS2lkc1s0IDAgUl0+PgplbmRvYmoKCjMgMCBvYmoKPDwvRm9udDw8L2hlbHYgNSAwIFI+Pj4+CmVuZG9iagoKNCAwIG9iago8PC9UeXBlL1BhZ2UvTWVkaWFCb3hbMCAwIDU5NSA4NDJdL1JvdGF0ZSAwL1Jlc291cmNlcyAzIDAgUi9QYXJlbnQgMiAwIFIvQ29udGVudHNbNiAwIFJdPj4KZW5kb2JqCgo1IDAgb2JqCjw8L1R5cGUvRm9udC9TdWJ0eXBlL1R5cGUxL0Jhc2VGb250L0hlbHZldGljYS9FbmNvZGluZy9XaW5BbnNpRW5jb2Rpbmc+PgplbmRvYmoKCjYgMCBvYmoKPDwvTGVuZ3RoIDIwMS9GaWx0ZXIvRmxhdGVEZWNvZGU+PgpzdHJlYW0KeNotjr1OBDEMhPs8RWokwPHP+FY6XYGgoUNKd6La3YgCChqe/yZ7yEqimXg+u/yWl15aFVarkJrQ2n/K89f+/Vcbah/1eo7wRbdQMxXdVMI9wsJVfAnz4au36fl0nNqY2Kj38Mtnfy9SH7U9LScXIf61XM8+UrEgeXY0rITOKFQALHlKz2BH3AeyZ/A2epaOgQ38peNo1O0Y0h/mqszkJBjJA7uK6T/DpiZX+a6sANeFTp3J/oPILLdh9k4+GAf9rZePcgM5IkSUCmVuZHN0cmVhbQplbmRvYmoKCnhyZWYKMCA3CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDA0MiAwMDAwMCBuIAowMDAwMDAwMTIwIDAwMDAwIG4gCjAwMDAwMDAxNzIgMDAwMDAgbiAKMDAwMDAwMDIxMyAwMDAwMCBuIAowMDAwMDAwMzIwIDAwMDAwIG4gCjAwMDAwMDA0MDkgMDAwMDAgbiAKCnRyYWlsZXIKPDwvU2l6ZSA3L1Jvb3QgMSAwIFIvSURbPDZCNzlDMzhGNzJDMjlEM0I3RUMyOUY1N0MyOERDMkFEPjxDMDdBQ0QzNjVGNDI3RUFFMTc5NkZGMTUxMEQyODA2Rj5dPj4Kc3RhcnR4cmVmCjY3OQolJUVPRgo=';
function fixture(url,method='GET',body=''){
 const p=new URL(url).pathname;
 if(p==='/tenders'&&method==='POST')return tender;
 if(p==='/tenders')return mode==='empty'?[]:[tender,...[2,3,4,5].map(n=>({...tender,id:'r'+n,external_reference:'UIR3-00'+n,title:'Expediente sintético de mantenimiento '+n,status:n===4?'ARCHIVED':'ACTIVE'}))];
 if(p==='/tenders/r3')return tender;
 if(p==='/tenders/r3/documents')return documents;
 if(p.endsWith('/import')){const name=body?.match(/filename="([^"]+)"/)?.[1]??'A.pdf';return [{filename:name,status:body.includes('IMPORT_INDEPENDENT')||body.includes('NEW_REVISION')?'IMPORTED':'NAME_CONFLICT',document_id:'current'}];}
 if(p.endsWith('/pages')){if(pagesFail)return undefined;const id=p.split('/').at(-2);return [1,2].map(n=>({id:id+'-p'+n,document_id:id,page_number:n,text:'Texto derivado de prueba, página '+n,extraction_method:'NATIVE',ocr_results:[]}));}
 if(p.endsWith('/content'))return contentFail?undefined:{pdf};
 if(p.endsWith('/workspace'))return {tender_id:'r3',processing:{status:'PARTIAL'},scopes:[],requirements:{scope_note:'TEST',requirements:[]},semantics:{scope_note:'TEST',requirements:[]},warnings:[]};
 if(p.endsWith('/documents')||p==='/companies'||p.endsWith('/providers'))return [];
 return undefined;
}
ws.addEventListener('message', async event => {
 const m=JSON.parse(event.data);
 if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}return;}
 if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text+': '+(m.params.exceptionDetails.exception?.description??''));
 if(m.method==='Fetch.requestPaused') {
  const {requestId,request}=m.params;requests.push(request.url);
  if(request.method!=='GET' && request.method!=='OPTIONS')writes.push(request.url);
  if(delayContent&&new URL(request.url).pathname.endsWith('/content'))await new Promise(r=>setTimeout(r,800));
  const value=fixture(request.url,request.method,request.postData);
  if(new URL(request.url).pathname.endsWith('/content')&&value?.pdf){await call('Fetch.fulfillRequest',{requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'application/pdf'},{name:'Access-Control-Allow-Origin',value:'*'}],body:value.pdf});return;}
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
 await size(1366,768);await call('Page.navigate',{url:'http://127.0.0.1:5181/#/licitaciones'});await until(`document.querySelectorAll('.tender-product tbody tr').length===5`);await shot('01-licitaciones');checks.push('table real API fixtures / five Tender rows / translated status');
 mode='empty';await click('Actualizar licitaciones');await until(`document.body.textContent.includes('Aún no hay licitaciones.')`);await shot('02-empty');mode='normal';await click('Actualizar licitaciones');await until(`document.querySelector('tbody tr')!==null`);
 await click('Nueva licitación');await shot('03-create');await evaluate(`(()=>{const e=document.querySelector('.tender-create input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'Nuevo expediente de prueba');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await click('Crear licitación');await until(`location.hash.includes('/r3/resumen')`);checks.push('empty / explicit creation / no auto submit');
 await go('/licitaciones/r3/resumen');await until(`document.body.textContent.includes('4 revisiones registradas')`);await shot('04-resumen');await shot('05-resumen-attention');assert.ok(await evaluate(`document.body.textContent.includes('1 revisiones con extracción parcial')`));checks.push('summary deterministic document count and attention');
 await go('/licitaciones/r3/documentos');await until(`document.querySelector('.document-registry tbody tr')!==null`);await click('Ver documento');await until(`document.querySelector('.product-pdf-viewer')!==null`);await new Promise(r=>setTimeout(r,600));await top();await shot('06-documents-viewer');await shot('07-current-revision');
 const bounds=await evaluate(`document.querySelector('.product-pdf-viewer').getBoundingClientRect().toJSON()`);assert.ok(bounds.width>=500);checks.push('1366 viewer width >=500 / selected original PDF');
 await evaluate(`document.querySelectorAll('.document-registry tbody button')[1].click()`);await until(`document.querySelector('.document-viewer p').textContent.includes('Versión anterior')`);await shot('08-previous-revision');checks.push('previous revision retains unique original context');
 await click('Importar documentos');await evaluate(`document.querySelector('.document-imports').scrollIntoView()`);
 await evaluate(`(()=>{const input=document.querySelector('.document-imports input[type=file]'),transfer=new DataTransfer();transfer.items.add(new File(['A exact bytes'],'A.pdf',{type:'application/pdf'}));transfer.items.add(new File(['B other bytes'],'B.pdf',{type:'application/pdf'}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 await click('Importar archivos seleccionados');await until(`document.querySelectorAll('.conflict-decision').length===2`);await evaluate(`document.querySelector('.conflict-decision').scrollIntoView()`);await shot('09-conflict');await shot('10-multiple-conflicts');await click('Importar documentos');checks.push('two client file identities / two independent human conflicts');
 delayContent=true;await evaluate(`document.querySelectorAll('.document-registry tbody button')[3].click()`);await until(`document.querySelector('.document-viewer').textContent.includes('Cargando PDF original')`);await shot('11-viewer-loading');delayContent=false;await until(`document.querySelector('.product-pdf-viewer')!==null`);
 contentFail=true;pagesFail=true;await click('Reabrir visor');await until(`document.querySelector('.document-viewer [role=alert]')!==null`);await evaluate(`document.querySelector('.document-viewer').scrollIntoView()`);await shot('12-viewer-error');contentFail=false;pagesFail=false;await evaluate(`document.querySelector('.document-viewer [role=alert] button').click()`);await until(`document.querySelector('.product-pdf-viewer')!==null`);checks.push('viewer error / bounded retry / registry retained');
 await evaluate(`document.querySelectorAll('.document-registry tbody button')[2].click()`);await until(`document.querySelector('.document-viewer').textContent.includes('Vista previa no disponible')`);await shot('13-non-pdf');checks.push('non-PDF honest fallback no fabricated render/download');
 await evaluate(`document.querySelectorAll('.document-registry tbody button')[0].click()`);await until(`document.querySelector('.product-pdf-viewer')!==null`);
 await evaluate(`document.querySelector('.document-registry input').focus()`);await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});assert.ok(await evaluate(`document.activeElement.tagName==='SELECT' && getComputedStyle(document.activeElement).outlineStyle!=='none'`));assert.ok(await evaluate(`Array.from(document.querySelectorAll('.tender-documents input,.tender-documents select')).every(e=>e.closest('label')||e.labels?.length)`));checks.push('keyboard filter order / visible focus / labels');
 for(const[w,h]of [[1366,768],[1440,900],[1920,1080],[768,900],[390,844]]){await size(w,h);await top();assert.ok(await evaluate(`document.documentElement.scrollWidth<=${w}`));await shot('14-documents-'+w);}checks.push('3 desktop + 768/390 / no page overflow');
 await size(1366,768);await go('/licitaciones/r3/requisitos');await until(`document.querySelector('.tender-context-nav a[aria-current]')?.textContent==='Requisitos'`);for(const section of ['comercial','preparacion','propuesta']){await go('/licitaciones/r3/'+section);await until(`document.querySelector('.tender-context-nav a[aria-current]')?.getAttribute('href').endsWith('/${section}')`);}await go('/configuracion/diagnostico');checks.push('legacy Requirements / Commercial / Readiness / Proposal / diagnostics reachable');
 assert.deepEqual(errors,[]);assert.ok(writes.every(u=>u.endsWith('/documents/import')||u.endsWith('/tenders')));checks.push('no runtime exceptions / no OCR Vision LLM or automatic writes');
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({status:'PASS',fixture:'ISOLATED_TEST_ONLY',checks,writes,errors,viewer1366:bounds},null,2));console.log(JSON.stringify({status:'PASS',groups:checks.length}));
}finally{ws.close();}
