import { FormEvent, useEffect, useState } from "react";
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

const API_URL = "http://localhost:8000";

function App() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [title, setTitle] = useState("");
  const [institutionProfile, setInstitutionProfile] = useState("");
  const [externalReference, setExternalReference] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadTenders = async () => {
    try {
      const response = await axios.get<Tender[]>(`${API_URL}/tenders`);
      setTenders(response.data);
    } catch (err) {
      setError("Unable to load tenders from the backend.");
    }
  };

  useEffect(() => {
    void loadTenders();
  }, []);

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

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: "0 20px", fontFamily: "sans-serif" }}>
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
              {tenders.map((tender) => (
                <div key={tender.id} style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 14, background: "#f8fafc" }}>
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
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
