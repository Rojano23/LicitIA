import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import axios from "axios";

type Tender = {
  id: string;
  title: string;
  institution_profile: string | null;
  external_reference: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

type TenderDocument = {
  id: string;
  tender_id: string;
  original_filename: string;
  source_relative_path: string | null;
  stored_relative_path: string;
  mime_type: string | null;
  file_size_bytes: number;
  sha256: string;
  status: string;
  processing_status?: string;
  page_count?: number;
  revision_of_document_id: string | null;
  revision_number: number;
  is_current: boolean;
  imported_at: string;
};

type DocumentPage = {
  id: string;
  document_id: string;
  page_number: number;
  text: string;
  char_count: number;
  extraction_method: string;
  status: string;
  extracted_at: string;
};

type ImportResult = {
  filename: string;
  source_relative_path: string | null;
  status: string;
  message: string | null;
  document_id: string | null;
  stored_relative_path: string | null;
  sha256: string | null;
  revision_of_document_id: string | null;
  revision_number: number | null;
  is_current: boolean | null;
};

type PendingConflict = {
  file: File;
  sourceRelativePath: string | null;
  filename: string;
  candidates: TenderDocument[];
};

const API_URL = "http://localhost:8000";
const SELECTED_TENDER_STORAGE_KEY = "licitia_selected_tender_id";

function App() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<TenderDocument[]>([]);
  const [title, setTitle] = useState("");
  const [institutionProfile, setInstitutionProfile] = useState("");
  const [externalReference, setExternalReference] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResults, setImportResults] = useState<ImportResult[]>([]);
  const [pendingConflict, setPendingConflict] = useState<PendingConflict | null>(null);
  const [selectedRevisionTargetId, setSelectedRevisionTargetId] = useState<string>("");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [documentPages, setDocumentPages] = useState<DocumentPage[]>([]);
  const [documentPagesLoading, setDocumentPagesLoading] = useState(false);
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(null);
  const documentRequestRef = useRef(0);

  const loadTenders = async () => {
    try {
      const response = await axios.get<Tender[]>(`${API_URL}/tenders`);
      setTenders(response.data);

      const storedTenderId = window.localStorage.getItem(SELECTED_TENDER_STORAGE_KEY);
      const isStoredTenderValid = storedTenderId && response.data.some((tender) => tender.id === storedTenderId);

      if (storedTenderId && isStoredTenderValid) {
        setSelectedTenderId(storedTenderId);
        return;
      }

      window.localStorage.removeItem(SELECTED_TENDER_STORAGE_KEY);
      setSelectedTenderId(null);
    } catch (err) {
      setError("Unable to load tenders from the backend.");
    }
  };

  const handleSelectTender = (tenderId: string) => {
    setSelectedTenderId(tenderId);
    window.localStorage.setItem(SELECTED_TENDER_STORAGE_KEY, tenderId);
  };

  const loadDocuments = async (tenderId: string) => {
    const requestId = ++documentRequestRef.current;
    setDocumentsLoading(true);
    setDocumentsError(null);

    try {
      const response = await axios.get<TenderDocument[]>(`${API_URL}/tenders/${tenderId}/documents`);

      if (requestId !== documentRequestRef.current) {
        return;
      }

      setDocuments(response.data);
    } catch (err) {
      if (requestId !== documentRequestRef.current) {
        return;
      }

      setDocuments([]);
      setDocumentsError("No fue posible cargar los documentos.");
    } finally {
      if (requestId === documentRequestRef.current) {
        setDocumentsLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadTenders();
  }, []);

  useEffect(() => {
    if (!selectedTenderId) {
      setDocuments([]);
      setDocumentsError(null);
      setDocumentsLoading(false);
      setSelectedDocumentId(null);
      return;
    }

    setSelectedDocumentId(null);
    void loadDocuments(selectedTenderId);
  }, [selectedTenderId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    if (!title.trim()) {
      setError("Tender title is required.");
      return;
    }

    setLoading(true);

    try {
      await axios.post(`${API_URL}/tenders`, {
        title: title.trim(),
        institution_profile: institutionProfile.trim() || null,
        external_reference: externalReference.trim() || null,
      });

      setTitle("");
      setInstitutionProfile("");
      setExternalReference("");
      await loadTenders();
    } catch (err) {
      setError("Unable to create the Tender.");
    } finally {
      setLoading(false);
    }
  };

  const resolveConflict = async (action: "IMPORT_INDEPENDENT" | "NEW_REVISION") => {
    if (!selectedTenderId || !pendingConflict) {
      return;
    }

    setImporting(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("files", pendingConflict.file);
      if (pendingConflict.sourceRelativePath) {
        formData.append("source_relative_paths", pendingConflict.sourceRelativePath);
      }
      formData.append("conflict_action", action);

      if (action === "NEW_REVISION") {
        if (!selectedRevisionTargetId) {
          setError("Debe seleccionar un documento actual para crear una revisión.");
          return;
        }
        formData.append("revision_of_document_id", selectedRevisionTargetId);
      }

      const response = await axios.post<ImportResult[]>(`${API_URL}/tenders/${selectedTenderId}/documents/import`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setImportResults(response.data);
      setPendingConflict(null);
      setSelectedRevisionTargetId("");
      await loadDocuments(selectedTenderId);
    } catch (err) {
      setError("No se pudo resolver el conflicto del documento.");
    } finally {
      setImporting(false);
    }
  };

  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!selectedTenderId) {
      setError("Select a Tender before importing documents.");
      return;
    }

    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length === 0) {
      return;
    }

    setImporting(true);
    setError("");

    try {
      const formData = new FormData();
      const relativePaths: string[] = [];

      selectedFiles.forEach((file) => {
        const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || "";
        formData.append("files", file);
        relativePaths.push(relativePath);
      });

      relativePaths.forEach((item) => formData.append("source_relative_paths", item));

      const response = await axios.post<ImportResult[]>(`${API_URL}/tenders/${selectedTenderId}/documents/import`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const conflicts = response.data.filter((result) => result.status === "NAME_CONFLICT");
      if (conflicts.length > 0 && selectedFiles.length > 0) {
        const conflictFile = selectedFiles[0];
        const candidates = documents.filter((document) => document.original_filename === conflicts[0].filename);
        setPendingConflict({
          file: conflictFile,
          sourceRelativePath: relativePaths[0] || null,
          filename: conflicts[0].filename,
          candidates,
        });
        if (candidates[0]) {
          setSelectedRevisionTargetId(candidates[0].id);
        }
      }

      setImportResults(response.data);
      await loadDocuments(selectedTenderId);
    } catch (err) {
      setError("Unable to import the selected documents.");
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) ?? null;
  const selectedDocumentUrl =
    selectedTenderId && selectedDocumentId ? `${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/content` : null;
  const selectedPage = documentPages.find((page) => page.page_number === selectedPageNumber) ?? null;

  const loadDocumentPages = async (tenderId: string, documentId: string) => {
    setDocumentPagesLoading(true);
    try {
      const response = await axios.get<DocumentPage[]>(`${API_URL}/tenders/${tenderId}/documents/${documentId}/pages`);
      setDocumentPages(response.data);
      setSelectedPageNumber(response.data[0]?.page_number ?? null);
    } catch (err) {
      setDocumentPages([]);
      setSelectedPageNumber(null);
    } finally {
      setDocumentPagesLoading(false);
    }
  };

  const handleExtractPdfText = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setDocumentPagesLoading(true);
    try {
      await axios.post(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/extract-pages`);
      await loadDocuments(selectedTenderId);
      await loadDocumentPages(selectedTenderId, selectedDocumentId);
    } catch (err) {
      setError("No se pudo extraer el texto del PDF.");
    } finally {
      setDocumentPagesLoading(false);
    }
  };

  const isPdfDocument = (document: TenderDocument | null) => {
    if (!document) {
      return false;
    }
    const mimeType = document.mime_type?.toLowerCase() ?? "";
    const filename = document.original_filename.toLowerCase();
    return mimeType.includes("pdf") || filename.endsWith(".pdf");
  };

  return (
    <div style={{ maxWidth: 1200, margin: "40px auto", padding: "0 20px", fontFamily: "sans-serif" }}>
      <style>{`
        .pdf-viewer {
          width: 100%;
          min-height: 760px;
          border: 1px solid #d9e1ec;
          border-radius: 12px;
          background: #f8fafc;
        }
        .viewer-placeholder {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 240px;
          border: 1px dashed #d9e1ec;
          border-radius: 12px;
          background: #f8fafc;
          color: #52607a;
          padding: 20px;
          text-align: center;
        }
      `}</style>
      <h1>LicitIA — Tender Workspace</h1>

      <div style={{ display: "grid", gridTemplateColumns: "370px 1fr", gap: 24 }}>
        <section style={{ border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Create Tender</h2>
          <form onSubmit={handleSubmit}>
            <div style={{ display: "grid", gap: 12 }}>
              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Title</div>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                />
              </label>

              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Institution / Profile</div>
                <input
                  value={institutionProfile}
                  onChange={(event) => setInstitutionProfile(event.target.value)}
                  placeholder="optional"
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                />
              </label>

              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>External Reference</div>
                <input
                  value={externalReference}
                  onChange={(event) => setExternalReference(event.target.value)}
                  placeholder="optional"
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                />
              </label>

              {error && <div style={{ color: "crimson", fontSize: 14 }}>{error}</div>}

              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: "11px 16px",
                  borderRadius: 8,
                  border: "none",
                  background: "#1b5bd8",
                  color: "#fff",
                  fontWeight: 700,
                  cursor: loading ? "not-allowed" : "pointer",
                }}
              >
                {loading ? "Creating..." : "Create Tender"}
              </button>
            </div>
          </form>
        </section>

        <section style={{ border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Existing Tenders</h2>

          {tenders.length === 0 ? (
            <p>No tenders created yet.</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {tenders.map((tender) => {
                const active = tender.id === selectedTenderId;
                return (
                  <button
                    key={tender.id}
                    type="button"
                    onClick={() => handleSelectTender(tender.id)}
                    style={{
                      textAlign: "left",
                      border: active ? "2px solid #1b5bd8" : "1px solid #e8edf2",
                      borderRadius: 10,
                      padding: 14,
                      background: active ? "#edf4ff" : "#f8fafc",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{tender.title}</div>
                      {active && (
                        <span style={{ fontSize: 12, background: "#dfeeff", color: "#1b5bd8", borderRadius: 999, padding: "4px 8px", fontWeight: 700 }}>
                          Seleccionado
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 14, color: "#52607a", marginTop: 8 }}>
                      {tender.institution_profile || "No institution profile"} • {tender.external_reference || "No external reference"}
                    </div>
                    <div style={{ fontSize: 12, color: "#5d6d88", marginTop: 8 }}>
                      Status: {tender.status} • ID: {tender.id}
                    </div>
                    <div style={{ fontSize: 12, color: "#5d6d88", marginTop: 4 }}>
                      Created: {new Date(tender.created_at).toLocaleString()}
                    </div>
                    <div style={{ marginTop: 10, fontSize: 12, fontWeight: 700, color: active ? "#1b5bd8" : "#52607a" }}>
                      {active ? "Seleccionado" : "Abrir"}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Import Documents</h2>
          <p style={{ color: "#52607a", marginTop: -4 }}>
            Select a Tender and import multiple files or an entire folder. Duplicates are detected by SHA-256.
          </p>
          <label style={{ display: "inline-block", marginTop: 12 }}>
            <input type="file" multiple onChange={handleImport} style={{ display: "block" }} />
          </label>
          <div style={{ marginTop: 12, color: "#52607a" }}>{importing ? "Importing..." : "Ready to import."}</div>

          {pendingConflict && (
            <div style={{ marginTop: 16, border: "1px solid #d9e1ec", borderRadius: 12, background: "#fff8e7", padding: 16 }}>
              <h3 style={{ marginTop: 0 }}>Conflicto de documento</h3>
              <p style={{ margin: "8px 0" }}>
                Ya existe un documento con el mismo nombre, pero el contenido es diferente. Archivo: <strong>{pendingConflict.filename}</strong>
              </p>

              {pendingConflict.candidates.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <label style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>Selecciona la revisión actual para registrar la nueva revisión</label>
                  <select
                    value={selectedRevisionTargetId}
                    onChange={(event) => setSelectedRevisionTargetId(event.target.value)}
                    style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                  >
                    {pendingConflict.candidates.map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.original_filename} • Rev {candidate.revision_number} • {candidate.is_current ? "Vigente" : "Sustituido"}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 16 }}>
                <button type="button" onClick={() => void resolveConflict("IMPORT_INDEPENDENT")} style={{ padding: "10px 14px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                  Importar como documento independiente
                </button>
                <button type="button" onClick={() => void resolveConflict("NEW_REVISION")} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                  Registrar como nueva revisión
                </button>
                <button type="button" onClick={() => setPendingConflict(null)} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {importResults.length > 0 && (
            <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
              {importResults.map((result, index) => (
                <div key={`${result.filename}-${index}`} style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 12, background: "#f8fafc" }}>
                  <div style={{ fontWeight: 700 }}>{result.filename}</div>
                  <div style={{ fontSize: 12, color: "#52607a", marginTop: 6 }}>
                    {result.status} • {result.message || "No message"}
                  </div>
                  {result.sha256 && <div style={{ fontSize: 12, color: "#52607a" }}>SHA-256: {result.sha256}</div>}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {selectedTenderId ? (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Documentos</h2>

          {documentsLoading && <p>Cargando documentos...</p>}

          {!documentsLoading && documentsError && <p>{documentsError}</p>}

          {!documentsLoading && !documentsError && documents.length === 0 && (
            <p>Esta licitación todavía no tiene documentos importados.</p>
          )}

          {!documentsLoading && !documentsError && documents.length > 0 && (
            <div style={{ display: "grid", gap: 12 }}>
              {documents.map((document) => (
                <div key={document.id} style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 14, background: selectedDocumentId === document.id ? "#edf4ff" : "#f8fafc" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{document.original_filename}</div>
                      <div style={{ fontSize: 12, color: "#52607a", marginTop: 6 }}>
                        Revisión {document.revision_number} • {document.is_current ? "Vigente" : "Sustituido"}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedDocumentId(document.id);
                        void loadDocumentPages(selectedTenderId ?? "", document.id);
                      }}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: "1px solid #cfd8e3",
                        background: selectedDocumentId === document.id ? "#1b5bd8" : "#fff",
                        color: selectedDocumentId === document.id ? "#fff" : "#1a1a1a",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      {selectedDocumentId === document.id ? "Vista previa" : "Ver"}
                    </button>
                  </div>
                  {document.sha256 && (
                    <div style={{ fontSize: 11, color: "#52607a", marginTop: 6, wordBreak: "break-all" }}>
                      SHA-256: {document.sha256.slice(0, 12)}...
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {selectedDocument && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ marginBottom: 12 }}>{selectedDocument.original_filename}</h3>

              {isPdfDocument(selectedDocument) && (
                <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
                  <button type="button" onClick={() => void handleExtractPdfText()} style={{ padding: "10px 14px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                    Extraer texto PDF
                  </button>
                  <span style={{ fontSize: 12, color: "#52607a" }}>
                    Estado: {selectedDocument.processing_status ?? "PENDING"}
                  </span>
                </div>
              )}

              {isPdfDocument(selectedDocument) && selectedDocumentUrl ? (
                <iframe src={selectedDocumentUrl} className="pdf-viewer" title={selectedDocument.original_filename} />
              ) : (
                <div className="viewer-placeholder">Este documento no puede mostrarse en el visor local PDF.</div>
              )}

              {documentPages.length > 0 && (
                <div style={{ marginTop: 20, border: "1px solid #e8edf2", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12 }}>Texto extraído por página</h4>

                  {documentPagesLoading ? (
                    <p>Cargando páginas…</p>
                  ) : (
                    <>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                        {documentPages.map((page) => (
                          <button
                            key={page.id}
                            type="button"
                            onClick={() => setSelectedPageNumber(page.page_number)}
                            style={{
                              borderRadius: 999,
                              border: selectedPageNumber === page.page_number ? "1px solid #1b5bd8" : "1px solid #d9e1ec",
                              background: selectedPageNumber === page.page_number ? "#edf4ff" : "#fff",
                              color: selectedPageNumber === page.page_number ? "#1b5bd8" : "#1a1a1a",
                              padding: "6px 10px",
                              cursor: "pointer",
                              fontWeight: 700,
                            }}
                          >
                            Pág. {page.page_number}
                          </button>
                        ))}
                      </div>

                      {selectedPage && (
                        <div style={{ border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#fff" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
                            <strong>Página {selectedPage.page_number}</strong>
                            <span style={{ color: "#52607a", fontSize: 12 }}>
                              {selectedPage.status} • {selectedPage.char_count} caracteres • {selectedPage.extraction_method}
                            </span>
                          </div>
                          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12, lineHeight: 1.5 }}>
                            {selectedPage.text || "(Sin texto nativo detectado en esta página)"}
                          </pre>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      ) : (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Documentos</h2>
          <p style={{ color: "#52607a" }}>Selecciona una licitación para ver sus documentos</p>
        </section>
      )}
    </div>
  );
}

export default App;
