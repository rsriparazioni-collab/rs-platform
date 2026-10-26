import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Save, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

const TIERS = ["5", "10", "15", "20"];
const vuota = (mese) => ({ mese, periodo: "", righe: [], accessori: [], note: "" });

export const IncentiviSoglie = ({ mese }) => {
  const [lista, setLista] = useState([]);
  const [form, setForm] = useState(vuota(mese));
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();
  const load = useCallback(() => api.get("/incentivi/soglie").then((r) => { setLista(r.data); const f = r.data.find((x) => x.mese === mese); setForm(f || vuota(mese)); }).catch(() => {}), [mese]);
  useEffect(() => { load(); }, [load]);

  const carica = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file); setBusy(true);
    try { const r = await api.post("/incentivi/carica-gara", fd, { headers: { "Content-Type": "multipart/form-data" } }); const a = r.data.anteprima; setForm({ ...form, ...a, mese: a.mese && /^\d{4}-\d{2}$/.test(a.mese) ? a.mese : form.mese, righe: (a.righe || []).map((x) => ({ prodotto: x.prodotto, soglie: Object.fromEntries(TIERS.map((t) => [t, x.soglie?.[t] ?? ""])) })), accessori: a.accessori || [] }); toast.success("Tabella letta: controlla e salva"); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  const salva = async () => {
    try { await api.post("/incentivi/soglie", { ...form, righe: form.righe.map((r) => ({ ...r, soglie: Object.fromEntries(TIERS.map((t) => [t, parseFloat(r.soglie[t]) || 0])) })), accessori: form.accessori.map((a) => ({ ...a, importo: parseFloat(a.importo) || 0 })) }); toast.success(`Soglie ${form.mese} salvate`); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const setRiga = (i, patch) => setForm({ ...form, righe: form.righe.map((r, j) => (j === i ? { ...r, ...patch } : r)) });

  return (
    <div className="space-y-4" data-testid="inc-soglie">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border-2 border-dashed border-sky-300 bg-sky-50 p-4">
        <Camera className="h-8 w-8 text-sky-600" />
        <div className="flex-1"><p className="font-semibold text-slate-900">Carica gara EOLO del mese</p><p className="text-xs text-slate-600">Foto o screenshot del volantino "Gara TOP Partner Retail": la tabella soglie viene letta in automatico, poi la controlli e salvi.</p></div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => carica(e.target.files?.[0])} data-testid="inc-gara-file" />
        <Button onClick={() => fileRef.current?.click()} disabled={busy} data-testid="inc-gara-btn">{busy ? "Lettura in corso…" : "Carica gara (foto)"}</Button>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <input type="month" value={form.mese} onChange={(e) => setForm({ ...form, mese: e.target.value })} className="h-9 rounded-md border border-slate-200 px-2 text-sm" data-testid="inc-soglie-mese" />
          <Input className="w-72" placeholder="Periodo (es. ordini 01/10–31/10)" value={form.periodo} onChange={(e) => setForm({ ...form, periodo: e.target.value })} />
          <Button size="sm" variant="outline" onClick={() => setForm({ ...form, righe: [...form.righe, { prodotto: "", soglie: Object.fromEntries(TIERS.map((t) => [t, ""])) }] })} data-testid="inc-soglie-add"><Plus className="h-4 w-4" /> Riga</Button>
          <Button size="sm" onClick={salva} data-testid="inc-soglie-salva"><Save className="h-4 w-4" /> Salva soglie {form.mese}</Button>
        </div>
        <table className="mt-3 w-full text-sm" data-testid="inc-soglie-table">
          <thead className="text-left text-xs uppercase text-slate-500"><tr><th className="px-2 py-1">Prodotto</th>{TIERS.map((t) => <th key={t} className="px-2 py-1">Da {t}</th>)}<th></th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {form.righe.map((r, i) => <tr key={i}><td className="px-2 py-1"><Input className="h-8" value={r.prodotto} onChange={(e) => setRiga(i, { prodotto: e.target.value })} data-testid={`inc-soglia-prod-${i}`} /></td>
              {TIERS.map((t) => <td key={t} className="px-2 py-1"><Input type="number" className="h-8 w-20" value={r.soglie[t]} onChange={(e) => setRiga(i, { soglie: { ...r.soglie, [t]: e.target.value } })} /></td>)}
              <td><button onClick={() => setForm({ ...form, righe: form.righe.filter((_, j) => j !== i) })}><Trash2 className="h-4 w-4 text-slate-400" /></button></td></tr>)}
          </tbody>
        </table>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm"><span className="text-slate-500">Accessori:</span>
          {form.accessori.map((a, i) => <span key={i} className="flex items-center gap-1 rounded border border-slate-200 px-2 py-1"><Input className="h-7 w-32" value={a.voce} onChange={(e) => setForm({ ...form, accessori: form.accessori.map((x, j) => (j === i ? { ...x, voce: e.target.value } : x)) })} /><Input type="number" className="h-7 w-16" value={a.importo} onChange={(e) => setForm({ ...form, accessori: form.accessori.map((x, j) => (j === i ? { ...x, importo: e.target.value } : x)) })} /></span>)}
          <Button size="sm" variant="ghost" onClick={() => setForm({ ...form, accessori: [...form.accessori, { voce: "", importo: "" }] })}><Plus className="h-4 w-4" /></Button></div>
      </div>
      <p className="text-xs text-slate-500">Soglie salvate: {lista.map((l) => l.mese).join(", ") || "nessuna"}. La soglia (Da 5/10/15/20) si calcola sul totale EOLO del mese di tutti i negozi e propone l'importo nei contratti "In pagamento".</p>
    </div>
  );
};
