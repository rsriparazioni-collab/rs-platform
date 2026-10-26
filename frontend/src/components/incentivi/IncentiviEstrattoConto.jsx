import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { eur } from "./IncentiviCalcolo";

export const IncentiviEstrattoConto = ({ mese, meta }) => {
  const [d, setD] = useState(null);
  const [nuova, setNuova] = useState({ store_id: "", societa: "ditta", categoria: "riparazioni", descrizione: "", importo: "" });
  useEffect(() => {
    let attivo = true;
    api.get(`/incentivi/calcolo?mese=${mese}`).then((r) => { if (attivo) setD(r.data); }).catch((e) => toast.error(apiError(e)));
    return () => { attivo = false; };
  }, [mese]);
  const load = useCallback(() => api.get(`/incentivi/calcolo?mese=${mese}`).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [mese]);
  const add = async () => {
    if (!nuova.store_id || !nuova.importo) return toast.error("Negozio e importo obbligatori");
    try { await api.post("/incentivi/compensazioni", { ...nuova, mese, importo: parseFloat(nuova.importo) }); toast.success("Compensazione aggiunta"); setNuova({ ...nuova, descrizione: "", importo: "" }); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const del = async (id) => { try { await api.delete(`/incentivi/compensazioni/${id}`); load(); } catch (e) { toast.error(apiError(e)); } };
  const pagato = async (e, societa, v) => { try { await api.post("/incentivi/estratto-conto/pagato", { mese, store_id: e.store_id, societa, pagato: v }); load(); } catch (err) { toast.error(apiError(err)); } };
  if (!d) return <p className="text-sm text-slate-500">Caricamento…</p>;
  return (
    <div className="space-y-4" data-testid="inc-estratti">
      <p className="text-sm text-slate-600">Negozi fuori dal fondo (terzi e SRLS): <b>dare</b> = provvigioni confermate − trattenuta {d.parametri.trattenuta_terzi_pct}% (EOLO fatturato alla ditta; energia solo per i terzi). <b>Avere</b> = riparazioni, ricariche, SIM che il negozio deve alla ditta o alla SRLS. Le quote girate sono spesa nel PDP al pagamento, mai margine.</p>
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <h4 className="text-sm font-semibold">Aggiungi compensazione (avere)</h4>
        <div className="mt-2 grid gap-2 md:grid-cols-6">
          <select className="h-9 rounded-md border border-slate-200 px-2 text-sm" value={nuova.store_id} onChange={(e) => setNuova({ ...nuova, store_id: e.target.value })} data-testid="inc-comp-store"><option value="">Negozio…</option>{meta.stores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}</select>
          <select className="h-9 rounded-md border border-slate-200 px-2 text-sm" value={nuova.societa} onChange={(e) => setNuova({ ...nuova, societa: e.target.value })} data-testid="inc-comp-societa"><option value="ditta">Dovuto alla ditta individuale</option><option value="srls">Dovuto alla SRLS</option></select>
          <select className="h-9 rounded-md border border-slate-200 px-2 text-sm" value={nuova.categoria} onChange={(e) => setNuova({ ...nuova, categoria: e.target.value })}><option value="riparazioni">Riparazioni</option><option value="ricariche">Ricariche SIM</option><option value="sim">SIM</option><option value="altro">Altro</option></select>
          <Input placeholder="Descrizione" value={nuova.descrizione} onChange={(e) => setNuova({ ...nuova, descrizione: e.target.value })} data-testid="inc-comp-desc" />
          <Input type="number" step="0.5" placeholder="€" value={nuova.importo} onChange={(e) => setNuova({ ...nuova, importo: e.target.value })} data-testid="inc-comp-importo" />
          <Button size="sm" onClick={add} data-testid="inc-comp-add"><Plus className="h-4 w-4" /> Aggiungi</Button>
        </div>
      </div>
      {d.estratti_conto.map((e) => (
        <div key={e.store_id} className="rounded-xl border border-slate-200 bg-white" data-testid={`inc-estratto-${e.store_id}`}>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div><span className="font-semibold text-slate-900">{e.negozio}</span> <span className="text-xs text-slate-500">({e.entita}) · {e.n_contratti} contratti · EOLO {eur(e.eolo_lordo)} · energia {eur(e.energia_lordo)} · trattenuta {eur(e.trattenuta)}</span>{e.nota && <p className="text-xs text-amber-700">{e.nota}</p>}</div>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span>Saldo <b>ditta</b>: <b className={e.saldo_ditta >= 0 ? "text-emerald-700" : "text-red-600"}>{eur(e.saldo_ditta)}</b> <label className="ml-1 text-xs"><input type="checkbox" checked={e.pagato_ditta} onChange={(ev) => pagato(e, "ditta", ev.target.checked)} data-testid={`inc-pagato-ditta-${e.store_id}`} /> pagato</label></span>
              <span>Saldo <b>SRLS</b>: <b className={e.saldo_srls >= 0 ? "text-emerald-700" : "text-red-600"}>{eur(e.saldo_srls)}</b> <label className="ml-1 text-xs"><input type="checkbox" checked={e.pagato_srls} onChange={(ev) => pagato(e, "srls", ev.target.checked)} data-testid={`inc-pagato-srls-${e.store_id}`} /> pagato</label></span>
            </div>
          </div>
          <div className="grid gap-3 p-4 md:grid-cols-2 text-xs">
            <div><p className="mb-1 font-semibold uppercase text-slate-500">Dare (provvigioni − trattenuta)</p>{e.righe.map((r, i) => <div key={i} className={`flex justify-between ${r.stato === "stornata" ? "text-red-600" : ""}`}><span>{r.data} · {r.fonte.toUpperCase()} · {r.descrizione}</span><span>{eur(r.importo)} → <b>{eur(r.netto)}</b></span></div>)}</div>
            <div><p className="mb-1 font-semibold uppercase text-slate-500">Avere (compensazioni)</p>{e.compensazioni.map((c) => <div key={c.id} className="flex justify-between"><span>{c.categoria} · {c.descrizione} <i className="text-slate-400">→ {c.societa}</i></span><span>{eur(c.importo)} <button onClick={() => del(c.id)} className="ml-1 text-slate-400 hover:text-red-600" data-testid={`inc-comp-del-${c.id}`}><Trash2 className="inline h-3 w-3" /></button></span></div>)}{!e.compensazioni.length && <p className="text-slate-400">—</p>}</div>
          </div>
        </div>))}
      {!d.estratti_conto.length && <p className="text-sm text-slate-400">Nessuna provvigione di negozi esterni nel mese.</p>}
    </div>
  );
};
