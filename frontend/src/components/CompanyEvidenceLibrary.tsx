import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import axios from "axios";

type Company = {
  id: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

type CompanyDocument = {
  id: string;
  company_id: string;
  original_filename: string;
  source_relative_path: string | null;
  stored_relative_path: string;
  mime_type: string | null;
  file_size_bytes: number;
  sha256: string;
  status: string;
  document_type: string | null;
  label: string | null;
  issuer: string | null;
  issue_date: string | null;
  expiration_date: string | null;
  metadata_note: string | null;
  archived_at: string | null;
  revision_of_document_id: string | null;
  conflict_resolution_action: string | null;
  revision_number: number;
  is_current: boolean;
  imported_at: string;
  updated_at: string;
};

type CompanyImportResult = {
  filename: string;
  source_relative_path: string | null;
  status: string;
  message: string | null;
  document_id: string | null;
  stored_relative_path: string | null;
  sha256: string | null;
  revision_of_document_id: string | null;
  conflict_resolution_action: string | null;
  revision_number: number | null;
  is_current: boolean | null;
};

type PendingConflict = {
  file: File;
  filename: string;
  sourceRelativePath: string | null;
  candidates: CompanyDocument[];
};

type Props = {
  apiUrl: string;
};

const SELECTED_COMPANY_STORAGE_KEY = "licitia_selected_company_id";

export function CompanyEvidenceLibrary({ apiUrl }: Props) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);
  const [companyDocuments, setCompanyDocuments] = useState<CompanyDocument[]>([]);
  const [companyName, setCompanyName] = useState("");
  const [companyLegalName, setCompanyLegalName] = useState("");
  const [companyTaxId, setCompanyTaxId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingCompanies, setLoadingCompanies] = useState(false);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [importing, setImporting] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [importResults, setImportResults] = useState<CompanyImportResult[]>([]);
  const [pendingConflict, setPendingConflict] = useState<PendingConflict | null>(null);
  const [selectedRevisionTargetId, setSelectedRevisionTargetId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  const [editDocumentType, setEditDocumentType] = useState("");
  const [editLabel, setEditLabel] = useState("");
  const [editIssuer, setEditIssuer] = useState("");
  const [editIssueDate, setEditIssueDate] = useState("");
  const [editExpirationDate, setEditExpirationDate] = useState("");
  const [editNote, setEditNote] = useState("");

  const selectedDocument = useMemo(
    () => companyDocuments.find((item) => item.id === selectedDocumentId) ?? null,
    [companyDocuments, selectedDocumentId],
  );

  const loadCompanies = async () => {
    setLoadingCompanies(true);
    try {
      const response = await axios.get<Company[]>(`${apiUrl}/companies`);
      setCompanies(response.data);

      const storedId = window.localStorage.getItem(SELECTED_COMPANY_STORAGE_KEY);
      if (storedId && response.data.some((company) => company.id === storedId)) {
        setSelectedCompanyId(storedId);
      } else if (response.data[0]) {
        setSelectedCompanyId(response.data[0].id);
        window.localStorage.setItem(SELECTED_COMPANY_STORAGE_KEY, response.data[0].id);
      } else {
        setSelectedCompanyId(null);
        window.localStorage.removeItem(SELECTED_COMPANY_STORAGE_KEY);
      }
    } catch (err) {
      setError("No fue posible cargar empresas.");
    } finally {
      setLoadingCompanies(false);
    }
  };

  const loadCompanyDocuments = async (companyId: string, includeArchivedItems: boolean) => {
    setLoadingDocuments(true);
    try {
      const response = await axios.get<CompanyDocument[]>(`${apiUrl}/companies/${companyId}/documents`, {
        params: { include_archived: includeArchivedItems },
      });
      setCompanyDocuments(response.data);
    } catch (err) {
      setCompanyDocuments([]);
      setError("No fue posible cargar la biblioteca documental de la empresa.");
    } finally {
      setLoadingDocuments(false);
    }
  };

  useEffect(() => {
    void loadCompanies();
  }, []);

  useEffect(() => {
    if (!selectedCompanyId) {
      setCompanyDocuments([]);
      setSelectedDocumentId("");
      return;
    }
    void loadCompanyDocuments(selectedCompanyId, includeArchived);
  }, [selectedCompanyId, includeArchived]);

  useEffect(() => {
    if (!selectedDocument) {
      setEditDocumentType("");
      setEditLabel("");
      setEditIssuer("");
      setEditIssueDate("");
      setEditExpirationDate("");
      setEditNote("");
      return;
    }
    setEditDocumentType(selectedDocument.document_type ?? "");
    setEditLabel(selectedDocument.label ?? "");
    setEditIssuer(selectedDocument.issuer ?? "");
    setEditIssueDate(selectedDocument.issue_date ?? "");
    setEditExpirationDate(selectedDocument.expiration_date ?? "");
    setEditNote(selectedDocument.metadata_note ?? "");
  }, [selectedDocument]);

  const handleSelectCompany = (companyId: string) => {
    setSelectedCompanyId(companyId);
    window.localStorage.setItem(SELECTED_COMPANY_STORAGE_KEY, companyId);
    setSelectedDocumentId("");
    setPendingConflict(null);
    setSelectedRevisionTargetId("");
  };

  const handleCreateCompany = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!companyName.trim()) {
      setError("El nombre de empresa es obligatorio.");
      return;
    }

    try {
      const response = await axios.post<Company>(`${apiUrl}/companies`, {
        name: companyName.trim(),
        legal_name: companyLegalName.trim() || null,
        tax_id: companyTaxId.trim() || null,
      });
      setCompanyName("");
      setCompanyLegalName("");
      setCompanyTaxId("");
      await loadCompanies();
      handleSelectCompany(response.data.id);
    } catch (err) {
      setError("No fue posible crear la empresa.");
    }
  };

  const handleImportDocuments = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!selectedCompanyId) {
      setError("Selecciona una empresa antes de importar documentos.");
      return;
    }

    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length === 0) {
      return;
    }

    setImporting(true);
    setError(null);

    try {
      const formData = new FormData();
      const relativePaths: string[] = [];

      selectedFiles.forEach((file) => {
        const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || "";
        formData.append("files", file);
        relativePaths.push(relativePath);
      });
      relativePaths.forEach((relativePath) => formData.append("source_relative_paths", relativePath));

      const response = await axios.post<CompanyImportResult[]>(`${apiUrl}/companies/${selectedCompanyId}/documents/import`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setImportResults(response.data);

      const conflicts = response.data.filter((item) => item.status === "NAME_CONFLICT");
      if (conflicts.length > 0 && selectedFiles[0]) {
        const conflictFilename = conflicts[0].filename;
        const conflictCandidates = companyDocuments.filter((doc) => doc.original_filename === conflictFilename && doc.is_current);
        setPendingConflict({
          file: selectedFiles[0],
          filename: conflictFilename,
          sourceRelativePath: relativePaths[0] || null,
          candidates: conflictCandidates,
        });
        if (conflictCandidates[0]) {
          setSelectedRevisionTargetId(conflictCandidates[0].id);
        }
      }

      await loadCompanyDocuments(selectedCompanyId, includeArchived);
    } catch (err) {
      setError("No fue posible importar documentos de empresa.");
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const resolveConflict = async (action: "NEW_DOCUMENT" | "NEW_REVISION") => {
    if (!selectedCompanyId || !pendingConflict) {
      return;
    }

    const formData = new FormData();
    formData.append("files", pendingConflict.file);
    if (pendingConflict.sourceRelativePath) {
      formData.append("source_relative_paths", pendingConflict.sourceRelativePath);
    }
    formData.append("conflict_action", action);
    if (action === "NEW_REVISION") {
      if (!selectedRevisionTargetId) {
        setError("Selecciona un documento vigente para crear revisión.");
        return;
      }
      formData.append("revision_of_document_id", selectedRevisionTargetId);
    }

    setImporting(true);
    setError(null);
    try {
      const response = await axios.post<CompanyImportResult[]>(`${apiUrl}/companies/${selectedCompanyId}/documents/import`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportResults(response.data);
      setPendingConflict(null);
      setSelectedRevisionTargetId("");
      await loadCompanyDocuments(selectedCompanyId, includeArchived);
    } catch (err) {
      setError("No fue posible resolver el conflicto de nombre.");
    } finally {
      setImporting(false);
    }
  };

  const saveDocumentMetadata = async () => {
    if (!selectedCompanyId || !selectedDocumentId) {
      return;
    }

    try {
      await axios.patch(`${apiUrl}/companies/${selectedCompanyId}/documents/${selectedDocumentId}`, {
        document_type: editDocumentType || null,
        label: editLabel || null,
        issuer: editIssuer || null,
        issue_date: editIssueDate || null,
        expiration_date: editExpirationDate || null,
        metadata_note: editNote || null,
      });
      await loadCompanyDocuments(selectedCompanyId, includeArchived);
    } catch (err) {
      setError("No fue posible guardar metadatos del documento.");
    }
  };

  const toggleArchiveDocument = async (document: CompanyDocument) => {
    if (!selectedCompanyId) {
      return;
    }

    try {
      await axios.patch(`${apiUrl}/companies/${selectedCompanyId}/documents/${document.id}/archive`, {
        archived: document.archived_at === null,
      });
      await loadCompanyDocuments(selectedCompanyId, includeArchived);
      if (selectedDocumentId === document.id && document.archived_at === null && !includeArchived) {
        setSelectedDocumentId("");
      }
    } catch (err) {
      setError("No fue posible actualizar estado archivado del documento.");
    }
  };

  const openDocumentInViewer = (document: CompanyDocument) => {
    if (!selectedCompanyId) {
      return;
    }
    window.open(`${apiUrl}/companies/${selectedCompanyId}/documents/${document.id}/content`, "_blank", "noopener,noreferrer");
  };

  return (
    <section style={{ marginBottom: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
      <h2 style={{ marginTop: 0 }}>Biblioteca empresarial (MVP-05.1)</h2>
      <div style={{ fontSize: 13, color: "#52607a", marginBottom: 12 }}>
        Gestión de documentos corporativos desacoplada de licitación y requisitos. Sin evaluación de cumplimiento en esta etapa.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 20 }}>
        <div style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 12, background: "#f8fafc" }}>
          <h3 style={{ marginTop: 0 }}>Crear empresa</h3>
          <form onSubmit={handleCreateCompany} style={{ display: "grid", gap: 8 }}>
            <input value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="Nombre" style={{ padding: 9, borderRadius: 8, border: "1px solid #cfd8e3" }} />
            <input value={companyLegalName} onChange={(event) => setCompanyLegalName(event.target.value)} placeholder="Razón social" style={{ padding: 9, borderRadius: 8, border: "1px solid #cfd8e3" }} />
            <input value={companyTaxId} onChange={(event) => setCompanyTaxId(event.target.value)} placeholder="RFC" style={{ padding: 9, borderRadius: 8, border: "1px solid #cfd8e3" }} />
            <button type="submit" style={{ padding: "10px 12px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
              Crear empresa
            </button>
          </form>

          <h3 style={{ marginBottom: 8 }}>Empresas</h3>
          {loadingCompanies ? (
            <div style={{ fontSize: 12, color: "#52607a" }}>Cargando empresas...</div>
          ) : companies.length === 0 ? (
            <div style={{ fontSize: 12, color: "#52607a" }}>Sin empresas registradas.</div>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {companies.map((company) => {
                const active = selectedCompanyId === company.id;
                return (
                  <button
                    key={company.id}
                    type="button"
                    onClick={() => handleSelectCompany(company.id)}
                    style={{
                      textAlign: "left",
                      padding: 10,
                      borderRadius: 8,
                      border: active ? "2px solid #1b5bd8" : "1px solid #d9e1ec",
                      background: active ? "#edf4ff" : "#fff",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontWeight: 700 }}>{company.name}</div>
                    <div style={{ fontSize: 12, color: "#52607a" }}>{company.legal_name || "Sin razón social"}</div>
                    <div style={{ fontSize: 11, color: "#52607a" }}>RFC: {company.tax_id || "-"}</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 12, background: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h3 style={{ margin: 0 }}>Documentos de empresa</h3>
            <label style={{ fontSize: 12, color: "#334155", display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
              Incluir archivados
            </label>
          </div>

          <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <input type="file" multiple onChange={handleImportDocuments} disabled={!selectedCompanyId || importing} />
            <button
              type="button"
              onClick={() => selectedCompanyId && void loadCompanyDocuments(selectedCompanyId, includeArchived)}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}
              disabled={!selectedCompanyId}
            >
              Recargar
            </button>
          </div>

          {pendingConflict && (
            <div style={{ marginTop: 10, border: "1px solid #f59e0b", borderRadius: 8, padding: 10, background: "#fffbeb" }}>
              <div style={{ fontSize: 12, color: "#7c2d12" }}>
                Conflicto detectado para {pendingConflict.filename}. Elige si deseas importar como nuevo documento o como nueva revisión.
              </div>
              <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                <select value={selectedRevisionTargetId} onChange={(event) => setSelectedRevisionTargetId(event.target.value)} style={{ padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }}>
                  <option value="">Selecciona documento vigente para revisión</option>
                  {pendingConflict.candidates.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.original_filename} | rev {candidate.revision_number} | {candidate.id}
                    </option>
                  ))}
                </select>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button type="button" onClick={() => void resolveConflict("NEW_DOCUMENT")} disabled={importing} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                    Importar como NEW_DOCUMENT
                  </button>
                  <button type="button" onClick={() => void resolveConflict("NEW_REVISION")} disabled={importing} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700 }}>
                    Importar como NEW_REVISION
                  </button>
                </div>
              </div>
            </div>
          )}

          {importResults.length > 0 && (
            <div style={{ marginTop: 10, border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Resultados de importación</div>
              <div style={{ display: "grid", gap: 4 }}>
                {importResults.map((item, index) => (
                  <div key={`${item.filename}-${item.status}-${index}`} style={{ fontSize: 12, color: "#334155" }}>
                    {item.filename} • {item.status} {item.conflict_resolution_action ? `(${item.conflict_resolution_action})` : ""}
                  </div>
                ))}
              </div>
            </div>
          )}

          {loadingDocuments ? (
            <div style={{ marginTop: 10, fontSize: 12, color: "#52607a" }}>Cargando documentos...</div>
          ) : companyDocuments.length === 0 ? (
            <div style={{ marginTop: 10, fontSize: 12, color: "#52607a" }}>No hay documentos para la empresa seleccionada.</div>
          ) : (
            <div style={{ marginTop: 10, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#f8fafc" }}>
                    <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Archivo</th>
                    <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Tipo / Etiqueta</th>
                    <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Estado</th>
                    <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {companyDocuments.map((document) => (
                    <tr key={document.id}>
                      <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                        <button
                          type="button"
                          onClick={() => setSelectedDocumentId(document.id)}
                          style={{ border: "none", background: "transparent", padding: 0, color: "#1b5bd8", cursor: "pointer", fontWeight: 700 }}
                        >
                          {document.original_filename}
                        </button>
                        <div style={{ color: "#52607a" }}>rev {document.revision_number} • vigente: {document.is_current ? "sí" : "no"}</div>
                      </td>
                      <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{document.document_type || "-"} / {document.label || "-"}</td>
                      <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{document.status}</td>
                      <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          <button type="button" onClick={() => openDocumentInViewer(document)} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                            Ver
                          </button>
                          <button type="button" onClick={() => void toggleArchiveDocument(document)} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                            {document.archived_at ? "Restaurar" : "Archivar"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selectedDocument && (
            <div style={{ marginTop: 12, border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Editar metadatos</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
                <input value={editDocumentType} onChange={(event) => setEditDocumentType(event.target.value)} placeholder="document_type" style={{ padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }} />
                <input value={editLabel} onChange={(event) => setEditLabel(event.target.value)} placeholder="label" style={{ padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }} />
                <input value={editIssuer} onChange={(event) => setEditIssuer(event.target.value)} placeholder="issuer" style={{ padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }} />
                <input type="date" value={editIssueDate} onChange={(event) => setEditIssueDate(event.target.value)} style={{ padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }} />
                <input type="date" value={editExpirationDate} onChange={(event) => setEditExpirationDate(event.target.value)} style={{ padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }} />
              </div>
              <textarea value={editNote} onChange={(event) => setEditNote(event.target.value)} placeholder="nota" style={{ width: "100%", minHeight: 70, marginTop: 8, padding: 8, borderRadius: 8, border: "1px solid #cfd8e3" }} />
              <button type="button" onClick={() => void saveDocumentMetadata()} style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                Guardar metadatos
              </button>
            </div>
          )}

          {error && <div style={{ marginTop: 10, color: "crimson", fontSize: 13 }}>{error}</div>}
        </div>
      </div>
    </section>
  );
}
