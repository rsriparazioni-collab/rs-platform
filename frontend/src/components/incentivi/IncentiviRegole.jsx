import { useEffect, useState } from "react";
import { Save, ArrowLeftRight, FileText, MessageCircle, PenLine } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

const NUM = [["gettone_lordo", "Gettone lordo per contratto €", "Uguale per EOLO ed energia, in busta lordo"], ["eolo_fondo_pct", "% EOLO al fondo", "Dopo il gettone: resto all'azienda"], ["costo_datore_fattore", "Fattore costo datore", "≈1,45: contributi, TFR, ratei — da verificare col consulente"],
  ["energia_importo", "Provvigione energia €", "CambiaOra / ENEL"], ["energia_acquisizione", "Energia: quota acquisizione €", "al negozio del cliente"], ["energia_lavorazione", "Energia: quota lavorazione €", "a chi fa la pratica"], ["trattenuta_terzi_pct", "Trattenuta negozi terzi / SRLS su EOLO %", ""],
  ["coef_eolo", "Coeff. classifica EOLO %", ""], ["coef_energia", "Coeff. classifica energia %", ""], ["coef_riparazione", "Coeff. classifica riparazioni % (sul margine)", "prezzo − ricambio, solo consegnate"], ["valore_sim_nuova", "Valore SIM nuova €", "figurativo, solo classifica"], ["valore_sim_mnp", "Valore SIM MNP €", ""], ["valore_fisso", "Valore fisso/internet non EOLO €", ""], ["bonus_squadra_pct", "Premio squadra: % dell'eccedenza sul miglior fondo 6 mesi (0 = spento)", "pagato dalla quota azienda EOLO, diviso in parti uguali a chi ha valore > 0"], ["tetto_fondo", "Tetto fondo mensile € (0 = nessuno)", ""]];

export const IncentiviRegole = ({ cfg, meta, reload }) => {
  const [f, setF] = useState(cfg);
  const [premi, setPremi] = useState(cfg.premi_pct.join("/"));
  const [log, setLog] = useState([]);
  const [ent, setEnt] = useState({ store_id: "", entita: "srls", da: "" });
  const [firme, setFirme] = useState([]);
  useEffect(() => { setF(cfg); setPremi(cfg.premi_pct.join("/")); api.get("/incentivi/config/log").then((r) => setLog(r.data)).catch(() => {}); api.get("/incentivi/firme").then((r) => setFirme(r.data)).catch(() => {}); }, [cfg]);

  const salva = async () => {
    const body = Object.fromEntries(NUM.map(([k]) => [k, parseFloat(f[k]) || 0]));
    body.premi_pct = premi.split("/").map((x) => parseFloat(x) || 0); body.partecipanti = f.partecipanti; body.negozi_fondo = f.negozi_fondo; body.padre_in_fondo = f.padre_in_fondo; body.persona_negozio = f.persona_negozio || {};
    try { await api.put("/incentivi/config", body); toast.success("Regole salvate (modifica registrata)"); reload(); } catch (e) { toast.error(apiError(e)); }
  };
  const cambiaEntita = async () => {
    if (!ent.store_id) return toast.error("Scegli il negozio");
    if (!window.confirm(`Dal ${ent.da || "inizio"} ${meta.stores.find((s) => s.id === ent.store_id)?.nome} appartiene a ${ent.entita === "srls" ? "RS Riparazioni SRLS" : "ditta individuale"}. Confermi?`)) return;
    try { await api.post("/incentivi/entita", ent); toast.success("Entità aggiornata"); reload(); } catch (e) { toast.error(apiError(e)); }
  };
  const toggle = (k, id) => setF({ ...f, [k]: f[k].includes(id) ? f[k].filter((x) => x !== id) : [...f[k], id] });

  return (
    <div className="space-y-4" data-testid="inc-regole">
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {NUM.map(([k, l, h]) => <label key={k} className="rounded-xl border border-slate-200 bg-white p-3 text-sm"><span className="font-medium text-slate-800">{l}</span><Input type="number" step="0.5" className="mt-1" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`inc-cfg-${k}`} />{h && <span className="text-xs text-slate-500">{h}</span>}</label>)}
        <label className="rounded-xl border border-slate-200 bg-white p-3 text-sm"><span className="font-medium text-slate-800">Premi % del fondo (1º/2º/3º…)</span><Input className="mt-1" value={premi} onChange={(e) => setPremi(e.target.value)} data-testid="inc-cfg-premi" /><span className="text-xs text-slate-500">es. 50/30/20 — ex aequo: premio diviso</span></label>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm"><p className="font-medium text-slate-800">Partecipanti alla gara</p><div className="mt-2 flex flex-wrap gap-2">{meta.users.filter((u) => u.role !== "admin").map((u) => <label key={u.id} className={`cursor-pointer rounded-full border px-3 py-1 ${f.partecipanti.includes(u.id) ? "border-emerald-400 bg-emerald-50" : "border-slate-200"}`}><input type="checkbox" className="mr-1" checked={f.partecipanti.includes(u.id)} onChange={() => toggle("partecipanti", u.id)} data-testid={`inc-part-${u.id}`} />{u.name}</label>)}</div></div>
        <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm"><p className="font-medium text-slate-800">Negozi che alimentano il fondo</p><div className="mt-2 flex flex-wrap gap-2">{meta.stores.map((s) => <label key={s.id} className={`cursor-pointer rounded-full border px-3 py-1 ${f.negozi_fondo.includes(s.id) ? "border-emerald-400 bg-emerald-50" : "border-slate-200"}`}><input type="checkbox" className="mr-1" checked={f.negozi_fondo.includes(s.id)} onChange={() => toggle("negozi_fondo", s.id)} data-testid={`inc-fondo-${s.id}`} />{s.nome}</label>)}
          <label className={`cursor-pointer rounded-full border px-3 py-1 ${f.padre_in_fondo ? "border-emerald-400 bg-emerald-50" : "border-slate-200"}`}><input type="checkbox" className="mr-1" checked={!!f.padre_in_fondo} onChange={() => setF({ ...f, padre_in_fondo: !f.padre_in_fondo })} data-testid="inc-fondo-padre" />Codice PADRE (foglio)</label></div></div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm" data-testid="inc-persona-negozio">
        <p className="font-medium text-slate-800">Persona predefinita per negozio</p>
        <p className="text-xs text-slate-500">Usata quando una provvigione non ha il venditore (es. righe importate dal foglio): il contratto viene attribuito a questa persona per gettone e classifica.</p>
        <div className="mt-2 flex flex-wrap gap-2">{meta.stores.map((s) => <label key={s.id} className="flex items-center gap-1 text-xs"><span className="w-20 text-slate-600">{s.nome}</span><select className="h-8 rounded-md border border-slate-200 px-1" value={(f.persona_negozio || {})[s.id] || ""} onChange={(e) => setF({ ...f, persona_negozio: { ...(f.persona_negozio || {}), [s.id]: e.target.value } })} data-testid={`inc-pn-${s.id}`}><option value="">—</option>{meta.users.filter((u) => f.partecipanti.includes(u.id)).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>)}</div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={salva} className="gap-2" data-testid="inc-cfg-salva"><Save className="h-4 w-4" /> Salva regole</Button>
        <Button variant="outline" className="gap-2" onClick={() => downloadBlob("/incentivi/regolamento.pdf", "regolamento_incentivi_rs.pdf")} data-testid="inc-regolamento-pdf"><FileText className="h-4 w-4" /> Regolamento PDF da firmare</Button>
        <Button variant="outline" className="gap-2" onClick={async () => { if (!window.confirm("Inviare ora il WhatsApp di classifica ai partecipanti con numero di telefono? (solo se il modulo è online)")) return; try { const r = await api.post("/incentivi/invia-classifica"); toast.success(`Inviati: ${r.data.inviati}${r.data.motivo ? " – " + r.data.motivo : ""}`); } catch (e) { toast.error(apiError(e)); } }} data-testid="inc-invia-classifica"><MessageCircle className="h-4 w-4" /> Invia classifica WhatsApp ora</Button>
        <Button variant="outline" className="gap-2" onClick={async () => { if (!window.confirm("Inviare ora all'amministrazione il riepilogo WhatsApp del mese scorso (fondo, classifica, premi)?")) return; try { const r = await api.post("/incentivi/invia-riepilogo"); toast.success(`Riepilogo ${r.data.mese} inviato`); } catch (e) { toast.error(apiError(e)); } }} data-testid="inc-invia-riepilogo"><MessageCircle className="h-4 w-4" /> Riepilogo mese ad amministrazione</Button>
        <Button variant="outline" className="gap-2" onClick={async () => { if (!window.confirm("Inviare su WhatsApp il link di firma del regolamento ai partecipanti che non hanno ancora firmato?")) return; try { const r = await api.post("/incentivi/firme/invia"); toast.success(`Link inviati: ${r.data.inviati}${r.data.senza_telefono.length ? " – senza telefono: " + r.data.senza_telefono.join(", ") : ""}`); api.get("/incentivi/firme").then((x) => setFirme(x.data)); } catch (e) { toast.error(apiError(e)); } }} data-testid="inc-firme-invia"><PenLine className="h-4 w-4" /> Invia regolamento da firmare</Button>
      </div>
      {!!firme.length && <div className="flex flex-wrap gap-2 text-xs" data-testid="inc-firme-stato">{firme.map((f) => <span key={f.user_id} className={`rounded-full border px-2 py-0.5 ${f.stato === "firmata" ? "border-emerald-300 bg-emerald-50 text-emerald-800" : f.stato ? "border-amber-300 bg-amber-50 text-amber-800" : "border-slate-200 text-slate-500"}`}>{f.nome}: {f.stato === "firmata" ? `firmato ${(f.firmato_at || "").slice(0, 10)}` : f.stato ? "in attesa di firma" : "link non inviato"}</span>)}</div>}

      <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm" data-testid="inc-entita">
        <p className="flex items-center gap-2 font-medium text-slate-800"><ArrowLeftRight className="h-4 w-4" /> Società per negozio (tasto cambia entità)</p>
        <p className="text-xs text-slate-500">Attuale: {cfg.entita.map((e) => `${meta.stores.find((s) => s.id === e.store_id)?.nome || "?"} → ${e.entita}${e.da ? ` dal ${e.da}` : ""}`).join(" · ")}. Negozi senza regola = terzi.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <select className="h-9 rounded-md border border-slate-200 px-2" value={ent.store_id} onChange={(e) => setEnt({ ...ent, store_id: e.target.value })} data-testid="inc-ent-store"><option value="">Negozio…</option>{meta.stores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}</select>
          <select className="h-9 rounded-md border border-slate-200 px-2" value={ent.entita} onChange={(e) => setEnt({ ...ent, entita: e.target.value })} data-testid="inc-ent-tipo"><option value="srls">RS Riparazioni SRLS</option><option value="ditta">Ditta individuale</option></select>
          <input type="month" className="h-9 rounded-md border border-slate-200 px-2" value={ent.da} onChange={(e) => setEnt({ ...ent, da: e.target.value })} data-testid="inc-ent-da" />
          <Button variant="outline" onClick={cambiaEntita} data-testid="inc-ent-salva">Applica da questa data</Button>
        </div>
      </div>
      <details className="rounded-xl border border-slate-200 bg-white p-3 text-xs"><summary className="cursor-pointer font-medium">Registro modifiche regole ({log.length})</summary>
        {log.map((l) => <div key={l.id} className="mt-1 border-t border-slate-100 pt-1">{l.at.slice(0, 16).replace("T", " ")} · {l.user_name}: {Object.entries(l.modifiche).map(([k, v]) => `${k}: ${JSON.stringify(v.prima)} → ${JSON.stringify(v.dopo)}`).join("; ")}</div>)}</details>
    </div>
  );
};
