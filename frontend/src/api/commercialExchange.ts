import axios from "axios";
export type ImportRow = { scope_id: string; item_reference?: string; import_row: number | null;
  state: string; eligible: boolean; warnings: string[]; errors: string[]; invalid_fields?: string[];
  diff: {field: string; current: string | null; imported: string | null; proposed: string | null}[];
  reference_diff?: {field: string; current: string; imported: string}[]; price_outcome?: string };
export type ImportPreview = { stage_id: string; export_id: string; tender_id: string; origin: string;
  applied: false; counts: Record<string, number>; rows: ImportRow[];
  file_evidence: {sha256: string; file_name: string; format: string; export_id: string; stage_id: string} };
export type ImportApplied = { stage_id: string; applied: true; counts: Record<string, number>;
  outcomes: {scope_id: string; outcome: string; reasons: string[]; warnings?: string[]}[] };
const path = (base: string, tender: string) => `${base}/tenders/${tender}/commercial-exchange`;
export const exchangeApi = {
  export: async (base: string,tender: string,kind: "xlsx" | "csv") => (await axios.get<Blob>(`${path(base,tender)}/export/${kind}`,{responseType:"blob"})).data,
  stage: async (base: string,tender: string,file: File,replace: boolean,currency: boolean) => {
    const form=new FormData();form.append("file",file);form.append("replace_manual_price",String(replace));form.append("confirm_currency_change",String(currency));
    return (await axios.post<ImportPreview>(`${path(base,tender)}/stage`,form)).data;
  },
  apply: async (base: string,tender: string,stage: string) => (await axios.post<ImportApplied>(`${path(base,tender)}/stages/${stage}/apply`,{confirm:true})).data,
};
