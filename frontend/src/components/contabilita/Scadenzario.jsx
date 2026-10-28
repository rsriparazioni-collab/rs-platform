import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Plus, Trash2, CheckCircle2, Circle, BellRing } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { PeriodoPicker, eur } from "./shared";

const fmt = (d) => d.split("-").reverse().join("/");

const NuovaScadenza = ({ centri, anno, mese, onSaved }) => {
  const vuoto = { centro_id: centri[0]?.id || "", tipo: "f24", voce: "", importo: "", data: `${anno}-${String(mese).padStart(2, "0")}-16`, ricorrenza: "nessuna", fino_a: "", note: "" };
  const [f, setF] = useState(vuoto);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const salva = async () => {
    if (!f.voce.trim() || !f.importo || !f.data) return toast.error("Compila descrizione, importo e data");
    try { await api.post("/scadenzario", { ...f, importo: Number(f.importo), fino_a: f.fino_a || null }); toast.success("Scadenza aggiunta"); setF(vuoto); onSaved(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="grid gap-2 rounded-xl border border-amber-200 bg-amber-50/50 p-3 text-sm md:grid-cols-8" data-testid="scadenza-form">
      <select value={f.centro_id} onChange={set("centro_id")} className="h-9 rounded-lg border border-slate-200 bg-white px-2" data-testid="scadenza-centro">{centri.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select>
      <select value={f.tipo} onChange={set("tipo")} className="h-9 rounded-lg border border-slate-200 bg-white px-2" data-testid="scadenza-tipo">
        <option value="iva">IVA</option><option value="inps">INPS</option><option value="f24">F24 / imposte</option><option value="affitto">Affitto</option><option value="altro">Altro</option>
      </select>
      <Input value={f.voce} onChange={set("voce")} placeholder="Descrizione (es. Affitto Sondrio)" className="h-9 md:col-span-2" data-testid="scadenza-voce" />
      <Input type="number" step="0.01" value={f.importo} onChange={set("importo")} placeholder="Importo €" className="h-9" data-testid="scadenza-importo" />
      <Input type="date" value={f.data} onChange={set("data")} className="h-9" data-testid="scadenza-data" />
      <select value={f.ricorrenza} onChange={set("ricorrenza")} className="h-9 rounded-lg border border-slate-200 bg-white px-2" data-testid="scadenza-ricorrenza"><option value="nessuna">Una volta</option><option value="mensile">Ogni mese</option></select>
      <Button onClick={salva} className="h-9 gap-1" data-testid="scadenza-salva"><Plus className="h-4 w-4" /> Aggiungi</Button>
      {f.ricorrenza === "mensile" && <div className="flex items-center gap-2 md:col-span-8 text-xs text-slate-600">Fino a (opzionale): <Input type="date" value={f.fino_a} onChange={set("fino_a")} className="h-8 w-44" data-testid="scadenza-fino-a" /> — ogni mese lo stesso giorno della prima data</div>}
    </div>
  );
};

export const Scadenzario = ({ anno, mese, setAnno, setMese, centri = [], isAdmin }) => {
  const [d, setD] = useState(null);
  const [giorni, setGiorni] = useState(5);
  const load = useCallback(() => api.get("/scadenzario", { params: { anno, mese } }).then((r) => { setD(r.data); setGiorni(r.data.giorni_preavviso); }).catch((e) => toast.error(apiError(e))), [anno, mese]);
  useEffect(() => { load(); }, [load]);
  const toggle = async (s) => { try { await api.put(`/scadenzario/${s.id}/pagata`, { pagata: !s.pagata_at }); load(); } catch (e) { toast.error(apiError(e)); } };
  const del = async (s) => { if (!window.confirm(s.template_id ? "Eliminare questa scadenza ricorrente (tutti i mesi)?" : "Eliminare la scadenza?")) return; try { await api.delete(`/scadenzario/${s.id}`); load(); } catch (e) { toast.error(apiError(e)); } };
  const salvaCfg = async () => { try { await api.put("/scadenzario/config", { giorni_preavviso: Number(giorni) }); toast.success("Preavviso salvato"); } catch (e) { toast.error(apiError(e)); } };
  const oggi = new Date().toISOString().slice(0, 10);
  if (!d) return <div className="text-sm text-slate-500">Caricamento…</div>;
  return (
    <div className="space-y-4" data-testid="scadenzario-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><CalendarClock className="h-5 w-5 text-amber-600" /> Scadenzario F24 & affitti</h2>
        <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
      </div>
      <p className="text-xs text-slate-500">{d.nota}</p>
      <div className="grid gap-2 text-sm sm:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-white p-3"><div className="text-xs text-slate-500">Totale mese</div><div className="font-bold tabular-nums" data-testid="scad-totale">{eur(d.totale)}</div></div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3"><div className="text-xs text-amber-700">Ancora da pagare</div><div className="font-bold tabular-nums text-amber-800" data-testid="scad-da-pagare">{eur(d.da_pagare)}</div></div>
        <div className={`rounded-lg border p-3 ${d.scadute ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-white"}`}><div className="text-xs text-slate-500">Scadute non pagate</div><div className="font-bold tabular-nums" data-testid="scad-scadute">{d.scadute}</div></div>
        {isAdmin && <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-3"><BellRing className="h-4 w-4 text-sky-600" /><span className="text-xs text-slate-600">WhatsApp</span><Input type="number" min={1} max={30} value={giorni} onChange={(e) => setGiorni(e.target.value)} className="h-8 w-16" data-testid="scad-giorni" /><span className="text-xs text-slate-600">gg prima</span><Button size="sm" variant="outline" onClick={salvaCfg} className="h-8" data-testid="scad-giorni-salva">Salva</Button></div>}
      </div>
      {isAdmin && centri.length > 0 && <NuovaScadenza centri={centri} anno={anno} mese={mese} onSaved={load} />}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-2">Stato</th><th className="p-2">Data</th><th className="p-2">Centro</th><th className="p-2">Tipo</th><th className="p-2">Descrizione</th><th className="p-2 text-right">Importo</th><th className="p-2"></th></tr></thead>
          <tbody>
            {d.items.length === 0 && <tr><td colSpan={7} className="p-4 text-center text-slate-400" data-testid="scad-vuoto">Nessuna scadenza inserita per questo mese</td></tr>}
            {d.items.map((s) => {
              const late = !s.pagata_at && s.data < oggi;
              return (
                <tr key={s.id} className={`border-t ${s.pagata_at ? "text-slate-400" : late ? "bg-rose-50" : ""}`} data-testid="scad-riga">
                  <td className="p-2">{isAdmin ? <button onClick={() => toggle(s)} title={s.pagata_at ? "Segna non pagata" : "Segna pagata"} data-testid="scad-toggle">{s.pagata_at ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <Circle className="h-5 w-5 text-slate-300" />}</button> : (s.pagata_at ? "Pagata" : "—")}</td>
                  <td className="p-2 tabular-nums">{fmt(s.data)}{late && <span className="ml-1 text-[10px] font-bold text-rose-600">SCADUTA</span>}</td>
                  <td className="p-2">{s.centro_nome}</td>
                  <td className="p-2"><span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{d.tipi[s.tipo] || s.tipo}</span>{s.template_id && <span className="ml-1 text-[10px] text-slate-400">mensile</span>}</td>
                  <td className="p-2">{s.voce}{s.note && <div className="text-xs text-slate-400">{s.note}</div>}</td>
                  <td className="p-2 text-right font-semibold tabular-nums">{eur(s.importo)}</td>
                  <td className="p-2 text-right">{isAdmin && <button onClick={() => del(s)} className="text-slate-400 hover:text-rose-600" data-testid="scad-del"><Trash2 className="h-4 w-4" /></button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {d.stime_piano.length > 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-3 text-sm" data-testid="scad-stime">
          <div className="mb-1 text-xs font-semibold uppercase text-slate-500">Stime dal piano fiscale (non ancora inserite come scadenze reali)</div>
          {d.stime_piano.map((s, i) => <div key={i} className="flex justify-between py-0.5"><span>{fmt(s.data)} · {s.centro_nome} · {s.voce} <span className="text-[10px] uppercase text-slate-400">{s.certezza}</span></span><span className="tabular-nums">{eur(s.importo)}</span></div>)}
        </div>
      )}
    </div>
  );
};
