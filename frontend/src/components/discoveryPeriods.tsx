export type Period='all'|'7'|'30'|'60'|'90'|'month'|'previous'|'custom';
export type DateRange={from:string;to:string};
const dateString=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
export function resolvePeriod(period:Period,today=new Date()):DateRange{
 const end=new Date(today.getFullYear(),today.getMonth(),today.getDate());
 if(period==='all'||period==='custom')return {from:'',to:''};
 let start=new Date(end);
 if(period==='previous'){start=new Date(end.getFullYear(),end.getMonth()-1,1);end.setDate(0);}
 else if(period==='month')start.setDate(1);
 else start.setDate(start.getDate()-Number(period)+1);
 return {from:dateString(start),to:dateString(end)};
}
export function PeriodFilter({label,value,from,to,onChange,allowAll=false}:{label:string;value:Period;from:string;to:string;onChange:(period:Period,range:DateRange)=>void;allowAll?:boolean}){
 return <div className="discovery-period"><label>{label}<select value={value} onChange={e=>{const period=e.target.value as Period;onChange(period,period==='custom'?{from,to}:resolvePeriod(period));}}>{allowAll&&<option value="all">Todos</option>}{(['7','30','60','90'] as const).map(v=><option key={v} value={v}>Últimos {v} días</option>)}<option value="month">Este mes</option><option value="previous">Mes anterior</option><option value="custom">Personalizado</option></select></label>{value==='custom'&&<><label>Desde<input aria-label={`${label}: Desde`} type="date" value={from} onChange={e=>onChange(value,{from:e.target.value,to})}/></label><label>Hasta<input aria-label={`${label}: Hasta`} type="date" value={to} onChange={e=>onChange(value,{from,to:e.target.value})}/></label></>}<small>{from||to?`${from||'Sin inicio'} — ${to||'Sin fin'}`:'Sin límite de publicación'}</small></div>;
}
