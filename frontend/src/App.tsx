import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";
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
  imported_at: string;
};

type ImportResult = {
  filename: string;
  source_relative_path: string | null;
  status: string;
  message: string | null;
  document_id: string | null;
  stored_relative_path: string | null;
  sha256: string | null;
};

const API_URL = "http://localhost:8000";

function App() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<TenderDocument[]>([]);
  const [title, setTitle] = useState("");
  const [institutionProfile, setInstitutionProfile] = useState("");
  const [externalReference, setExternalReference] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResults, setImportResults] = useState<ImportResult[]>([]);

  const loadTenders = async () => {
    try {
      const response = await axios.get<Tender[]>(`${API_URL}/tenders`);
      setTenders(response.data);
      if (!selectedTenderId && response.data[0]) {
        setSelectedTenderId(response.data[0].id);
      }
    } catch (err) {
      setError("Unable to load tenders from the backend.");
    }
  };

  const loadDocuments = async (tenderId: string) => {
    try {
      const response = await axios.get<TenderDocument[]>(`${API_URL}/tenders/${tenderId}/documents`);
      setDocuments(response.data);
    } catch (err) {
      setDocuments([]);
    }
  };

  useEffect(() => {
    void loadTenders();
  }, []);

  useEffect(() => {
    if (selectedTenderId) {
      void loadDocuments(selectedTenderId);
    }
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

      setImportResults(response.data);
      await loadDocuments(selectedTenderId);
    } catch (err) {
      setError("Unable to import the selected documents.");
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: "40px auto", padding: "0 20px", fontFamily: "sans-serif" }}>
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
                    onClick={() => setSelectedTenderId(tender.id)}
                    style={{
                      textAlign: "left",
                      border: active ? "2px solid #1b5bd8" : "1px solid #e8edf2",
                      borderRadius: 10,
                      padding: 14,
                      background: active ? "#edf4ff" : "#f8fafc",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: 18 }}>{tender.title}</div>
                    <div style={{ fontSize: 14, color: "#52607a", marginTop: 8 }}>
                      {tender.institution_profile || "No institution profile"} • {tender.external_reference || "No external reference"}
                    </div>
                    <div style={{ fontSize: 12, color: "#5d6d88", marginTop: 8 }}>
                      Status: {tender.status} • ID: {tender.id}
                    </div>
                    <div style={{ fontSize: 12, color: "#5d6d88", marginTop: 4 }}>
                      Created: {new Date(tender.created_at).toLocaleString()}
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

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Document Registry</h2>

          {documents.length === 0 ? (
            <p>No documents imported for this Tender yet.</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {documents.map((document) => (
                <div key={document.id} style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 14, background: "#f8fafc" }}>
                  <div style={{ fontWeight: 700, fontSize: 18 }}>{document.original_filename}</div>
                  <div style={{ fontSize: 12, color: "#52607a", marginTop: 6 }}>
                    {document.source_relative_path || "No source path"} • {document.file_size_bytes} bytes • {document.mime_type || "unknown type"}
                  </div>
                  <div style={{ fontSize: 12, color: "#52607a", marginTop: 6 }}>
                    Status: {document.status} • Imported: {new Date(document.imported_at).toLocaleString()}
                  </div>
                  <div style={{ fontSize: 11, color: "#52607a", marginTop: 6, wordBreak: "break-all" }}>
                    SHA-256: {document.sha256}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default App;
