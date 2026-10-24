import {render,screen,within,waitFor,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach,it,expect,vi} from 'vitest';
import {DocumentImports} from './DocumentImports';
import {tendersApi,type TenderDocument} from '../api/tenders';
const doc=(name:string,id:string):TenderDocument=>({id,tender_id:'t',original_filename:name,source_relative_path:null,stored_relative_path:'private',mime_type:'application/pdf',file_size_bytes:10,sha256:'hash',status:'IMPORTED',revision_number:1,revision_of_document_id:null,is_current:true,imported_at:'2026-10-23'});
const changed=vi.fn();
beforeEach(()=>{vi.restoreAllMocks();changed.mockClear();vi.spyOn(window,'confirm').mockReturnValue(true);});
async function queue(files:File[]){const user=userEvent.setup();render(<DocumentImports apiUrl="/api" tenderId="t" documents={[doc('A.pdf','a'),doc('B.pdf','b')]} onImported={changed}/>);await user.upload(screen.getByLabelText('Archivos del expediente'),files);return user;}
it('UIR3-18/19/20: stable local identities correlate two conflicts resolved B then A with exact File/target',async()=>{
 const a=new File(['AAAA'],'A.pdf'),b=new File(['BBBB'],'B.pdf');const spy=vi.spyOn(tendersApi,'import').mockImplementation(async(_base,_t,file,action)=>({filename:file.name,status:action==='NONE'?'NAME_CONFLICT':'IMPORTED',document_id:file===a?'a':'b'}));
 const user=await queue([a,b]);expect(spy).not.toHaveBeenCalled();const ids=Array.from(document.querySelectorAll('[data-import-id]')).map(e=>e.getAttribute('data-import-id'));expect(new Set(ids).size).toBe(2);
 await user.click(screen.getByText('Importar archivos seleccionados'));await screen.findByLabelText('Decisión para B.pdf');
 await user.selectOptions(screen.getByLabelText('Decisión para B.pdf'),'NEW_REVISION');await user.selectOptions(screen.getByLabelText('Revisión actual para B.pdf'),'b');
 await user.click(within(screen.getByLabelText('Decisión para B.pdf').closest('li')!).getByText('Confirmar decisión'));await waitFor(()=>expect(spy).toHaveBeenCalledWith('/api','t',b,'NEW_REVISION','b'));
 await user.selectOptions(screen.getByLabelText('Decisión para A.pdf'),'IMPORT_INDEPENDENT');await user.click(within(screen.getByLabelText('Decisión para A.pdf').closest('li')!).getByText('Confirmar decisión'));
 await waitFor(()=>expect(spy).toHaveBeenCalledWith('/api','t',a,'IMPORT_INDEPENDENT',''));expect(Array.from(document.querySelectorAll('[data-import-id]')).map(e=>e.getAttribute('data-import-id'))).toEqual(ids);
});
it('UIR3-21: cancelling A leaves B conflict and bytes untouched',async()=>{
 const a=new File(['a'],'A.pdf'),b=new File(['b'],'B.pdf');const spy=vi.spyOn(tendersApi,'import').mockImplementation(async(_base,_t,file)=>({filename:file.name,status:'NAME_CONFLICT',document_id:'x'}));const user=await queue([a,b]);await user.click(screen.getByText('Importar archivos seleccionados'));await screen.findByLabelText('Decisión para B.pdf');await user.click(within(screen.getByLabelText('Decisión para A.pdf').closest('li')!).getByText('Cancelar'));expect(screen.getByLabelText('Decisión para B.pdf')).toHaveValue('');expect(spy).toHaveBeenCalledTimes(2);
});
it('UIR3-22: uncertain retry retains original identity/File and no automatic retry',async()=>{
 const a=new File(['a'],'A.pdf');const spy=vi.spyOn(tendersApi,'import').mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce({filename:'A.pdf',status:'DUPLICATE',document_id:'a'});const user=await queue([a]);const id=document.querySelector('[data-import-id]')?.getAttribute('data-import-id');await user.click(screen.getByText('Importar archivos seleccionados'));await user.click(await screen.findByText('Reintentar importación'));expect(spy).toHaveBeenNthCalledWith(2,'/api','t',a,'NONE',undefined);expect(document.querySelector('[data-import-id]')).toHaveAttribute('data-import-id',id);expect(await screen.findByText('Contenido idéntico ya registrado')).toBeVisible();
});
it('UIR3-15: duplicate has no revision action',async()=>{vi.spyOn(tendersApi,'import').mockResolvedValue({filename:'A.pdf',status:'DUPLICATE',document_id:'a'});const user=await queue([new File(['a'],'A.pdf')]);await user.click(screen.getByText('Importar archivos seleccionados'));await screen.findByText('Contenido idéntico ya registrado');expect(screen.queryByText('Confirmar decisión')).not.toBeInTheDocument();});
it('rejecting human confirmation does not persist a conflict decision',async()=>{const spy=vi.spyOn(tendersApi,'import').mockResolvedValue({filename:'A.pdf',status:'NAME_CONFLICT',document_id:'a'});const user=await queue([new File(['a'],'A.pdf')]);await user.click(screen.getByText('Importar archivos seleccionados'));await user.selectOptions(await screen.findByLabelText('Decisión para A.pdf'),'IMPORT_INDEPENDENT');vi.mocked(window.confirm).mockReturnValue(false);await user.click(screen.getByText('Confirmar decisión'));expect(spy).toHaveBeenCalledTimes(1);});
it('pending import prevents changing Tender when abandonment is declined',async()=>{vi.spyOn(tendersApi,'import');await queue([new File(['a'],'A.pdf')]);vi.mocked(window.confirm).mockReturnValue(false);const event=new CustomEvent('tuscope:navigate',{cancelable:true,detail:{tenderId:'other'}});fireEvent(window,event);expect(event.defaultPrevented).toBe(true);});
