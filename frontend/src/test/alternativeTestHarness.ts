import axios from "axios";
import { vi } from "vitest";
import type { TechnicalAlternative } from "../api/technicalAlternatives";
import type { ComplianceEvaluation, ScopeSnapshot } from "../api/alternativeCompliance";
import { alternative, evaluation } from "./alternativeFixtures";

export const alternativeProps = { apiUrl: "http://localhost:8000", tenderId: "tender-1",
  documents: [{ id: "document-1", original_filename: "Alcance sintético.pdf" }] };
export function failure(status: number, code?: string) {
  return { isAxiosError: true, response: { status, data: { detail: { code } } } };
}
export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
export function mockAlternatives() {
  const first = alternative();
  const store: { alternatives: TechnicalAlternative[]; evaluations: Record<string, ComplianceEvaluation[]>; scope: ScopeSnapshot } = {
    alternatives: [first], evaluations: { "alt-a": [evaluation()] }, scope: evaluation().scope_snapshot,
  };
  const get = vi.spyOn(axios, "get").mockImplementation(async (url: string) => {
    if (url.endsWith("/technical-alternatives")) return { data: store.alternatives };
    if (url.endsWith("/alternative-scope-snapshot")) return { data: store.scope };
    const parts = url.split("/");
    const index = parts.indexOf("technical-alternatives");
    const id = parts[index + 1];
    if (parts[index + 2] === "compliance") {
      const rows = store.evaluations[id] ?? [];
      if (parts.length === index + 3) return { data: rows };
      const row = rows.find(value => value.id === parts[index + 3]);
      if (row) return { data: row };
    } else {
      const row = store.alternatives.find(value => value.id === id);
      if (row) return { data: row };
    }
    throw failure(404);
  });
  const post = vi.spyOn(axios, "post").mockRejectedValue(new Error("Unexpected synthetic write"));
  return { store, get, post };
}
