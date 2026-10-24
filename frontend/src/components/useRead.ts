import {useEffect,useRef,useState} from 'react';
/** A result can only be consumed by the context which requested it. */
export function useRead<T>(key:string,read:()=>Promise<T>){
 const reader=useRef(read);reader.current=read;
 const [attempt,setAttempt]=useState(0),[state,setState]=useState<{key:string;value?:T;loading:boolean;error:boolean}>({key,loading:true,error:false});
 const generation=useRef(0);
 useEffect(()=>{let live=true;const n=++generation.current;setState({key,loading:true,error:false});void reader.current().then(value=>{if(live&&n===generation.current)setState({key,value,loading:false,error:false});}).catch(()=>{if(live&&n===generation.current)setState({key,loading:false,error:true});});return()=>{live=false;generation.current++;};},[key,attempt]);
 return {...(state.key===key?state:{loading:true,error:false,value:undefined}),refresh:()=>setAttempt(n=>n+1)};
}
