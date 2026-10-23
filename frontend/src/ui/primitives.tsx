import type { ButtonHTMLAttributes, ReactNode } from 'react';
export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';
export function Button({ variant = 'secondary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'destructive' }) {
  return <button {...props} className={`ui-button ui-button--${variant} ${className}`} />;
}
export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`ui-badge ui-tone--${tone}`}>{children}</span>;
}
export function SourceBadge({ name, restricted = false }: { name: string; restricted?: boolean }) {
  return <span className="ui-source"><strong>{name}</strong>{restricted && <StatusBadge>Automatización no disponible actualmente</StatusBadge>}</span>;
}
export function PageHeader({ title, context, action }: { title: string; context?: ReactNode; action?: ReactNode }) {
  return <header className="ui-page-header"><div><h1 tabIndex={-1} id="page-title">{title}</h1>{context && <div className="ui-page-context">{context}</div>}</div>{action}</header>;
}
export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: Tone }) {
  return <div className={`ui-notice ui-tone--${tone}`}>{children}</div>;
}
export function EmptyState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <section className="ui-state"><h2>{title}</h2><p>{children}</p>{action}</section>;
}
export function LoadingState({ children = 'Consultando información…' }: { children?: ReactNode }) {
  return <p role="status" className="ui-state">{children}</p>;
}
export function ErrorState({ children = 'No se pudo consultar la información. Verifica la conexión local e intenta de nuevo.', retry }: { children?: ReactNode; retry?: () => void }) {
  return <div role="alert" className="ui-state ui-tone--danger"><p>{children}</p>{retry && <Button onClick={retry}>Volver a consultar</Button>}</div>;
}
export function SummarySurface({ children }: { children: ReactNode }) { return <section className="ui-surface">{children}</section>; }
export function TableShell({ label, children, loading = false, empty = false }: { label: string; children: ReactNode; loading?: boolean; empty?: boolean }) {
  return <section aria-label={label}>{loading ? <LoadingState /> : empty ? <EmptyState title="Sin registros">Ajusta los filtros o agrega información para continuar.</EmptyState> : <div role="region" aria-label={label} tabIndex={0} className="ui-table-shell">{children}</div>}</section>;
}
