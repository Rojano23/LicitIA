import {useId,type ReactNode} from 'react';
export function DiscoveryHelp({name,children}:{name:string;children:ReactNode}){
 const id=useId();return <details className="discovery-help"><summary aria-label={`Ayuda: ${name}`} aria-controls={id}>?</summary><p id={id}>{children}</p></details>;
}
// Examples verified against persisted public PEMEX values and the accepted CFE adapter/fixture.
// Text inputs intentionally avoid presenting these examples as an exhaustive source catalog.
export function filterHelp(source:string,field:'event'|'supply',acquisition=false){
 if(field==='event'){
  const pemex='PEMEX: Nacional, Internacional o Internacional bajo TLC.';
  const cfe=acquisition?'CFE admite Concurso abierto, Concurso simplificado o Adjudicación directa.':'CFE: por ejemplo, Concurso abierto.';
  return `${source==='CFE'?cfe:source==='PEMEX'?pemex:`${pemex} ${cfe}`} Es opcional; usa el texto que informa la fuente.`;
 }
 return `${source==='CFE'?'CFE: por ejemplo, Adquisición por Abastecimientos.':source==='PEMEX'?'PEMEX: Bienes, Servicios, Obra pública o Arrendamientos.':'PEMEX: Bienes, Servicios, Obra pública o Arrendamientos. CFE: por ejemplo, Adquisición por Abastecimientos.'} Es opcional; usa el texto que informa la fuente.`;
}
