import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, Landmark } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI, PeriodoPicker, eur } from "./shared";

const CERT = { certo: ["Verificato (dati AdE)", "bg-emerald-100 text-emerald-800"], incompleto: ["Incompleto", "bg-amber-100 text-amber-800"], mancante: ["Dato mancante", "bg-rose-100 text-rose-800"], nessun_dato: ["Nessun dato", "bg-slate-100 text-slate-600"] };
export const Badge = ({ certezza }) => { const m = CERT[certezza] || ["—", "bg-slate-100 text-slate-600"]; return <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${m[1]}`} data-testid={`iva-badge-${certezza}`}>{m[0]}</span>; };

const Riga = ({ label, value, sub, bold, testid, nd }) => (
  <div className="flex items-baseline justify-between gap-3 py-1" data-testid={testid}>
    <span className={`text-sm ${bold ? "font-semibold text-slate-900" : "text-slate-600"}`}>{label}{sub && <span className="ml-1 text-xs text-slate-400">{sub}</span>}</span>
    <span className={`tabular-nums ${bold ? "text-base font-bold text-slate-900" : "text-sm text-slate-800"}`}>{nd ? <span className="text-xs font-medium text-rose-700">non determinabile</span> : eur(value)}</span>
  </div>
);

const Aliquote = ({ righe, testid }) => (
  <table className="mt-1 w-full text-xs" data-testid={testid}>
    <thead><tr className="text-left text-[10px] uppercase text-slate-400"><th className="py-0.5">Aliquota / natura</th><th className="py-0.5 text-right">Imponibile</th><th className="py-0.5 text-right">IVA</th><th className="py-0.5 text-right">Fonte</th></tr></thead>
    <tbody>{righe.map((a, i) => (
      <tr key={i} className={`border-t border-slate-100 ${a.aliquota == null || a.natura === "da_verificare" ? "bg-rose-50" : ""}`}>
        <td className="py-0.5">{a.label}{a.n ? <span className="ml-1 text-slate-400">({a.n} doc.)</span> : null}</td>
        <td className="py-0.5 text-right tabular-nums">{eur(a.imponibile)}</td><td className="py-0.5 text-right tabular-nums">{eur(a.imposta)}</td>
        <td className="py-0.5 text-right text-slate-400">{(a.fonte || []).join(", ")}</td>
      </tr>))}
      {!righe.length && <tr><td colSpan={4} className="py-1 text-slate-400">Nessun dato</td></tr>}
    </tbody>
  </table>
);

const NATURE = ["esente", "non_imponibile", "esclusa", "non_soggetta", "forfettario", "reverse_charge", "regime_margine", "iva_altro_stato", "imponibile"];

export const IvaDashboard = ({ anno, mese, setAnno, setMese, isAdmin, centroId: centroFisso, compatto }) => {
  const [centri, setCentri] = useState([]);
  const [centroId, setCentroId] = useState(centroFisso || "");
  const [d, setD] = useState(null);
  const [credito, setCredito] = useState("");
  const [rett, setRett] = useState("");
  useEffect(() => { if (centroFisso) { setCentroId(centroFisso); return; } api.get("/contabilita/pdp/centri").then((r) => { setCentri(r.data); setCentroId((c) => c || r.data[0]?.id || ""); }).catch(() => {}); }, [centroFisso]);
  const load = useCallback(() => { if (!centroId) return; api.get("/contabilita/iva", { params: { centro_id: centroId, anno, mese } }).then((r) => { setD(r.data); setCredito(r.data.credito_fonte === "manuale" ? String(r.data.credito_precedente) : ""); setRett(r.data.rettifiche ? String(r.data.rettifiche) : ""); }).catch((e) => toast.error(apiError(e))); }, [centroId, anno, mese]);
  useEffect(() => { load(); }, [load]);
  if (!d) return <p className="text-sm text-slate-500" data-testid="iva-loading">Caricamento IVA…</p>;
  const v = d.vendite, a = d.acquisti, corr = v.corrispettivi;
  const salva = async () => { try { const r = await api.put("/contabilita/iva", { credito_precedente: credito === "" ? null : parseFloat(credito), rettifiche: rett === "" ? null : parseFloat(rett), note: d.note || "" }, { params: { centro_id: centroId, anno, mese } }); setD(r.data); toast.success("Liquidazione aggiornata"); } catch (e) { toast.error(apiError(e)); } };
  const setPeriodicita = async (p) => { try { await api.put("/contabilita/iva/config", { periodicita: p }, { params: { centro_id: centroId } }); load(); } catch (e) { toast.error(apiError(e)); } };
  const setNatura = async (id, natura) => { try { await api.patch(`/contabilita/pdp/fatture/${id}/natura`, { natura_iva: natura }); toast.success("Natura IVA registrata"); load(); } catch (e) { toast.error(apiError(e)); } };
  const certVendite = corr.negozi.some((n) => n.certezza === "mancante") ? "mancante" : corr.negozi.some((n) => n.certezza === "incompleto") ? "incompleto" : "certo";
  return (
    <div className="space-y-4" data-testid="iva-dashboard">
      <div className="flex flex-wrap items-center gap-2">
        {!centroFisso && <select value={centroId} onChange={(e) => setCentroId(e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" data-testid="iva-centro-select">{centri.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select>}
        {!compatto && <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />}
        {compatto && <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900"><Landmark className="h-4 w-4" /> IVA {MESI[mese]} {anno} <Badge certezza={d.certezza} /></h3>}
        <span className="ml-auto flex items-center gap-2 text-xs text-slate-500">Periodicità:
          {["mensile", "trimestrale"].map((p) => <button key={p} type="button" onClick={() => setPeriodicita(p)} className={`rounded-full border px-2.5 py-0.5 ${d.periodicita === p ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-slate-200"}`} data-testid={`iva-periodicita-${p}`}>{p}</button>)}
          {!d.periodicita && <span className="text-rose-600">non impostata</span>}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="iva-card-vendite">
          <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-900">Vendite · IVA a debito</h3><Badge certezza={certVendite} /></div>
          <Riga label="Imponibile corrispettivi" sub="RT AdE" value={corr.imponibile} testid="iva-corr-imponibile" />
          <Riga label="IVA corrispettivi" sub="RT AdE" value={corr.imposta} testid="iva-corr-imposta" />
          {corr.non_determinabile_lordo > 0 && <Riga label="Scontrini senza RT (lordo)" sub="IVA non conteggiata" value={corr.non_determinabile_lordo} nd testid="iva-corr-nd" />}
          <Riga label="Imponibile fatture emesse" sub={`${v.fatture_emesse.n} doc.${v.fatture_emesse.note_credito.n ? ` · ${v.fatture_emesse.note_credito.n} note di credito` : ""}`} value={v.fatture_emesse.imponibile} testid="iva-emesse-imponibile" />
          <Riga label="IVA fatture emesse" value={v.fatture_emesse.imposta} testid="iva-emesse-imposta" />
          {v.fatture_emesse.note_credito.n > 0 && <Riga label="di cui note di credito" sub="già sottratte" value={v.fatture_emesse.note_credito.totale} testid="iva-emesse-nc" />}
          <div className="my-1 border-t border-slate-100" />
          <Riga label="Imponibile vendite" value={v.imponibile_totale} bold testid="iva-vendite-imponibile" nd={!v.determinabile && !v.imponibile_totale} />
          <Riga label="IVA a debito" sub={v.determinabile ? "" : "parziale"} value={v.iva_debito} bold testid="iva-debito" />
          <Aliquote righe={v.per_aliquota} testid="iva-vendite-aliquote" />
          <div className="mt-2 space-y-1">{corr.negozi.map((n) => (
            <div key={n.store_id} className="rounded-md border border-slate-100 bg-slate-50 px-2 py-1 text-[11px] text-slate-600" data-testid={`iva-negozio-${n.store_id}`}>
              <div className="flex flex-wrap items-center gap-1.5"><b className="text-slate-800">{n.store_nome}</b> <Badge certezza={n.certezza} /> copertura RT <b>{n.giorni_rt}/{n.giorni_attesi} gg</b>{n.copertura_pct != null && ` (${n.copertura_pct}%)`}</div>
              {n.giorni_mancanti_rt.length > 0 && <div className="text-rose-700" data-testid={`iva-negozio-mancanti-${n.store_id}`}>{n.giorni_mancanti_rt.length} gg senza RT: {n.giorni_mancanti_rt.map((g) => g.data.slice(8)).join(", ")} → € {n.non_determinabile_lordo.toFixed(2)} non conteggiati</div>}
              {n.giorni_discordanti.length > 0 && <div className="text-amber-700">{n.giorni_discordanti.length} gg discordanti: {n.giorni_discordanti.map((g) => `${g.data.slice(8)} (${eur(g.scontrini)} vs RT ${eur(g.rt)})`).join(", ")}</div>}
              {n.giorni_solo_rt.length > 0 && <div className="text-slate-500">{n.giorni_solo_rt.length} gg solo RT: {n.giorni_solo_rt.map((g) => g.data.slice(8)).join(", ")}</div>}
            </div>))}</div>
          {v.fatture_manuali.non_riconciliate.length > 0 && <div className="mt-2 rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[11px] text-rose-800" data-testid="iva-manuali-non-riconciliate">Fatture nelle chiusure senza documento AdE ({v.fatture_manuali.non_riconciliate.length}): {v.fatture_manuali.non_riconciliate.map((x) => `${x.store_nome} ${x.data.slice(8)}/${x.data.slice(5, 7)} n.${x.numero || "?"} ${eur(x.importo)}`).join(" · ")}</div>}
          {v.fatture_manuali.riconciliate.length > 0 && <p className="mt-1 text-[11px] text-emerald-700" data-testid="iva-manuali-riconciliate">{v.fatture_manuali.riconciliate.length} fatture delle chiusure riconciliate con l'AdE (non sommate due volte)</p>}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="iva-card-acquisti">
          <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-900">Acquisti · IVA detraibile</h3><Badge certezza={a.fatture_ricevute.n ? (a.fatture_ricevute.anomalie.some((x) => x.tipo === "natura_da_verificare") ? "incompleto" : "certo") : "mancante"} /></div>
          <Riga label="Imponibile acquisti" sub={`${a.fatture_ricevute.n} doc.${a.fatture_ricevute.note_credito.n ? ` · ${a.fatture_ricevute.note_credito.n} note di credito` : ""}`} value={a.imponibile_totale} testid="iva-acquisti-imponibile" />
          <Riga label="IVA sugli acquisti" value={a.iva_totale} testid="iva-acquisti-iva" />
          {a.iva_indetraibile > 0 && <Riga label="IVA indetraibile" sub="limiti art. 19-bis1 (da verificare)" value={-a.iva_indetraibile} testid="iva-indetraibile" />}
          <div className="my-1 border-t border-slate-100" />
          <Riga label="IVA potenzialmente detraibile" value={a.iva_detraibile} bold testid="iva-detraibile" />
          <Aliquote righe={a.fatture_ricevute.per_aliquota} testid="iva-acquisti-aliquote" />
        </div>

        <div className={`rounded-xl border p-4 ${d.saldo > 0 ? "border-rose-200 bg-rose-50/40" : "border-emerald-200 bg-emerald-50/40"}`} data-testid="iva-card-saldo">
          <div className="mb-2 flex items-center justify-between"><h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900"><Landmark className="h-4 w-4" /> Liquidazione {MESI[mese]} {anno}</h3><Badge certezza={d.certezza} /></div>
          <Riga label="IVA a debito" value={v.iva_debito} />
          <Riga label="− IVA detraibile" value={-a.iva_detraibile} />
          <Riga label="− Credito periodo precedente" sub={{ riporto_automatico: "riporto automatico", riporto_automatico_incompleto: "riporto da mese incompleto", manuale: "inserito" }[d.credito_fonte] || "nessuno"} value={-d.credito_precedente} testid="iva-credito-prec" />
          {d.rettifiche !== 0 && <Riga label="± Rettifiche" sub="inserite" value={d.rettifiche} testid="iva-rettifiche" />}
          <div className="my-1 border-t border-slate-200" />
          <Riga label={d.saldo > 0 ? "IVA da versare (stima)" : d.saldo < 0 ? "Credito IVA (stima)" : "Saldo IVA"} value={Math.abs(d.saldo)} bold testid="iva-saldo" />
          {d.interessi_trimestrale > 0 && <Riga label="Interessi 1% (trimestrale)" value={d.interessi_trimestrale} />}
          <p className="mt-1 text-xs text-slate-500" data-testid="iva-scadenza">{d.scadenza ? <>Scadenza F24: <b>{d.scadenza.split("-").reverse().join("/")}</b> · {d.scadenza_nota}</> : <span className="text-rose-600">Scadenza non calcolata: imposta la periodicità</span>}</p>
          {d.iva_foglio != null && <p className="mt-1 text-xs text-slate-500" data-testid="iva-foglio">Foglio Google: IVA {eur(d.iva_foglio)} · differenza {eur(d.saldo - d.iva_foglio)}</p>}
          {isAdmin && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input type="number" step="0.01" placeholder="Credito precedente (€)" value={credito} onChange={(e) => setCredito(e.target.value)} className="h-8 w-40 rounded-md border border-slate-300 bg-white px-2 text-xs" data-testid="iva-credito-input" />
              <input type="number" step="0.01" placeholder="Rettifiche ± (€)" value={rett} onChange={(e) => setRett(e.target.value)} className="h-8 w-32 rounded-md border border-slate-300 bg-white px-2 text-xs" data-testid="iva-rettifiche-input" />
              <Button size="sm" variant="outline" className="h-8 text-xs" onClick={salva} data-testid="iva-credito-salva">Salva</Button>
            </div>)}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4" data-testid="iva-mancanti">
          <h4 className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-amber-900"><HelpCircle className="h-4 w-4" /> Dati mancanti e differenze da riconciliare ({d.mancanti.length})</h4>
          {d.mancanti.length ? <ul className="list-disc space-y-0.5 pl-5 text-xs text-amber-900">{d.mancanti.map((m, i) => <li key={i}>{m}</li>)}</ul> : <p className="flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> Tutti i dati del mese sono presenti</p>}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="iva-anomalie">
          <h4 className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-slate-900"><AlertTriangle className="h-4 w-4 text-rose-600" /> Documenti da controllare ({d.anomalie.length})</h4>
          <div className="max-h-72 space-y-1 overflow-y-auto text-xs">
            {d.anomalie.map((x, i) => (
              <div key={i} className="rounded border border-slate-100 px-2 py-1" data-testid={`iva-anomalia-${x.tipo}`}>
                <b className="text-slate-800">{x.doc}</b> · imp. {eur(x.imponibile)} · IVA {eur(x.imposta)}{x.detraibile != null && <> · detraibile {eur(x.detraibile)}</>}
                <div className="text-slate-500">{x.msg}</div>
                {x.tipo === "natura_da_verificare" && isAdmin && (
                  <select defaultValue="" onChange={(e) => e.target.value && setNatura(x.id, e.target.value)} className="mt-1 h-7 rounded border border-slate-300 bg-white px-1.5 text-[11px]" data-testid={`iva-natura-select-${x.id}`}>
                    <option value="">Imposta natura IVA…</option>{NATURE.map((n) => <option key={n} value={n}>{d.nature_label[n]}</option>)}
                  </select>)}
              </div>))}
            {!d.anomalie.length && <p className="text-slate-400">Nessuna anomalia</p>}
          </div>
        </div>
      </div>
      <p className="text-[11px] text-slate-400">Regole: corrispettivi solo da RT AdE (i giorni senza RT non vengono stimati né azzerati: restano "non determinabili"); fatture dall'AdE con aliquota implicita e natura N1–N7 quando presente, altrimenti "da verificare"; note di credito sottratte; detraibilità 100% salvo limiti art. 19-bis1 segnalati; reverse charge segnalato per integrazione, non calcolato. Il saldo è gestionale e non sostituisce la liquidazione del commercialista.</p>
    </div>
  );
};
