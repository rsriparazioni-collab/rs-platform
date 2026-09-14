import { useEffect, useState } from "react";
import { Save, Plus, Trash2, Upload, Search, Calculator } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const MARCHE = { "*": "Tutte le marche", apple: "Apple", samsung: "Samsung", altri: "Altri Android" };
const num = (v) => (v === "" || v == null ? 0 : parseFloat(v) || 0);

function Regole() {
  const [regole, setRegole] = useState([]);
  const [tipologie, setTipologie] = useState({});
  const [sim, setSim] = useState({ tipologia: "display", marca: "apple", costo: "80" });
  useEffect(() => { api.get("/regole-prezzi").then((r) => { setRegole(r.data.regole); setTipologie(r.data.tipologie); }).catch((e) => toast.error(apiError(e))); }, []);
  const upd = (i, k, v) => setRegole((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const save = async () => {
    try {
      const payload = regole.map((r) => ({ tipologia: r.tipologia, marca: r.marca, label: r.label, manodopera: num(r.manodopera), ricarico_pct: num(r.ricarico_pct), prezzo_min: num(r.prezzo_min), prezzo_max: num(r.prezzo_max) }));
      const res = await api.put("/regole-prezzi", payload); setRegole(res.data.regole); toast.success("Regole salvate: i nuovi prezzi consigliati sono attivi");
    } catch (e) { toast.error(apiError(e)); }
  };
  const regola = regole.find((r) => r.tipologia === sim.tipologia && r.marca === sim.marca) || regole.find((r) => r.tipologia === sim.tipologia && r.marca === "*");
  let simPrezzo = null;
  if (regola) {
    const c = sim.tipologia === "software" ? 0 : num(sim.costo);
    let p = 5 * Math.round(((c * (1 + num(regola.ricarico_pct) / 100) + num(regola.manodopera)) * 1.22) / 5);
    if (num(regola.prezzo_min) && (sim.tipologia === "software" || c * 1.22 < num(regola.prezzo_min))) p = Math.max(p, num(regola.prezzo_min));
    if (num(regola.prezzo_max) && c * 1.22 + num(regola.manodopera) * 1.22 <= num(regola.prezzo_max)) p = Math.min(p, num(regola.prezzo_max));
    simPrezzo = { prezzo: p, margine: p / 1.22 - c - 2 };
  }
  return (
    <div className="space-y-4" data-testid="regole-prezzi">
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2">Tipologia</th><th className="px-3 py-2">Marca</th><th className="px-3 py-2">Etichetta</th><th className="px-3 py-2">Manodopera €</th><th className="px-3 py-2">Ricarico %</th><th className="px-3 py-2">Min €</th><th className="px-3 py-2">Max €</th><th /></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {regole.map((r, i) => (
              <tr key={r.id || i} data-testid={`regola-${i}`}>
                <td className="px-3 py-1.5"><Select value={r.tipologia} onValueChange={(v) => upd(i, "tipologia", v)}><SelectTrigger className="h-8 w-40"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(tipologie).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></td>
                <td className="px-3 py-1.5"><Select value={r.marca} onValueChange={(v) => upd(i, "marca", v)}><SelectTrigger className="h-8 w-36"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(MARCHE).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></td>
                <td className="px-3 py-1.5"><Input className="h-8" value={r.label} onChange={(e) => upd(i, "label", e.target.value)} data-testid={`regola-label-${i}`} /></td>
                <td className="px-3 py-1.5"><Input className="h-8 w-20" type="number" step="1" value={r.manodopera} onChange={(e) => upd(i, "manodopera", e.target.value)} data-testid={`regola-manodopera-${i}`} /></td>
                <td className="px-3 py-1.5"><Input className="h-8 w-20" type="number" step="1" value={r.ricarico_pct} onChange={(e) => upd(i, "ricarico_pct", e.target.value)} data-testid={`regola-ricarico-${i}`} /></td>
                <td className="px-3 py-1.5"><Input className="h-8 w-20" type="number" step="5" value={r.prezzo_min} onChange={(e) => upd(i, "prezzo_min", e.target.value)} /></td>
                <td className="px-3 py-1.5"><Input className="h-8 w-20" type="number" step="5" value={r.prezzo_max} onChange={(e) => upd(i, "prezzo_max", e.target.value)} /></td>
                <td className="px-2"><Button variant="ghost" size="icon" onClick={() => setRegole((rs) => rs.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4 text-rose-500" /></Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" className="gap-2" onClick={() => setRegole((rs) => [...rs, { tipologia: "altro", marca: "*", label: "Nuova regola", manodopera: 30, ricarico_pct: 70, prezzo_min: 0, prezzo_max: 0 }])} data-testid="regola-add"><Plus className="h-4 w-4" /> Aggiungi regola</Button>
        <Button className="gap-2 bg-slate-900 hover:bg-slate-800" onClick={save} data-testid="regole-save"><Save className="h-4 w-4" /> Salva regole</Button>
      </div>
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4" data-testid="simulatore">
        <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-900"><Calculator className="h-4 w-4" /> Simulatore prezzo</p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1"><Label className="text-xs">Tipologia</Label><Select value={sim.tipologia} onValueChange={(v) => setSim({ ...sim, tipologia: v })}><SelectTrigger className="h-8 w-44" data-testid="sim-tipologia"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(tipologie).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1"><Label className="text-xs">Marca</Label><Select value={sim.marca} onValueChange={(v) => setSim({ ...sim, marca: v })}><SelectTrigger className="h-8 w-36"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(MARCHE).filter(([k]) => k !== "*").map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1"><Label className="text-xs">Costo ricambio netto €</Label><Input className="h-8 w-28" type="number" value={sim.costo} onChange={(e) => setSim({ ...sim, costo: e.target.value })} data-testid="sim-costo" /></div>
          {simPrezzo && <div className="ml-auto text-right"><p className="text-xs text-emerald-700">Prezzo consigliato al cliente</p><p className="font-heading text-2xl font-bold text-emerald-900" data-testid="sim-prezzo">€ {simPrezzo.prezzo.toFixed(2)}</p><p className="text-xs text-emerald-700">margine netto € {simPrezzo.margine.toFixed(2)}</p></div>}
        </div>
      </div>
    </div>
  );
}

function Listino() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const [parsed, setParsed] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/listino", { params: { q, limit: 100 } }).then((r) => setRows(r.data)).catch(() => {});
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await api.post("/listino/parse-fattura", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setParsed({ ...r.data, righe: r.data.righe.map((x) => ({ ...x, fornitore: r.data.fornitore || "Sifar", data_fattura: r.data.data_fattura, keep: true })) });
      if (!r.data.righe.length) toast.warning("Nessuna riga con prezzo riconosciuta: il PDF potrebbe essere un'immagine scannerizzata");
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };
  const saveParsed = async () => {
    const righe = parsed.righe.filter((r) => r.keep && r.descrizione && r.prezzo_netto > 0).map(({ keep, qty_hint, ...r }) => ({ ...r, prezzo_netto: num(r.prezzo_netto) }));
    try { const r = await api.post("/listino", righe); toast.success(`${r.data.salvate} righe salvate nel listino`); setParsed(null); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const updP = (i, k, v) => setParsed((p) => ({ ...p, righe: p.righe.map((r, j) => (j === i ? { ...r, [k]: v } : r)) }));

  return (
    <div className="space-y-4" data-testid="listino">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
          <Upload className="h-4 w-4" /> {busy ? "Lettura fattura..." : "Carica fattura fornitore (PDF)"}
          <input type="file" accept="application/pdf" className="hidden" onChange={(e) => upload(e.target.files?.[0])} data-testid="listino-upload" />
        </label>
        <div className="relative flex-1 min-w-[240px]"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-9" placeholder="Cerca nel listino..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="listino-search" /></div>
      </div>
      {parsed && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4" data-testid="listino-parsed">
          <p className="mb-2 text-sm font-semibold text-slate-900">Righe riconosciute: {parsed.righe.length} — controlla prezzo e descrizione, togli la spunta a quelle da scartare</p>
          <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-xs">
              <tbody className="divide-y divide-slate-100">
                {parsed.righe.map((r, i) => (
                  <tr key={i} className={r.keep ? "" : "opacity-40"}>
                    <td className="px-2 py-1"><input type="checkbox" checked={r.keep} onChange={(e) => updP(i, "keep", e.target.checked)} data-testid={`parsed-keep-${i}`} /></td>
                    <td className="px-2 py-1"><Input className="h-7 w-28 font-mono text-xs" value={r.codice} onChange={(e) => updP(i, "codice", e.target.value)} /></td>
                    <td className="px-2 py-1"><Input className="h-7 text-xs" value={r.descrizione} onChange={(e) => updP(i, "descrizione", e.target.value)} /></td>
                    <td className="px-2 py-1"><Input className="h-7 w-24 text-xs" type="number" step="0.01" value={r.prezzo_netto} onChange={(e) => updP(i, "prezzo_netto", e.target.value)} data-testid={`parsed-prezzo-${i}`} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setParsed(null)}>Annulla</Button>
            <Button className="bg-slate-900 hover:bg-slate-800" onClick={saveParsed} data-testid="listino-save-parsed">Salva nel listino</Button>
          </div>
        </div>
      )}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"><th className="px-3 py-2">Codice</th><th className="px-3 py-2">Descrizione</th><th className="px-3 py-2">Tipologia</th><th className="px-3 py-2">Fornitore</th><th className="px-3 py-2">Prezzo netto</th><th /></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={r.id} data-testid={`listino-row-${r.id}`}>
                <td className="px-3 py-1.5 font-mono text-xs text-slate-500">{r.codice || "-"}</td><td className="px-3 py-1.5">{r.descrizione}</td>
                <td className="px-3 py-1.5 text-xs text-slate-500">{r.tipologia}{r.marca && r.marca !== "altri" ? ` · ${r.marca}` : ""}</td><td className="px-3 py-1.5 text-xs">{r.fornitore}{r.data_fattura ? ` · ${r.data_fattura}` : ""}</td>
                <td className="px-3 py-1.5 font-semibold">€ {r.prezzo_netto.toFixed(2)}</td>
                <td className="px-2"><Button variant="ghost" size="icon" onClick={() => api.delete(`/listino/${r.id}`).then(load)}><Trash2 className="h-4 w-4 text-rose-500" /></Button></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6} className="px-3 py-8 text-center text-xs text-slate-400" data-testid="listino-empty">Listino vuoto: carica una fattura PDF del fornitore per popolarlo.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function PrezziRiparazioni() {
  const [tab, setTab] = useState("regole");
  return (
    <div className="space-y-6" data-testid="prezzi-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Prezzi riparazioni</h1>
        <p className="mt-1 text-sm text-slate-500">Regole per tipologia e marca usate per il prezzo consigliato e il margine reale, e listino ricambi dei fornitori.</p>
      </div>
      <div className="flex gap-2 border-b border-slate-200">
        {[["regole", "Regole prezzi"], ["listino", "Listino fornitori"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${tab === k ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-900"}`} data-testid={`prezzi-tab-${k}`}>{l}</button>
        ))}
      </div>
      {tab === "regole" ? <Regole /> : <Listino />}
    </div>
  );
}
