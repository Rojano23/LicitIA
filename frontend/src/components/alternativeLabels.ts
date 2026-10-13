import type { AlternativeLifecycle } from "../api/technicalAlternatives";
import type { ComplianceStatus, EvaluationApplicability } from "../api/alternativeCompliance";

export const lifecycleLabels: Record<AlternativeLifecycle, string> = { DRAFT: "Borrador", ACTIVE: "Activa", ARCHIVED: "Archivada" };
export const complianceLabels: Record<ComplianceStatus | "STALE", string> = {
  COMPLIANT: "Cumple", PARTIAL: "Cumplimiento parcial", NON_COMPLIANT: "No cumple",
  REVIEW_REQUIRED: "Requiere revisión", NOT_EVALUATED: "Sin evaluar", STALE: "Evaluación desactualizada",
};
export const applicabilityLabels: Record<EvaluationApplicability, string> = {
  CURRENT: "Vigente", STALE_ALTERNATIVE: "Alternativa modificada",
  STALE_SCOPE: "Alcance contractual modificado", STALE_BOTH: "Alternativa y alcance modificados",
};
export const staleExplanations: Record<Exclude<EvaluationApplicability, "CURRENT">, string> = {
  STALE_ALTERNATIVE: "La alternativa cambió después de esta evaluación.",
  STALE_SCOPE: "El alcance contractual cambió después de esta evaluación.",
  STALE_BOTH: "La alternativa y el alcance cambiaron después de esta evaluación.",
};
export const scopeStateLabels: Record<string, string> = {
  NOT_REQUIRED: "Sin revisión requerida", PENDING: "Revisión de alcance pendiente",
  CONFIRMED: "Alcance confirmado", CORRECTED: "Alcance corregido", REJECTED: "Alcance rechazado",
  STALE_REVIEW: "Revisión de alcance desactualizada", SOURCE_BLOCKED: "Fuente bloqueada",
  UNRESOLVED_SOURCE: "Fuente sin resolver", NO_REVIEW: "Sin revisión humana",
  CURRENT: "Revisión humana vigente", STALE: "Revisión humana desactualizada", UNKNOWN: "Revisión no disponible",
  EFFECTIVE: "Fuente efectiva", EFFECTIVE_WITH_OVERLAY: "Fuente efectiva con modificaciones",
  REVIEW_REQUIRED: "Fuente requiere revisión", SUPERSEDED: "Fuente sustituida", REVOKED: "Fuente revocada",
};
export function dateLabel(value: string): string { return new Date(value).toLocaleString("es-MX"); }
