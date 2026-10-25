import {SearchProfiles} from './SearchProfiles';
import {useEffect,useState} from 'react';
import {discoveryApi,type Source} from '../api/discovery';
import {useRead} from './useRead';
import {Button,ErrorState,LoadingState,Notice,TableShell} from '../ui/primitives';
import './supportProduct.css';
export const restrictedSource=(s:Source)=>s.id==='COMPRAS_MX'||s.capabilities?.automation_status==='RESTRICTED'||s.capabilities?.automation_status==='DEFERRED_SOURCE_AUTOMATION_RESTRICTED';
export function SettingsView({apiUrl,embedded=false,focusProfiles=false,focusSources=false}:{apiUrl:string;embedded?:boolean;focusProfiles?:boolean;focusSources?:boolean}){
 const sources=useRead('settings-sources',()=>discoveryApi.sources(apiUrl));const [selected,setSelected]=useState(''),[editingBusy,setEditingBusy]=useState(false),[saved,setSaved]=useState('');const source=sources.value?.find(s=>s.id===selected);
 useEffect(()=>{if(focusSources){const el=document.getElementById('source-settings');el?.focus();el?.scrollIntoView?.({block:'start'});}},[focusSources]);
 return <section className="support-product" aria-label="Configuración">{!embedded&&<h2>Configuración</h2>}<p>Preferencias y fuentes de consulta soportadas. Los documentos se administran localmente; consultar Discovery solicita información a portales públicos externos.</p><Notice>Abrir esta pantalla no consulta portales externos ni envía información a servicios externos.</Notice>
 <h3 id="source-settings" tabIndex={-1}>Fuentes Discovery</h3><Button disabled={editingBusy} onClick={sources.refresh}>Actualizar configuración de fuentes</Button>{sources.loading&&<LoadingState/>}{sources.error&&<ErrorState retry={sources.refresh}>No se pudieron consultar las fuentes.</ErrorState>}
 <TableShell label="Fuentes configuradas"><table><thead><tr><th>Fuente</th><th>Capacidad / estado local</th><th>Acción</th></tr></thead><tbody>{sources.value?.map(s=><tr key={s.id}><td>{s.name}</td><td>{restrictedSource(s)?'Automatización no disponible actualmente':s.enabled?'Habilitada para consulta manual':'Deshabilitada localmente'}</td><td>{!restrictedSource(s)&&<Button disabled={editingBusy} onClick={()=>{setSelected(s.id);setSaved('');}}>Configurar {s.name}</Button>}</td></tr>)}</tbody></table></TableShell><p>La habilitación local no certifica disponibilidad del portal. Compras MX permanece restringido, sin consulta ejecutable ni sustitución de fuente.</p>
 {saved&&<p role="status">Configuración de {saved} guardada; no se ejecutó una consulta pública.</p>}
 {source&&!restrictedSource(source)&&<SourceSettings key={source.id+JSON.stringify(source.configuration)+source.enabled} source={source} apiUrl={apiUrl} onBusy={setEditingBusy} refresh={()=>{setSaved(source.name);sources.refresh();}}/>}
 <SearchProfiles apiUrl={apiUrl} focus={focusProfiles} availableSources={sources.value??[]}/>
 <h3>Presentación local</h3><p>Contrae o expande el menú lateral para guardar la preferencia en este navegador. No cambia los datos del expediente.</p>
 <details><summary>Administración local</summary><p>Almacenamiento, respaldos, conexión DB y configuración de proveedores siguen el procedimiento de instalación local del administrador. No hay un editor de variables de entorno ni rutas habilitado en Product UI.</p></details><a href="#/configuracion/diagnostico">Abrir Diagnóstico</a>
 </section>;
}
function SourceSettings({source,apiUrl,refresh,onBusy}:{source:Source;apiUrl:string;refresh:()=>void;onBusy:(value:boolean)=>void}){
 const [enabled,setEnabled]=useState(source.enabled),[areas,setAreas]=useState(source.configuration.areas),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 async function save(){if(restrictedSource(source)||busy)return;setBusy(true);onBusy(true);setError(false);try{await discoveryApi.configure(apiUrl,source.id,{enabled,areas});refresh();}catch{setError(true);}finally{setBusy(false);onBusy(false);}}
 return <aside className="support-detail"><h3>{source.name}</h3><fieldset disabled={busy}><legend>Configuración local de fuente</legend><label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Habilitar consulta manual</label>{source.areas.map(a=><label key={a.key}><input type="checkbox" checked={areas.includes(a.key)} onChange={e=>setAreas(e.target.checked?[...areas,a.key]:areas.filter(v=>v!==a.key))}/>{a.label}</label>)}<Button onClick={()=>void save()}>Guardar configuración de fuente</Button></fieldset>{error&&<ErrorState>No se pudo guardar. Consulta el estado actual antes de repetir.</ErrorState>}</aside>;
}
