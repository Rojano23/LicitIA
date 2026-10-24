import {Component, lazy, Suspense, type ComponentProps, type ReactNode} from 'react';
import type Workspace from '../App';
import {ErrorState, LoadingState} from './primitives';
const loadWorkspace=()=>import('../App');
/** Only the explicitly opened diagnostic tools are deferred. Existing route/state ownership stays intact. */
export class WorkspaceLoadBoundary extends Component<{children:ReactNode;retry:()=>void},{failed:boolean}> {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){return this.state.failed?<ErrorState retry={()=>{this.setState({failed:false});this.props.retry();}}>No se pudieron abrir las herramientas de diagnóstico. Puedes volver a intentar sin salir de la licitación.</ErrorState>:this.props.children;}
}
const initial=lazy(loadWorkspace);
export class DeferredWorkspace extends Component<NonNullable<ComponentProps<typeof Workspace>>,{view:typeof initial}> {
 state={view:initial};
 render(){const View=this.state.view;return <WorkspaceLoadBoundary retry={()=>this.setState({view:lazy(loadWorkspace)})}><Suspense fallback={<LoadingState>Abriendo herramientas de diagnóstico…</LoadingState>}><View {...this.props}/></Suspense></WorkspaceLoadBoundary>;}
}
