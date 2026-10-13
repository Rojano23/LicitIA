import axios from "axios";

export type AlternativeLifecycle = "DRAFT" | "ACTIVE" | "ARCHIVED";
export type AlternativeContent = {
  name: string;
  technical_description: string;
  assumptions: string | null;
  notes: string | null;
  lifecycle_state: AlternativeLifecycle;
};
export type AlternativeRevision = AlternativeContent & {
  id: string; alternative_id: string; tender_id: string; revision: number;
  fingerprint: string; created_at: string;
};
export type TechnicalAlternative = {
  id: string; tender_id: string; created_at: string;
  revisions: AlternativeRevision[]; current_revision: AlternativeRevision;
};
export type AlternativeAppend = AlternativeContent & { expected_current_revision: number };

export function technicalAlternativesApi(apiUrl: string, tenderId: string) {
  const base = `${apiUrl}/tenders/${encodeURIComponent(tenderId)}/technical-alternatives`;
  return {
    async list(): Promise<TechnicalAlternative[]> { return (await axios.get<TechnicalAlternative[]>(base)).data; },
    async detail(id: string): Promise<TechnicalAlternative> {
      return (await axios.get<TechnicalAlternative>(`${base}/${encodeURIComponent(id)}`)).data;
    },
    async create(payload: AlternativeContent): Promise<TechnicalAlternative> {
      return (await axios.post<TechnicalAlternative>(base, payload)).data;
    },
    async append(id: string, payload: AlternativeAppend): Promise<TechnicalAlternative> {
      return (await axios.post<TechnicalAlternative>(`${base}/${encodeURIComponent(id)}/revisions`, payload)).data;
    },
  };
}

export function alternativeRequestError(error: unknown): { status?: number; code?: string } {
  if (!axios.isAxiosError<{ detail?: { code?: string } }>(error)) return {};
  return { status: error.response?.status, code: error.response?.data?.detail?.code };
}
export function alternativeMutationMessage(error: unknown): string {
  const failure = alternativeRequestError(error);
  if (failure.status === 409) {
    const messages: Record<string, string> = {
      ALTERNATIVE_REVISION_CONFLICT: "Ya existe otra revisión de la alternativa. Se actualizará la información.",
      ALTERNATIVE_FINGERPRINT_STALE: "La alternativa cambió. Se actualizará antes de continuar.",
      SCOPE_SNAPSHOT_STALE: "El alcance contractual cambió. Se actualizará antes de iniciar otra evaluación.",
      COMPLIANCE_EVALUATION_STALE: "La evaluación ya no está vigente. Se conservará su historial y se actualizará la información.",
      COMPLIANCE_DECISION_REVISION_CONFLICT: "Esta obligación fue evaluada en otra sesión. Se cargará la decisión más reciente.",
      ALTERNATIVE_ARCHIVED: "La alternativa está archivada y no puede iniciar una evaluación nueva.",
      ALTERNATIVE_CONCURRENT_CHANGE: "Hubo un cambio simultáneo. Actualiza la información antes de volver a guardar.",
      SCOPE_CONTEXT_UNFLUSHED: "El contexto contractual aún tiene cambios pendientes. Actualiza antes de continuar.",
    };
    return messages[failure.code ?? ""] ?? "La información cambió. Se actualizará antes de continuar.";
  }
  return failure.status === 422 ? "Revisa los campos del formulario; el servidor no aceptó la información."
    : failure.status === 404 ? "El registro ya no está disponible. Se actualizará la información."
    : "No se pudo confirmar el guardado. Revisa el historial actualizado antes de volver a guardar.";
}
