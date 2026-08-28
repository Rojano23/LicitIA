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

type PageOcrResult = {
  id: string;
  document_page_id: string;
  page_number: number | null;
  engine: string;
  engine_version: string;
  language: string;
  text: string;
  status: string;
  confidence: number | null;
  processing_time_ms: number | null;
  warnings: string | null;
  created_at: string;
  updated_at: string;
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
  ocr_results: PageOcrResult[];
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

type OcrProvider = {
  provider_id: string;
  provider_name: string;
  status: string;
  version: string | null;
  status_reason: string | null;
};

type ClassificationEvidence = {
  document_page_id: string | null;
  normalized_content_id: string | null;
  document_chunk_id: string | null;
  source_kind: string;
  signal: string;
  excerpt: string;
  weight_or_score: number;
};

type ClassificationTag = {
  tag: string;
  score: number;
};

type ClassificationCandidateScore = {
  type: string;
  score: number;
};

type ClassificationResult = {
  document_id: string;
  suggested_type: string;
  suggested_score: number;
  effective_type: string;
  classification_status: string;
  is_composite: boolean;
  human_type: string | null;
  human_note: string | null;
  candidate_scores: ClassificationCandidateScore[];
  functional_tags: ClassificationTag[];
  evidence: ClassificationEvidence[];
  input_fingerprint_sha256: string;
  not_ready: boolean;
};

type ReferenceCandidate = {
  document_id: string;
  original_filename: string;
  processing_status: string | null;
};

type ReferenceItem = {
  id: string;
  source_document_id: string;
  raw_reference_text: string;
  normalized_reference_key: string;
  relationship_hint: string;
  resolution_status: string;
  resolved_target_document_id: string | null;
  resolved_target_filename: string | null;
  page_number: number | null;
  excerpt: string;
  source_type: string | null;
  source_scope: string | null;
  source_engine: string | null;
  ambiguous_candidates: ReferenceCandidate[];
  human_decision: string | null;
};

type RelationshipSupport = {
  reference_id: string;
  raw_reference_text: string;
  normalized_reference_key: string;
  page_number: number | null;
  excerpt: string;
};

type RelationshipItem = {
  id: string;
  source_document_id: string;
  source_document_filename: string | null;
  target_document_id: string;
  target_document_filename: string | null;
  relationship_type: string;
  supporting_references: RelationshipSupport[];
};

type ReferenceAnalysis = {
  document_id: string;
  status: string;
  extractor_version: string;
  input_fingerprint_sha256: string;
  references: ReferenceItem[];
  relationships: RelationshipItem[];
  counts: {
    total_reference_mentions: number;
    resolved_references: number;
    ambiguous_references: number;
    unresolved_references: number;
    human_resolved_references: number;
    ignored_references: number;
    resolved_relationships: number;
  };
};

type AuditFinding = {
  code: string;
  severity: string;
  message: string;
  document_id: string | null;
  document_filename: string | null;
};

type AuditDocumentRow = {
  document_id: string;
  document_short_id: string;
  filename: string;
  is_current: boolean;
  processing_status: string;
  page_count: number;
  text_acquisition_state: string;
  normalized: boolean;
  normalized_source_count: number;
  classification_type: string;
  classification_status: string;
  classification_version: string | null;
  reference_analysis_status: string;
  reference_extractor_version: string | null;
  reference_count: number;
  auto_resolved_reference_count: number;
  human_resolved_reference_count: number;
  ambiguous_reference_count: number;
  unresolved_reference_count: number;
  ignored_reference_count: number;
  integrity_findings: string[];
};

type DocumentIntelligenceAudit = {
  tender_id: string;
  audit_version: string;
  generated_at: string;
  overall_readiness: string;
  summary: {
    documents: {
      total_documents: number;
      current_documents: number;
      non_current_documents: number;
    };
    classification: {
      classified_documents: number;
      unclassified_documents: number;
      status_counts: {
        SUGGESTED: number;
        CONFIRMED: number;
        NEEDS_REVIEW: number;
        OVERRIDDEN: number;
      };
    };
    references: {
      status_counts: {
        AUTO_RESOLVED: number;
        HUMAN_RESOLVED: number;
        AMBIGUOUS: number;
        UNRESOLVED: number;
        IGNORED: number;
      };
    };
  };
  document_rows: AuditDocumentRow[];
  findings: AuditFinding[];
};

type BaselineReferenceStatusCounts = {
  AUTO_RESOLVED: number;
  HUMAN_RESOLVED: number;
  AMBIGUOUS: number;
  UNRESOLVED: number;
  IGNORED: number;
};

type DocumentMapEntry = {
  source_document_id: string;
  source_filename: string | null;
  relationship_type: string;
  target_document_id: string;
  target_filename: string | null;
  supporting_reference_count: number;
  supporting_pages: number[];
  resolution_origin: string;
};

type RelationshipBaseline = {
  tender_id: string;
  baseline_version: string;
  source_audit_version: string;
  generated_at: string;
  counts: {
    relationship_edge_count: number;
    unresolved_reference_groups_count: number;
    ambiguous_reference_groups_count: number;
    duplicate_edge_count: number;
    self_edge_count: number;
  };
  reference_status_counts: BaselineReferenceStatusCounts;
  document_map: DocumentMapEntry[];
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
  const [ocrProviders, setOcrProviders] = useState<OcrProvider[]>([]);
  const [ocrMode, setOcrMode] = useState("AUTO");
  const [ocrRunning, setOcrRunning] = useState(false);
  const [classificationResult, setClassificationResult] = useState<ClassificationResult | null>(null);
  const [classificationLoading, setClassificationLoading] = useState(false);
  const [referenceAnalysis, setReferenceAnalysis] = useState<ReferenceAnalysis | null>(null);
  const [referenceLoading, setReferenceLoading] = useState(false);
  const [referenceTargetSelections, setReferenceTargetSelections] = useState<Record<string, string>>({});
  const [audit, setAudit] = useState<DocumentIntelligenceAudit | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [relationshipBaseline, setRelationshipBaseline] = useState<RelationshipBaseline | null>(null);
  const [relationshipBaselineLoading, setRelationshipBaselineLoading] = useState(false);
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
      setReferenceAnalysis(null);
      setAudit(null);
      setRelationshipBaseline(null);
      return;
    }

    setSelectedDocumentId(null);
    void loadDocuments(selectedTenderId);
    void loadOcrProviders();
    void loadDocumentIntelligenceAudit(selectedTenderId);
    void loadRelationshipBaseline(selectedTenderId);
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

  const loadOcrProviders = async () => {
    try {
      const response = await axios.get<OcrProvider[]>(`${API_URL}/ocr/providers`);
      setOcrProviders(response.data);
    } catch (err) {
      setOcrProviders([]);
    }
  };

  const handleRunOcr = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setOcrRunning(true);
    try {
      const pageSelection = selectedPageNumber ? [selectedPageNumber] : undefined;
      await axios.post(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/ocr`, {
        provider: ocrMode,
        page_numbers: pageSelection,
        force: false,
      });
      await loadDocumentPages(selectedTenderId, selectedDocumentId);
      await loadOcrProviders();
    } catch (err) {
      setError("No se pudo ejecutar el OCR del documento.");
    } finally {
      setOcrRunning(false);
    }
  };

  const loadDocumentClassification = async (tenderId: string, documentId: string) => {
    setClassificationLoading(true);
    try {
      const response = await axios.get<ClassificationResult>(`${API_URL}/tenders/${tenderId}/documents/${documentId}/classification`);
      setClassificationResult(response.data);
    } catch (err) {
      setClassificationResult(null);
    } finally {
      setClassificationLoading(false);
    }
  };

  const loadDocumentReferences = async (tenderId: string, documentId: string) => {
    setReferenceLoading(true);
    try {
      const response = await axios.get<ReferenceAnalysis>(`${API_URL}/tenders/${tenderId}/documents/${documentId}/references`);
      setReferenceAnalysis(response.data);
    } catch (err) {
      setReferenceAnalysis(null);
    } finally {
      setReferenceLoading(false);
    }
  };

  const handleAnalyzeReferences = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setReferenceLoading(true);
    try {
      const response = await axios.post<ReferenceAnalysis>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/analyze-references`);
      setReferenceAnalysis(response.data);
    } catch (err) {
      setError("No se pudieron analizar las referencias del documento.");
    } finally {
      setReferenceLoading(false);
    }
  };

  const handleReferenceDecision = async (referenceId: string, action: string) => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const payload: Record<string, string> = {
        action,
      };
      if (action === "RESOLVE_TO_DOCUMENT") {
        const selectedTarget = referenceTargetSelections[referenceId];
        if (!selectedTarget) {
          setError("Seleccione un documento destino para resolver la referencia.");
          return;
        }
        payload.human_target_document_id = selectedTarget;
      }
      const response = await axios.patch<ReferenceAnalysis>(`${API_URL}/tenders/${selectedTenderId}/references/${referenceId}`, payload);
      setReferenceAnalysis(response.data);
    } catch (err) {
      setError("No se pudo guardar la decisión de referencia.");
    }
  };

  const loadDocumentIntelligenceAudit = async (tenderId: string) => {
    setAuditLoading(true);
    try {
      const response = await axios.get<DocumentIntelligenceAudit>(`${API_URL}/tenders/${tenderId}/document-intelligence-audit`);
      setAudit(response.data);
    } catch (err) {
      setAudit(null);
    } finally {
      setAuditLoading(false);
    }
  };

  const handleRunDocumentIntelligenceAudit = async () => {
    if (!selectedTenderId) {
      return;
    }

    setAuditLoading(true);
    try {
      const response = await axios.post<DocumentIntelligenceAudit>(`${API_URL}/tenders/${selectedTenderId}/audit-document-intelligence`);
      setAudit(response.data);
      await loadRelationshipBaseline(selectedTenderId);
    } catch (err) {
      setError("No se pudo auditar el estado documental del expediente.");
    } finally {
      setAuditLoading(false);
    }
  };

  const loadRelationshipBaseline = async (tenderId: string) => {
    setRelationshipBaselineLoading(true);
    try {
      const response = await axios.get<RelationshipBaseline>(`${API_URL}/tenders/${tenderId}/relationship-baseline`);
      setRelationshipBaseline(response.data);
    } catch (err) {
      setRelationshipBaseline(null);
    } finally {
      setRelationshipBaselineLoading(false);
    }
  };

  const referenceStatusLabel = (status: string) => {
    if (status === "AUTO_RESOLVED") {
      return "Resuelta";
    }
    if (status === "AMBIGUOUS") {
      return "Ambigua";
    }
    if (status === "UNRESOLVED") {
      return "No encontrada";
    }
    if (status === "HUMAN_RESOLVED") {
      return "Resuelta por usuario";
    }
    if (status === "IGNORED") {
      return "Ignorada";
    }
    return status;
  };

  const shortId = (value: string | null) => (value ? value.slice(0, 8) : "");

  const candidateLabel = (candidate: ReferenceCandidate) => {
    return `${candidate.original_filename} · ${shortId(candidate.document_id)} · ${candidate.processing_status ?? "PENDING"}`;
  };

  const groupedReferences = (() => {
    if (!referenceAnalysis) {
      return [] as Array<{
        groupKey: string;
        normalized_reference_key: string;
        resolution_status: string;
        relationship_hint: string;
        mentions: ReferenceItem[];
        page_numbers: number[];
        candidate_label: string;
        target_label: string;
      }>;
    }

    const groups = new Map<string, {
      groupKey: string;
      normalized_reference_key: string;
      resolution_status: string;
      relationship_hint: string;
      mentions: ReferenceItem[];
      page_numbers: Set<number>;
      candidate_label: string;
      target_label: string;
    }>();

    for (const mention of referenceAnalysis.references) {
      const candidateSignature = mention.ambiguous_candidates.map((item) => item.document_id).sort().join(",");
      const key = `${mention.normalized_reference_key}|${mention.resolution_status}|${candidateSignature}`;
      const candidateText = mention.ambiguous_candidates
        .map((candidate) => `${candidate.original_filename} · ${shortId(candidate.document_id)} · ${candidate.processing_status ?? "PENDING"}`)
        .join(" | ");
      const targetText = mention.resolved_target_filename
        ? `${mention.resolved_target_filename} · ${shortId(mention.resolved_target_document_id)}`
        : "-";

      const existing = groups.get(key);
      if (existing) {
        existing.mentions.push(mention);
        if (mention.page_number !== null) {
          existing.page_numbers.add(mention.page_number);
        }
        continue;
      }

      groups.set(key, {
        groupKey: key,
        normalized_reference_key: mention.normalized_reference_key,
        resolution_status: mention.resolution_status,
        relationship_hint: mention.relationship_hint,
        mentions: [mention],
        page_numbers: mention.page_number !== null ? new Set([mention.page_number]) : new Set(),
        candidate_label: candidateText,
        target_label: targetText,
      });
    }

    return Array.from(groups.values())
      .map((item) => ({ ...item, page_numbers: Array.from(item.page_numbers).sort((a, b) => a - b) }))
      .sort((a, b) => b.mentions.length - a.mentions.length);
  })();

  const handleClassifyDocument = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setClassificationLoading(true);
    try {
      const response = await axios.post<ClassificationResult>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/classify`);
      setClassificationResult(response.data);
    } catch (err) {
      setClassificationResult(null);
      setError("No se pudo clasificar el documento.");
    } finally {
      setClassificationLoading(false);
    }
  };

  const handleConfirmClassification = async () => {
    if (!selectedTenderId || !selectedDocumentId || !classificationResult) {
      return;
    }

    try {
      const response = await axios.patch<ClassificationResult>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/classification`, {
        action: "CONFIRM",
        human_type: classificationResult.effective_type,
        human_note: "Confirmado por usuario",
      });
      setClassificationResult(response.data);
    } catch (err) {
      setError("No se pudo confirmar la clasificación.");
    }
  };

  const handleReviewClassification = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    try {
      const response = await axios.patch<ClassificationResult>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/classification`, {
        action: "MARK_FOR_REVIEW",
        human_note: "Revisión humana requerida",
      });
      setClassificationResult(response.data);
    } catch (err) {
      setError("No se pudo marcar la clasificación para revisión.");
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
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>Estado del expediente</h2>
            <button type="button" onClick={() => void handleRunDocumentIntelligenceAudit()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
              {auditLoading ? "Auditando..." : "Auditar expediente"}
            </button>
          </div>

          {!audit && <p style={{ color: "#52607a" }}>Sin auditoría cargada para esta licitación.</p>}

          {audit && (
            <>
              <div style={{ marginTop: 12, fontSize: 13, color: "#52607a" }}>
                Estado general: <strong>{audit.overall_readiness}</strong> • Versión auditoría: {audit.audit_version} • Actualizado: {new Date(audit.generated_at).toLocaleString()}
              </div>

              <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Documentos</div>
                  <div style={{ fontWeight: 700 }}>{audit.summary.documents.current_documents} actuales / {audit.summary.documents.total_documents} totales</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Clasificación</div>
                  <div style={{ fontWeight: 700 }}>{audit.summary.classification.classified_documents} clasificados / {audit.summary.classification.unclassified_documents} pendientes</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Referencias</div>
                  <div style={{ fontWeight: 700 }}>
                    Auto {audit.summary.references.status_counts.AUTO_RESOLVED} • Usuario {audit.summary.references.status_counts.HUMAN_RESOLVED} • Ambiguas {audit.summary.references.status_counts.AMBIGUOUS}
                  </div>
                  <div style={{ fontWeight: 700 }}>
                    Sin resolver {audit.summary.references.status_counts.UNRESOLVED} • Ignoradas {audit.summary.references.status_counts.IGNORED}
                  </div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Hallazgos</div>
                  <div style={{ fontWeight: 700 }}>{audit.findings.length} hallazgos</div>
                </div>
              </div>

              {audit.findings.length > 0 && (
                <div style={{ marginTop: 12, border: "1px solid #e8edf2", borderRadius: 10, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontWeight: 700, marginBottom: 8 }}>Hallazgos de integridad</div>
                  <div style={{ display: "grid", gap: 6 }}>
                    {audit.findings.slice(0, 10).map((finding, index) => (
                      <div key={`${finding.code}-${index}`} style={{ fontSize: 12 }}>
                        <strong>{finding.severity}</strong> • {finding.code} • {finding.message}
                        {finding.document_filename ? ` (${finding.document_filename})` : ""}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Texto</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Normalizado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Clasificación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Referencias</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.document_rows.map((row) => (
                      <tr key={row.document_id}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div style={{ fontWeight: 700 }}>{row.filename}</div>
                          <div style={{ color: "#52607a" }}>{row.document_short_id} • {row.processing_status}</div>
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.text_acquisition_state}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.normalized ? `Sí (${row.normalized_source_count})` : "No"}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {row.classification_type} • {row.classification_status}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {row.reference_analysis_status} • A:{row.auto_resolved_reference_count} H:{row.human_resolved_reference_count} Am:{row.ambiguous_reference_count} U:{row.unresolved_reference_count}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.integrity_findings.join(", ") || "OK"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2 style={{ marginTop: 0 }}>Mapa documental</h2>
          {relationshipBaselineLoading && <div style={{ color: "#52607a", fontSize: 13 }}>Cargando baseline relacional...</div>}
          {!relationshipBaselineLoading && !relationshipBaseline && (
            <div style={{ color: "#52607a", fontSize: 13 }}>No se pudo cargar el baseline relacional.</div>
          )}
          {relationshipBaseline && (
            <>
              <div style={{ fontSize: 13, color: "#52607a" }}>
                Baseline {relationshipBaseline.baseline_version} (fuente audit {relationshipBaseline.source_audit_version}) • {new Date(relationshipBaseline.generated_at).toLocaleString()}
              </div>
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Relaciones</div>
                  <div style={{ fontWeight: 700 }}>{relationshipBaseline.counts.relationship_edge_count}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Referencias ambiguas</div>
                  <div style={{ fontWeight: 700 }}>{relationshipBaseline.reference_status_counts.AMBIGUOUS}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Referencia sin documento físico resuelto</div>
                  <div style={{ fontWeight: 700 }}>{relationshipBaseline.reference_status_counts.UNRESOLVED}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Integridad del grafo</div>
                  <div style={{ fontWeight: 700 }}>Dup {relationshipBaseline.counts.duplicate_edge_count} • Self {relationshipBaseline.counts.self_edge_count}</div>
                </div>
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento origen</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Relación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento destino</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Evidencias</th>
                    </tr>
                  </thead>
                  <tbody>
                    {relationshipBaseline.document_map.map((entry) => (
                      <tr key={`${entry.source_document_id}-${entry.relationship_type}-${entry.target_document_id}`}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.source_filename ?? entry.source_document_id}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.relationship_type}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.target_filename ?? entry.target_document_id}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {entry.supporting_reference_count} refs • págs {entry.supporting_pages.length > 0 ? entry.supporting_pages.join(", ") : "-"} • origen {entry.resolution_origin}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

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
                        void loadDocumentClassification(selectedTenderId ?? "", document.id);
                        void loadDocumentReferences(selectedTenderId ?? "", document.id);
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
                  <button type="button" onClick={() => void handleClassifyDocument()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                    {classificationLoading ? "Clasificando..." : "Clasificar documento"}
                  </button>
                  <button type="button" onClick={() => void handleAnalyzeReferences()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                    {referenceLoading ? "Analizando referencias..." : "Analizar referencias"}
                  </button>
                  <span style={{ fontSize: 12, color: "#52607a" }}>
                    Estado: {selectedDocument.processing_status ?? "PENDING"}
                  </span>
                </div>
              )}

              {referenceAnalysis && (
                <div style={{ marginBottom: 20, border: "1px solid #d9e1ec", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12 }}>Referencias detectadas</h4>
                  <div style={{ fontSize: 12, color: "#52607a", marginBottom: 10 }}>
                    Estado análisis: {referenceAnalysis.status} • Total: {referenceAnalysis.counts.total_reference_mentions} • Auto-resueltas: {referenceAnalysis.counts.resolved_references} • Resueltas por usuario: {referenceAnalysis.counts.human_resolved_references} • Ambiguas: {referenceAnalysis.counts.ambiguous_references} • Sin documento resuelto: {referenceAnalysis.counts.unresolved_references} • Ignoradas: {referenceAnalysis.counts.ignored_references}
                  </div>

                  {referenceAnalysis.references.length === 0 ? (
                    <div style={{ fontSize: 12, color: "#52607a" }}>No se detectaron referencias documentales.</div>
                  ) : (
                    <div style={{ display: "grid", gap: 8 }}>
                      {groupedReferences.map((group) => (
                        <div key={group.groupKey} style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#fff" }}>
                          <div style={{ fontWeight: 700, marginBottom: 6 }}>{group.normalized_reference_key}</div>
                          <div style={{ fontSize: 12, color: "#52607a" }}>
                            {group.mentions.length} menciones • Estado: {referenceStatusLabel(group.resolution_status)} • Relación: {group.relationship_hint} • Páginas: {group.page_numbers.length > 0 ? group.page_numbers.join(", ") : "-"}
                          </div>
                          <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                            Destino: {group.target_label}
                          </div>
                          {group.candidate_label && (
                            <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                              Candidatos: {group.candidate_label}
                            </div>
                          )}

                          <details style={{ marginTop: 8 }}>
                            <summary style={{ cursor: "pointer", fontSize: 12, color: "#1b5bd8", fontWeight: 700 }}>Ver evidencias y acciones</summary>
                            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                              {group.mentions.map((reference) => (
                                <div key={reference.id} style={{ border: "1px solid #edf2f7", borderRadius: 8, padding: 8, background: "#f8fafc" }}>
                                  <div style={{ fontSize: 12, color: "#52607a" }}>
                                    Página: {reference.page_number ?? "-"} • Texto: {reference.raw_reference_text}
                                  </div>
                                  <div style={{ fontSize: 12, marginTop: 4 }}>{reference.excerpt}</div>
                                  {(reference.resolution_status === "AMBIGUOUS" || reference.resolution_status === "UNRESOLVED") && (
                                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                                      <select
                                        value={referenceTargetSelections[reference.id] ?? ""}
                                        onChange={(event) =>
                                          setReferenceTargetSelections((prev) => ({
                                            ...prev,
                                            [reference.id]: event.target.value,
                                          }))
                                        }
                                        style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #cfd8e3" }}
                                      >
                                        <option value="">Seleccionar documento destino</option>
                                        {reference.ambiguous_candidates.map((candidate) => (
                                          <option key={candidate.document_id} value={candidate.document_id}>
                                            {candidateLabel(candidate)}
                                          </option>
                                        ))}
                                      </select>
                                      <button type="button" onClick={() => void handleReferenceDecision(reference.id, "RESOLVE_TO_DOCUMENT")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                        Resolver
                                      </button>
                                      <button type="button" onClick={() => void handleReferenceDecision(reference.id, "MARK_UNRESOLVED")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                        Marcar no encontrada
                                      </button>
                                      <button type="button" onClick={() => void handleReferenceDecision(reference.id, "IGNORE_REFERENCE")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                        Ignorar
                                      </button>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {classificationResult && (
                <div style={{ marginBottom: 20, border: "1px solid #d9e1ec", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{classificationResult.effective_type}</div>
                      <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                        Tipo sugerido: {classificationResult.suggested_type} • Puntuación: {classificationResult.suggested_score}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button type="button" onClick={() => void handleConfirmClassification()} style={{ padding: "8px 12px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>Confirmar</button>
                      <button type="button" onClick={() => void handleReviewClassification()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>Revisar</button>
                    </div>
                  </div>

                  {classificationResult.candidate_scores.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ fontSize: 12, color: "#52607a", marginBottom: 6 }}>Tipos candidatos</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {classificationResult.candidate_scores.map((candidate) => (
                          <span key={candidate.type} style={{ fontSize: 12, borderRadius: 999, background: "#ede9fe", color: "#312e81", padding: "4px 8px", fontWeight: 700 }}>
                            {candidate.type} ({candidate.score})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {classificationResult.functional_tags.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ fontSize: 12, color: "#52607a", marginBottom: 6 }}>Funciones detectadas</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {classificationResult.functional_tags.map((tag) => (
                          <span key={tag.tag} style={{ fontSize: 12, borderRadius: 999, background: "#e0f2fe", color: "#0f172a", padding: "4px 8px", fontWeight: 700 }}>
                            {tag.tag} ({tag.score})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {classificationResult.evidence.length > 0 && (
                    <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
                      {classificationResult.evidence.slice(0, 3).map((item, index) => (
                        <div key={`${item.signal}-${index}`} style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#fff" }}>
                          <div style={{ fontSize: 12, color: "#52607a", marginBottom: 6 }}>
                            {item.source_kind} • {item.signal} • peso {item.weight_or_score}
                          </div>
                          <div style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>{item.excerpt}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {isPdfDocument(selectedDocument) && (
                <div style={{ marginBottom: 16, border: "1px solid #e8edf2", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12 }}>OCR providers</h4>
                  <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <select value={ocrMode} onChange={(event) => setOcrMode(event.target.value)} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #cfd8e3" }}>
                      <option value="AUTO">AUTO</option>
                      <option value="TESSERACT">TESSERACT</option>
                      <option value="PADDLEOCR">PADDLEOCR</option>
                      <option value="COMPARE">COMPARE</option>
                    </select>
                    <button type="button" onClick={() => void handleRunOcr()} disabled={ocrRunning} style={{ padding: "10px 14px", borderRadius: 8, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700, cursor: ocrRunning ? "not-allowed" : "pointer" }}>
                      {ocrRunning ? "Procesando OCR..." : "Ejecutar OCR"}
                    </button>
                  </div>

                  <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
                    {ocrProviders.length === 0 ? (
                      <div style={{ color: "#52607a", fontSize: 12 }}>Catalogando providers OCR…</div>
                    ) : (
                      ocrProviders.map((provider) => (
                        <div key={provider.provider_id} style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", border: "1px solid #d9e1ec", borderRadius: 8, padding: "8px 10px", background: "#fff" }}>
                          <div>
                            <strong>{provider.provider_name}</strong>
                            <div style={{ fontSize: 12, color: "#52607a" }}>{provider.version ?? "versión desconocida"}</div>
                          </div>
                          <span style={{ fontSize: 12, borderRadius: 999, padding: "4px 8px", background: provider.status === "AVAILABLE" ? "#dcfce7" : "#fee2e2", color: provider.status === "AVAILABLE" ? "#166534" : "#991b1b", fontWeight: 700 }}>
                            {provider.status}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
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
                        <div style={{ display: "grid", gap: 16 }}>
                          <div style={{ border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#fff" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
                              <strong>Texto nativo</strong>
                              <span style={{ color: "#52607a", fontSize: 12 }}>
                                {selectedPage.status} • {selectedPage.char_count} caracteres • {selectedPage.extraction_method}
                              </span>
                            </div>
                            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12, lineHeight: 1.5 }}>
                              {selectedPage.text || "(Sin texto nativo detectado en esta página)"}
                            </pre>
                          </div>

                          {selectedPage.ocr_results && selectedPage.ocr_results.length > 0 && (
                            <div style={{ border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#fff" }}>
                              <div style={{ marginBottom: 12, fontWeight: 700 }}>OCR alternativas</div>
                              <div style={{ display: "grid", gap: 12 }}>
                                {selectedPage.ocr_results.map((ocrResult) => (
                                  <div key={ocrResult.id} style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
                                      <strong>OCR — {ocrResult.engine}</strong>
                                      <span style={{ color: "#52607a", fontSize: 12 }}>
                                        {ocrResult.status} • {ocrResult.text.length} caracteres • {ocrResult.engine_version}
                                      </span>
                                    </div>
                                    <div style={{ color: "#52607a", fontSize: 12, marginBottom: 8 }}>
                                      {ocrResult.language || "idioma no especificado"}
                                    </div>
                                    {ocrResult.status === "OCR_FAILED" ? (
                                      <div style={{ color: "#991b1b", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 6, padding: 8 }}>
                                        OCR falló: {ocrResult.warnings || "No se pudo completar la lectura por OCR."}
                                      </div>
                                    ) : (
                                      <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12, lineHeight: 1.5 }}>
                                        {ocrResult.text || "No se detectó texto OCR en esta página."}
                                      </pre>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
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
