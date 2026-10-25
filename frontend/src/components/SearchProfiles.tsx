import {useEffect,useRef,useState} from 'react';
import {discoveryApi,type Source,type Profile} from '../api/discovery';
import {Button} from '../ui/primitives';
export function SearchProfiles({apiUrl,focus=false,availableSources}:{apiUrl:string;focus?:boolean;availableSources?:Source[]}){
 const [sources,setSources]=useState<Source[]>([]),[profiles,setProfiles]=useState<Profile[]>([]),[profileId,setProfile]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState('');const mounted=useRef(true);
 const [name,setName]=useState(''),[include,setInclude]=useState(''),[exclude,setExclude]=useState(''),[synonyms,setSynonyms]=useState('');
 const [profileAreas,setProfileAreas]=useState(''),[profileSources,setProfileSources]=useState<string[]>([]);
 const [active,setActive]=useState(true);

 async function refresh(){const [s,p]=await Promise.all([availableSources?Promise.resolve(availableSources):discoveryApi.sources(apiUrl),discoveryApi.profiles(apiUrl)]);if(mounted.current){setSources(s);setProfiles(p);}}
 async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();}catch{if(mounted.current)setError('No se pudo guardar o consultar el perfil. Revisa los datos y vuelve a consultar antes de repetir.');}finally{if(mounted.current)setBusy(false);}}
 useEffect(()=>{mounted.current=true;void run(refresh);return()=>{mounted.current=false;};},[apiUrl]);
 useEffect(()=>{if(availableSources)setSources(availableSources);},[availableSources]);
 useEffect(()=>{if(focus){const el=document.getElementById('search-profiles');el?.focus();el?.scrollIntoView?.({block:'start'});}},[focus]);
 function chooseProfile(id:string){setProfile(id);const p=profiles.find(p=>p.id===id);setName(p?.name??'');setInclude(p?.include_keywords.join('\n')??'');setExclude(p?.exclude_keywords.join('\n')??'');setSynonyms(Object.entries(p?.synonyms??{}).map(([key,values])=>`${key}=${values.join('|')}`).join('\n'));setActive(p?.active??true);setProfileSources(p?.source_ids??[]);setProfileAreas(p?.business_areas.join('\n')??'');}
 return <><p>Las reglas se evalúan en este equipo; tu perfil no se envía al portal.</p> <section id="search-profiles" tabIndex={-1} aria-label="Perfiles de búsqueda"><h3>Perfiles de búsqueda</h3> <fieldset disabled={busy}><legend>Reglas del perfil</legend>
 <label>Editar perfil<select value={profileId} onChange={e=>chooseProfile(e.target.value)}><option value="">Sin perfil / nuevo</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}{p.active?'':' (inactivo)'}</option>)}</select></label>
 <label>Nombre del perfil<input value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Incluir cualquiera de estos términos (uno por línea)<textarea value={include} onChange={e=>setInclude(e.target.value)}/></label>
 <label>Excluir (precedencia sobre incluir)<textarea value={exclude} onChange={e=>setExclude(e.target.value)}/></label>
 <label>Sinónimos (PLC=controlador lógico programable|otro)<textarea value={synonyms} onChange={e=>setSynonyms(e.target.value)}/></label>
 <label><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Perfil activo</label>
 <p>Fuentes del perfil: sin selección incluye todas.</p>{sources.map(s=><label key={s.id}><input type="checkbox" checked={profileSources.includes(s.id)} onChange={e=>setProfileSources(e.target.checked?[...profileSources,s.id]:profileSources.filter(id=>id!==s.id))}/>Restringir perfil a {s.id}</label>)}
 <label>Áreas de negocio o empresas del perfil (una por línea)<textarea value={profileAreas} onChange={e=>setProfileAreas(e.target.value)}/></label>
 <Button disabled={!name.trim()} onClick={()=>void run(async()=>{
  const split=(s:string)=>s.split('\n').map(v=>v.trim()).filter(Boolean);const groups:Record<string,string[]>={};
  for(const line of split(synonyms)){const [term,...parts]=line.split('=');if(!term||parts.length!==1)throw new Error('Formato sinónimo');groups[term.trim()]=parts[0].split('|').map(t=>t.trim());}
  const saved=await discoveryApi.saveProfile(apiUrl,{name,include_keywords:split(include),exclude_keywords:split(exclude),synonyms:groups,source_ids:profileSources,business_areas:split(profileAreas),active},profileId||undefined,profiles.find(p=>p.id===profileId)?.revision);
  await refresh();if(mounted.current)setProfile(saved.id);window.dispatchEvent(new Event("discovery-profiles-changed"));})}>Guardar perfil</Button>
 </fieldset>
</section>
{error&&<p role="alert">{error}</p>}<Button disabled={busy} onClick={()=>void run(refresh)}>Actualizar perfiles</Button></>;
}
