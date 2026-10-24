import {render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach,it,expect,vi} from 'vitest';
import axios from 'axios';
import ProductApp from '../ProductApp';
import {TenderCreation} from './TenderCreation';
import {DocumentImports} from './DocumentImports';
import {tendersApi,type TenderDocument} from '../api/tenders';
import {droppedOriginals,enumerateEntry,safeRelativePath,selectedOriginal,type DroppedEntry} from './expedienteSelection';
const tender={id:'new',title:'Referencia humana',external_reference:null,institution_profile:null,status:'DRAFT',created_at:'2026-10-24',updated_at:'2026-10-24'};
const original=(name='Bases.pdf',path='')=>{const f=new File(['bytes '+name],name,{type:'application/pdf'});if(path)Object.defineProperty(f,'webkitRelativePath',{value:path});return f;};
const props={apiUrl:'/api',onCreated:vi.fn(),onCancel:vi.fn()};
beforeEach(()=>{vi.restoreAllMocks();props.onCreated.mockClear();props.onCancel.mockClear();vi.spyOn(window,'confirm').mockReturnValue(true);localStorage.clear();});
function choose(files:File[]){fireEvent.change(screen.getByLabelText('Seleccionar archivos'),{target:{files}});}
function identify(){fireEvent.change(screen.getByLabelText('Referencia o nombre de la licitación'),{target:{value:' Referencia humana '}});}
function fileEntry(name:string):DroppedEntry{return {name,isFile:true,isDirectory:false,file:resolve=>resolve(original(name)),createReader:()=>{throw new Error('not a directory');}};}
function folder(name:string,batches:DroppedEntry[][]):DroppedEntry{return {name,isFile:false,isDirectory:true,file:()=>{throw new Error('not a file');},createReader:()=>{let i=0;return {readEntries:resolve=>resolve(batches[i++]??[])};}};}
it('UIR7-NEW-01/02/03/36/37 empty creation uses the existing Tender contract',async()=>{
 const spy=vi.spyOn(tendersApi,'create').mockResolvedValue(tender);render(<TenderCreation {...props}/>);
 expect(screen.getByLabelText(/Crear desde expediente/)).toBeChecked();expect(screen.getByText(/No has seleccionado/)).toBeVisible();identify();
 expect(screen.getByText('Crear licitación y agregar documentos')).toBeDisabled();fireEvent.click(screen.getByLabelText(/Crear vacía/));fireEvent.click(screen.getByRole('button',{name:'Crear licitación'}));
 await waitFor(()=>expect(props.onCreated).toHaveBeenCalledWith(tender,undefined));expect(spy).toHaveBeenCalledWith('/api',{title:'Referencia humana',external_reference:null,institution_profile:null});
});
it.each([5,30,125])('UIR7-NEW-04/08/09/15/16 compact selection of %i originals supports review/removal',count=>{
 render(<TenderCreation {...props}/>);choose(Array.from({length:count},(_,i)=>original(`Archivo-${i}.pdf`)));
 expect(screen.getByRole('status')).toHaveTextContent(`${count} documentos listos para agregar`);const disclosure=screen.getByText(`Revisar archivos (${count})`);expect(disclosure.closest('details')).not.toHaveAttribute('open');
 fireEvent.click(disclosure);fireEvent.click(screen.getByLabelText('Quitar Archivo-0.pdf'));expect(screen.getByRole('status')).toHaveTextContent(`${count-1} documentos listos`);fireEvent.click(screen.getByText('Quitar todos'));expect(screen.getByText(/No has seleccionado/)).toBeVisible();
});
it('UIR7-NEW-05/07 directory picker preserves nested relative locations and browser attribute',()=>{
 render(<TenderCreation {...props}/>);expect(screen.getByLabelText('Seleccionar carpeta')).toHaveAttribute('webkitdirectory');
 fireEvent.change(screen.getByLabelText('Seleccionar carpeta'),{target:{files:[original('Bases.pdf','Raíz/Bases/Bases.pdf'),original('Bases.pdf','Raíz/Anexos/Bases.pdf')]}});
 expect(screen.getByText('Raíz/Bases/Bases.pdf')).toBeInTheDocument();expect(screen.getByText('Raíz/Anexos/Bases.pdf')).toBeInTheDocument();expect(screen.getByRole('status')).toHaveTextContent('2 documentos');
});
it('UIR7-NEW-06/07 directory drop recurses through all native reader batches, including hidden originals',async()=>{
 const entry=folder('Raíz',[[fileEntry('A.pdf'),folder('Anexos',[[fileEntry('B.docx')],[fileEntry('.DS_Store')],[]])],[fileEntry('C.zip')],[]]);
 const result=await enumerateEntry(entry);expect(result.map(f=>f.relativePath)).toEqual(['Raíz/A.pdf','Raíz/Anexos/B.docx','Raíz/Anexos/.DS_Store','Raíz/C.zip']);expect(new Set(result.map(f=>f.clientImportId)).size).toBe(4);
});
it('UIR7-NEW-06 folder drop captures handles and supports native file fallback',async()=>{
 const entry=folder('Root',[[fileEntry('A.pdf')],[]]);const transfer={items:[{kind:'file',webkitGetAsEntry:()=>entry,getAsFile:()=>null}],files:[]} as unknown as DataTransfer;
 expect((await droppedOriginals(transfer))[0].relativePath).toBe('Root/A.pdf');expect((await droppedOriginals({items:[],files:[original('fallback.txt')]} as unknown as DataTransfer))[0].file.name).toBe('fallback.txt');
});
it('directory traversal failure is explicit and never silently accepts a partial folder',async()=>{
 render(<TenderCreation {...props}/>);const bad=folder('Root',[[fileEntry('A.pdf')],[]]);bad.createReader=()=>({readEntries:(_resolve,reject)=>reject(new DOMException('denied'))});
 fireEvent.drop(screen.getByRole('group',{name:'Seleccionar expediente'}),{dataTransfer:{items:[{kind:'file',webkitGetAsEntry:()=>bad,getAsFile:()=>null}]}});
 expect(await screen.findByRole('alert')).toHaveTextContent('Esta selección no se agregó');expect(screen.getByText(/No has seleccionado/)).toBeVisible();
});
it('UIR7-NEW-10/11 all extensions match the permissive canonical registry; ZIP is not expanded',()=>{
 for(const name of ['pdf.pdf','word.docx','excel.xls','sheet.xlsx','data.csv','text.txt','archive.zip','.DS_Store','unknown.bin'])expect(selectedOriginal(original(name)).omittedReason).toBeUndefined();
 for(const path of ['/Users/private/x.pdf','C:\\private\\x.pdf','../x.pdf','root/../x.pdf','file://x.pdf'])expect(safeRelativePath(path)).toBeUndefined();
 expect(safeRelativePath('Root/Anexos/A.pdf')).toBe('Root/Anexos/A.pdf');
});
it('UIR7-NEW-12–14/38 unsafe selections are disclosed and excluded while valid originals may proceed',async()=>{
 const spy=vi.spyOn(tendersApi,'create').mockResolvedValue(tender);render(<TenderCreation {...props}/>);identify();choose([original('valid.pdf'),original('private.pdf','/Users/private/private.pdf')]);
 expect(screen.getByRole('status')).toHaveTextContent('1 documentos listos para agregar · 1 archivos omitidos');expect(document.body.textContent).not.toContain('/Users/private');
 fireEvent.click(screen.getByText('Ver archivos omitidos (1)'));expect(screen.getByText(/ubicación relativa del archivo no es segura/)).toBeInTheDocument();fireEvent.click(screen.getByText('Crear licitación y agregar documentos'));
 await waitFor(()=>expect(spy).toHaveBeenCalledOnce());const session=props.onCreated.mock.calls[0][1];expect(session.files).toHaveLength(1);expect(session.omittedCount).toBe(1);
});
it('UIR7-NEW-17/35 repeated submit while pending creates exactly once and navigation cannot interrupt',async()=>{
 let resolve!:(v:typeof tender)=>void;const spy=vi.spyOn(tendersApi,'create').mockImplementation(()=>new Promise(r=>{resolve=r;}));render(<TenderCreation {...props}/>);identify();fireEvent.click(screen.getByLabelText(/Crear vacía/));const form=screen.getByRole('button',{name:'Crear licitación'}).closest('form')!;fireEvent.submit(form);fireEvent.submit(form);expect(spy).toHaveBeenCalledOnce();
 const event=new CustomEvent('tuscope:navigate',{cancelable:true});fireEvent(window,event);expect(event.defaultPrevented).toBe(true);resolve(tender);await waitFor(()=>expect(props.onCreated).toHaveBeenCalledOnce());
});
it('lost create response retains identification/files, does not automatically retry',async()=>{
 const spy=vi.spyOn(tendersApi,'create').mockRejectedValue(new Error('lost response'));render(<TenderCreation {...props}/>);identify();choose([original()]);fireEvent.click(screen.getByText('Crear licitación y agregar documentos'));expect(await screen.findByRole('alert')).toHaveTextContent('verifica si ya existe');expect(screen.getByRole('status')).toHaveTextContent('1 documentos');expect(spy).toHaveBeenCalledOnce();expect(props.onCreated).not.toHaveBeenCalled();
});
it('cancel requires explicit discard only before Tender creation',()=>{render(<TenderCreation {...props}/>);identify();choose([original()]);vi.mocked(window.confirm).mockReturnValue(false);fireEvent.click(screen.getByText('Cancelar'));expect(props.onCancel).not.toHaveBeenCalled();vi.mocked(window.confirm).mockReturnValue(true);fireEvent.click(screen.getByText('Cancelar'));expect(props.onCancel).toHaveBeenCalledOnce();});
it('UIR7-NEW-18–24/39 seeded canonical importer reports partial outcomes and retains exact retry File/path',async()=>{
 const a=original('A.pdf'),b=original('B.pdf'),c=original('C.pdf'),d=original('D.pdf');const files=[a,b,c,d].map((f,i)=>selectedOriginal(f,`Root/${i}/${f.name}`));const spy=vi.spyOn(tendersApi,'import').mockImplementation(async(_base,_t,file)=>{if(file===d)throw new Error('offline');return {filename:file.name,status:file===a?'IMPORTED':file===b?'DUPLICATE':'NAME_CONFLICT',document_id:'doc'};});
 const ack=vi.fn();render(<DocumentImports apiUrl='/api' tenderId='new' documents={[]} onImported={()=>{}} initialSession={{id:'session',tenderId:'new',files}} onSessionAccepted={ack}/>);
 await waitFor(()=>expect(spy).toHaveBeenCalledTimes(4));expect(screen.getByLabelText('Resultado de creación')).toHaveTextContent('1 documentos agregados · 1 duplicados · 1 requieren decisión · 1 fallidos');expect(ack).toHaveBeenCalledOnce();
 expect(spy.mock.calls[3]).toEqual(['/api','new',d,'NONE',undefined,'Root/3/D.pdf']);fireEvent.click(screen.getByText('Reintentar importación'));await waitFor(()=>expect(spy).toHaveBeenCalledTimes(5));expect(spy.mock.calls[4][2]).toBe(d);expect(screen.getByText('Licitación creada')).toBeVisible();
});
it('UIR7-NEW-19/21/22 same-name folder conflicts keep independent IDs and resolve B then A',async()=>{
 const a=original('Same.pdf','Root/A/Same.pdf'),b=new File(['DIFFERENT'],'Same.pdf');const files=[selectedOriginal(a),selectedOriginal(b,'Root/B/Same.pdf')];
 const docs:TenderDocument[]=[{id:'target',tender_id:'new',original_filename:'Same.pdf',is_current:true,revision_number:1,imported_at:'2026-10-24'} as TenderDocument];
 const spy=vi.spyOn(tendersApi,'import').mockImplementation(async(_base,_t,file,action)=>({filename:file.name,status:action==='NONE'?'NAME_CONFLICT':'IMPORTED',document_id:'target'}));render(<DocumentImports apiUrl='/api' tenderId='new' documents={docs} onImported={()=>{}} initialSession={{id:'s',tenderId:'new',files}}/>);
 await waitFor(()=>expect(screen.getAllByLabelText('Decisión para Same.pdf')).toHaveLength(2));const rows=Array.from(document.querySelectorAll<HTMLLIElement>('[data-import-id]'));expect(rows[0].dataset.importId).not.toBe(rows[1].dataset.importId);
 fireEvent.change(within(rows[1]).getByLabelText('Decisión para Same.pdf'),{target:{value:'NEW_REVISION'}});fireEvent.change(within(rows[1]).getByLabelText('Revisión actual para Same.pdf'),{target:{value:'target'}});fireEvent.click(within(rows[1]).getByText('Confirmar decisión'));await waitFor(()=>expect(spy).toHaveBeenLastCalledWith('/api','new',b,'NEW_REVISION','target','Root/B/Same.pdf'));
 fireEvent.change(within(rows[0]).getByLabelText('Decisión para Same.pdf'),{target:{value:'IMPORT_INDEPENDENT'}});fireEvent.click(within(rows[0]).getByText('Confirmar decisión'));await waitFor(()=>expect(spy).toHaveBeenLastCalledWith('/api','new',a,'IMPORT_INDEPENDENT','','Root/A/Same.pdf'));
});
it('UIR7-NEW-25–34 actual shell transfers to matching Documents once, retains selection across sidebar/rerender, no analysis writes',async()=>{
 window.location.hash='#/licitaciones';const get=vi.spyOn(axios,'get').mockImplementation(async(url:string)=>{if(url.endsWith('/tenders'))return {data:[]};if(url.endsWith('/tenders/new'))return {data:tender};if(url.endsWith('/documents'))return {data:[]};throw new Error('unexpected read');});
 const post=vi.spyOn(axios,'post').mockImplementation(async(url:string,body)=>{if(url.endsWith('/tenders'))return {data:tender};if(url.endsWith('/documents/import')){const file=(body as FormData).get('files') as File;return {data:[{filename:file.name,status:'IMPORTED',document_id:'doc'}]};}throw new Error('no auto analysis');});
 const user=userEvent.setup();const view=render(<ProductApp/>);await screen.findByText('Aún no hay licitaciones.');fireEvent.click(screen.getAllByText('Nueva licitación')[0]);identify();choose([original('A.pdf','Root/A.pdf')]);await user.click(screen.getByLabelText('Contraer menú'));view.rerender(<ProductApp/>);expect(screen.getByRole('status')).toHaveTextContent('1 documentos');expect(screen.getByLabelText('Referencia o nombre de la licitación')).toHaveValue(' Referencia humana ');
 fireEvent.click(screen.getByText('Crear licitación y agregar documentos'));await waitFor(()=>expect(window.location.hash).toBe('#/licitaciones/new/documentos'));await screen.findByText('Licitación creada');await waitFor(()=>expect(post).toHaveBeenCalledTimes(2));expect(post.mock.calls.map(c=>c[0])).toEqual(['http://localhost:8000/tenders','http://localhost:8000/tenders/new/documents/import']);expect(get).toHaveBeenCalled();
 fireEvent(window,new HashChangeEvent('hashchange'));expect(post).toHaveBeenCalledTimes(2);const form=post.mock.calls[1][1] as FormData;expect(form.get('source_relative_paths')).toBe('Root/A.pdf');expect(form.get('files')).toBeInstanceOf(File);expect(form.get('source_id')).toBeNull();
});
it('created Tender with unreadable Documents retains selection until explicit navigation discard; no recreation/deletion',async()=>{
 window.location.hash='#/licitaciones';vi.spyOn(axios,'get').mockImplementation(async(url:string)=>{if(url.endsWith('/tenders'))return {data:[]};throw new Error('offline');});const post=vi.spyOn(axios,'post').mockResolvedValue({data:tender});const remove=vi.spyOn(axios,'delete');
 render(<ProductApp/>);await screen.findByText('Aún no hay licitaciones.');fireEvent.click(screen.getAllByText('Nueva licitación')[0]);identify();choose([original()]);fireEvent.click(screen.getByText('Crear licitación y agregar documentos'));await screen.findByText(/No pudimos cargar esta licitación/);
 vi.mocked(window.confirm).mockReturnValue(false);window.location.hash='#/mi-empresa';fireEvent(window,new HashChangeEvent('hashchange'));await waitFor(()=>expect(window.location.hash).toBe('#/licitaciones/new/documentos'));expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('La licitación se conserva'));
 expect(post).toHaveBeenCalledTimes(1);expect(remove).not.toHaveBeenCalled();const unload=new Event('beforeunload',{cancelable:true});fireEvent(window,unload);expect(unload.defaultPrevented).toBe(true);
});
it('visual polish keeps two labelled native pickers in one input surface without proactive ZIP/browser explanation',()=>{
 render(<TenderCreation {...props}/>);const surface=screen.getByRole('group',{name:'Seleccionar expediente'});
 expect(within(surface).getByLabelText('Seleccionar archivos')).toHaveAttribute('type','file');expect(within(surface).getByLabelText('Seleccionar carpeta')).toHaveAttribute('webkitdirectory');
 expect(surface.querySelectorAll('.expediente-controls')).toHaveLength(1);expect(document.body.textContent).not.toMatch(/ZIP|navegador|descomprim/);expect(screen.getByText('Se agregarán al expediente los archivos compatibles.')).toBeVisible();
});
it('visual polish hides omission action when empty and places clear-all exclusively in collapsed file review',()=>{
 render(<TenderCreation {...props}/>);choose([original()]);expect(screen.queryByText(/Ver archivos omitidos/)).not.toBeInTheDocument();
 const review=screen.getByText('Revisar archivos (1)').closest('details')!;expect(review).not.toHaveAttribute('open');expect(within(review).getByText('Quitar todos')).not.toBeVisible();
 fireEvent.click(within(review).getByText('Revisar archivos (1)'));expect(within(review).getByText('Quitar todos')).toBeVisible();
});
