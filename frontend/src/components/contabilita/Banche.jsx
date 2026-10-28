import { useCallback, useEffect, useState } from "react";
import { Landmark, Upload, Trash2, Mail, Eye, Send } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Checkbox } from "../ui/checkbox";
import { PeriodoPicker, eur } from "./shared";

const ContoCard = ({ c, onUploaded }) => {
  const [busy, setBusy] = useState(false);
  const up = async (e) => {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    const fd = new FormData(); fd.append("conto_id", c.id); fd.append("file", file);
    setBusy(true);
    try { const r = await api.post("/banche/upload", fd); toast.success(`${c.nome}: ${r.data.nuovi} movimenti nuovi, ${r.data.gia_presenti} già presenti (${r.data.dal} → ${r.data.al})`); onUploaded(); } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };
  return (
    <label className={`flex cursor-pointer items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-sky-50 ${c.tipo === "pos" ? "border-violet-200 bg-violet-50/40" : "border-slate-200 bg-white"}`} data-testid={`conto-${c.id}`}>
      <span><b>{c.nome}</b><span className="ml-1 text-xs text-slate-500">{c.tipo === "pos" ? "· POS (solo controllo)" : "· banca"}</span>
        <div className="text-[11px] text-slate-400">{c.movimenti} movimenti{c.ultimo_movimento ? ` · ultimo ${c.ultimo_movimento}` : ""}</div></span>
      <span className="flex items-center gap-1 text-xs text-sky-700"><Upload className="h-3.5 w-3.5" /> {busy ? "…" : "Carica PDF/CSV/XLSX"}</span>
      <input type="file" accept=".pdf,.csv,.xlsx,.xls,application/pdf,text/csv" className="hidden" onChange={up} disabled={busy} data-testid={`conto-file-${c.id}`} />
    </label>
  );
};

export const Banche = ({ anno, mese, setAnno, setMese, centri = [] }) => {
  const [conti, setConti] = useState([]);
  const [entita, setEntita] = useState("ditta");
  const [ric, setRic] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [anteprima, setAnteprima] = useState(null);
  const loadConti = useCallback(() => api.get("/banche/conti").then((r) => setConti(r.data)).catch(() => {}), []);
  const loadRic = useCallback(() => api.get("/banche/riconciliazione", { params: { entita, anno, mese } }).then((r) => setRic(r.data)).catch((e) => toast.error(apiError(e))), [entita, anno, mese]);
  const loadCfg = useCallback(() => api.get("/report-commercialista/config").then((r) => setCfg(r.data)).catch(() => {}), []);
  useEffect(() => { loadConti(); loadCfg(); }, [loadConti, loadCfg]);
  useEffect(() => { loadRic(); }, [loadRic]);
  const salvaCfg = async () => { try { await api.put("/report-commercialista/config", { destinatari: cfg.destinatari, invio_automatico: cfg.invio_automatico }); toast.success("Commercialisti salvati"); loadCfg(); } catch (e) { toast.error(apiError(e)); } };
  const vedi = async (cid) => { try { const r = await api.get("/report-commercialista", { params: { centro_id: cid, anno, mese } }); setAnteprima(r.data); } catch (e) { toast.error(apiError(e)); } };
  const invia = async (cid) => {
    if (!window.confirm(`Inviare il riepilogo di ${mese}/${anno} al commercialista di ${centri.find((c) => c.id === cid)?.nome}?`)) return;
    try { await api.post("/report-commercialista/invia", { centro_id: cid, anno, mese, to: cfg.destinatari[cid] || "" }); toast.success("Email inviata"); loadCfg(); } catch (e) { toast.error(apiError(e)); }
  };
  const delEstratto = async (id) => { if (!window.confirm("Eliminare questo caricamento e i suoi movimenti?")) return; try { await api.delete(`/banche/estratti/${id}`); loadConti(); loadRic(); } catch (e) { toast.error(apiError(e)); } };
  return (
    <div className="space-y-4" data-testid="banche-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><Landmark className="h-5 w-5 text-sky-600" /> Estratti conto & riconciliazione</h2>
        <div className="flex items-center gap-2">
          <select value={entita} onChange={(e) => setEntita(e.target.value)} className="h-9 rounded-lg border border-slate-200 px-2 text-sm" data-testid="banche-entita"><option value="ditta">Ditta Enrico Mangani</option><option value="srls">RS Riparazioni SRLS</option></select>
          <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
        </div>
      </div>
      <div className="grid gap-2 md:grid-cols-2">{conti.filter((c) => c.entita === entita).map((c) => <ContoCard key={c.id} c={c} onUploaded={() => { loadConti(); loadRic(); }} />)}</div>
      {ric && (
        <>
          <p className="text-xs text-slate-500">{ric.nota}</p>
          <div className="grid gap-2 sm:grid-cols-4 text-sm">
            {[["POS dichiarato (chiusure)", ric.totali.pos_chiusure], ["Transazioni Nexi/myPOS", ric.totali.pos_transazioni], ["Accrediti POS in banca", ric.totali.accrediti_banca], ["Commissioni stimate", ric.totali.commissioni_stimate]].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-slate-200 bg-white p-2"><div className="text-[11px] uppercase text-slate-500">{k}</div><div className="font-bold" data-testid={`ric-${k.split(" ")[0].toLowerCase()}`}>{v === null ? "—" : eur(v)}</div></div>
            ))}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white"><div className="border-b px-3 py-2 text-sm font-semibold">POS per giorno</div>
              <div className="max-h-80 overflow-y-auto"><table className="w-full text-xs"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-2 py-1 text-left">Giorno</th><th className="px-2 py-1 text-right">Chiusure</th><th className="px-2 py-1 text-right">Transazioni</th><th className="px-2 py-1 text-right">In banca</th><th className="px-2 py-1 text-right">Diff</th></tr></thead>
                <tbody>{ric.giorni.map((g) => <tr key={g.data} className={`border-t ${g.ok === false ? "bg-rose-50" : ""}`} data-testid={`ric-giorno-${g.data}`}><td className="px-2 py-1 font-mono">{g.data.slice(5)}</td><td className="px-2 py-1 text-right">{eur(g.pos_chiusure)}</td><td className="px-2 py-1 text-right">{g.pos_transazioni ? eur(g.pos_transazioni) : "—"}</td><td className="px-2 py-1 text-right">{g.accrediti_banca ? eur(g.accrediti_banca) : "—"}</td><td className={`px-2 py-1 text-right ${g.ok === false ? "font-semibold text-rose-700" : "text-slate-400"}`}>{g.ok === null ? "n.d." : eur(g.diff_transazioni)}</td></tr>)}</tbody></table></div></div>
            <div className="space-y-3">
              <div className="rounded-xl border border-slate-200 bg-white"><div className="border-b px-3 py-2 text-sm font-semibold">Fatture ricevute AdE pagate in banca <span className="text-emerald-700">{ric.fatture_pagate.length}</span> · non trovate <span className="text-amber-700">{ric.fatture_non_trovate_in_banca.length}</span></div>
                <div className="max-h-40 overflow-y-auto px-3 py-1 text-xs">{ric.fatture_pagate.map((p, i) => <div key={i} className="flex justify-between border-t py-1"><span>{p.fattura.controparte}</span><span>{eur(p.fattura.totale)} · {p.movimento.data}</span></div>)}{!ric.fatture_pagate.length && <p className="py-2 text-slate-400">Nessun abbinamento (carica gli estratti del conto banca).</p>}</div></div>
              <div className="rounded-xl border border-slate-200 bg-white"><div className="border-b px-3 py-2 text-sm font-semibold">Caricamenti del mese</div>
                <div className="px-3 py-1 text-xs">{ric.estratti_caricati.map((e) => <div key={e.id} className="flex items-center justify-between border-t py-1"><span>{conti.find((c) => c.id === e.conto_id)?.nome} · {e.file} · {e.righe} righe ({e.dal} → {e.al})</span><button type="button" onClick={() => delEstratto(e.id)} className="text-rose-500 hover:text-rose-700" title="Elimina caricamento" data-testid={`estratto-del-${e.id}`}><Trash2 className="h-3.5 w-3.5" /></button></div>)}{!ric.estratti_caricati.length && <p className="py-2 text-slate-400">Nessun estratto caricato per questo mese.</p>}</div></div>
            </div>
          </div>
        </>
      )}
      {cfg && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3" data-testid="report-commercialisti">
          <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800"><Mail className="h-4 w-4 text-emerald-700" /> Report mensile ai commercialisti (automatico il 1° del mese)</h3>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {cfg.centri.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm">
                <span className="w-40 truncate font-medium">{c.nome}</span>
                <Input placeholder="email commercialista" value={cfg.destinatari[c.id] || ""} onChange={(e) => setCfg((x) => ({ ...x, destinatari: { ...x.destinatari, [c.id]: e.target.value } }))} className="h-8 flex-1 text-xs" data-testid={`comm-email-${c.id}`} />
                <Button size="sm" variant="ghost" className="h-8 text-xs" onClick={() => vedi(c.id)} data-testid={`comm-anteprima-${c.id}`}><Eye className="mr-1 h-3 w-3" /> Anteprima</Button>
                <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => invia(c.id)} disabled={!cfg.destinatari[c.id]} data-testid={`comm-invia-${c.id}`}><Send className="mr-1 h-3 w-3" /> Invia ora</Button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-2"><Checkbox data-testid="comm-auto" checked={cfg.invio_automatico} onCheckedChange={(v) => setCfg((x) => ({ ...x, invio_automatico: !!v }))} /> Invio automatico il 1° del mese</label>
            <Button size="sm" className="h-7 text-xs" onClick={salvaCfg} data-testid="comm-save">Salva</Button>
            {cfg.ultimi_invii?.[0] && <span className="text-slate-500">Ultimo invio: {cfg.ultimi_invii[0].at.slice(0, 16).replace("T", " ")} → {cfg.ultimi_invii[0].to}</span>}
          </div>
          {anteprima && <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3"><div className="flex justify-between"><b className="text-sm">Anteprima email</b><button type="button" className="text-xs text-slate-500" onClick={() => setAnteprima(null)}>chiudi</button></div><div className="prose prose-sm mt-2 max-w-none text-xs" data-testid="comm-anteprima-html" dangerouslySetInnerHTML={{ __html: anteprima.html }} /></div>}
        </div>
      )}
    </div>
  );
};
