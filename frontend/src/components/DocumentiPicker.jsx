import { Paperclip, Camera } from "lucide-react";
import api from "../lib/api";

const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";

export const uploadDocumenti = async (files, { clientId, servizioId } = {}) => {
  for (const f of files) {
    const fd = new FormData();
    fd.append("file", f);
    if (f.tipo) fd.append("tipo", f.tipo);
    if (clientId) await api.post(`/clients/${clientId}/attachments`, fd);
    if (servizioId) {
      const fd2 = new FormData();
      fd2.append("file", f);
      await api.post(`/servizi/${servizioId}/attachments`, fd2);
    }
  }
};

const TIPI = [["bolletta", "Bolletta"], ["documento", "Documento d'identità / CF"], ["altro", "Altro"]];
const indovinaTipo = (f, idx) => (/boll|fatt|enel|eni|luce|gas/i.test(f.name) ? "bolletta" : /ci|carta|ident|cf|codice|patente/i.test(f.name) ? "documento" : idx === 0 ? "bolletta" : "documento");

export const DocumentiPicker = ({ files, onChange, label = "Allega documenti (carta d'identità, ecc.)", testid = "documenti", conTipo = false }) => {
  const add = (e) => {
    const nuovi = Array.from(e.target.files || []);
    if (conTipo) nuovi.forEach((f, i) => { f.tipo = indovinaTipo(f, files.length + i); });
    onChange([...files, ...nuovi]); e.target.value = "";
  };
  const setTipo = (i, t) => { files[i].tipo = t; onChange([...files]); };
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-3 text-sm" data-testid={`${testid}-box`}>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex cursor-pointer items-center gap-2 font-medium text-slate-700"><Paperclip className="h-4 w-4" /> {label}
          <input type="file" multiple accept={ACCEPT} className="hidden" onChange={add} data-testid={`${testid}-input`} /></label>
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-800 hover:bg-sky-100"><Camera className="h-4 w-4" /> Fotografa documento
          <input type="file" accept="image/*" capture="environment" className="hidden" onChange={add} data-testid={`${testid}-camera-input`} /></label>
      </div>
      {files.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-slate-600" data-testid={`${testid}-list`}>
          {files.map((f, i) => <li key={i} className="flex items-center justify-between gap-2"><span className="truncate">{f.name}</span><span className="flex shrink-0 items-center gap-2">{conTipo && <select value={f.tipo || "altro"} onChange={(e) => setTipo(i, e.target.value)} className="h-6 rounded border border-slate-300 bg-white px-1 text-[11px]" data-testid={`${testid}-tipo-${i}`}>{TIPI.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}<button type="button" className="text-rose-600" onClick={() => onChange(files.filter((_, j) => j !== i))}>rimuovi</button></span></li>)}
        </ul>
      )}
    </div>
  );
};
