import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Calculator, Wallet } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI, eur } from "./shared";

const REGIMI = { ditta_individuale: "Ditta individuale (IRPEF + INPS)", srls: "SRLS (IRES + IRAP)" };
const LABEL = { irpef_scaglioni: null, addizionale_regionale_pct: "Addizionale regionale %", addizionale_comunale_pct: "Addizionale comunale %", inps_gestione_pct: "INPS gestione commercianti %", inps_minimale_reddito: "INPS minimale reddito €", inps_contributo_minimo: "INPS contributo minimo annuo €", acconto_pct: "Acconto % (metodo storico)", acconto_prima_rata_pct: "1ª rata acconto %", ires_pct: "IRES %", irap_pct: "IRAP %" };

export const PianoFiscale = ({ anno, setAnno, isAdmin }) => {
  const [centri, setCentri] = useState([]);
  const [centroId, setCentroId] = useState("");
  const [d, setD] = useState(null);
  const [sim, setSim] = useState({ ricavi_pct: 0, costi_pct: 0 });
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/contabilita/pdp/centri").then((r) => { setCentri(r.data); setCentroId((c) => c || r.data[0]?.id || ""); }).catch(() => {}); }, []);
  const load = useCallback(() => { if (!centroId) return; api.get("/contabilita/fiscale", { params: { centro_id: centroId, anno, ...sim } }).then((r) => { setD(r.data); setCfg({ regime: r.data.config.regime, params: r.data.config.params, imposte_anno_prec: r.data.config.imposte_anno_prec ?? "", acconti_versati: r.data.config.acconti_versati || 0 }); }).catch((e) => toast.error(apiError(e))); }, [centroId, anno, sim]);
  useEffect(() => { load(); }, [load]);
  if (!d || !cfg) return <p className="text-sm text-slate-500" data-testid="fiscale-loading">Caricamento…</p>;
  const salvaCfg = async () => { try { await api.put("/contabilita/fiscale/config", { ...cfg, imposte_anno_prec: cfg.imposte_anno_prec === "" ? null : parseFloat(cfg.imposte_anno_prec), acconti_versati: parseFloat(cfg.acconti_versati) || 0 }, { params: { centro_id: centroId } }); toast.success("Parametri fiscali salvati"); load(); } catch (e) { toast.error(apiError(e)); } };
  const setP = (k, v) => setCfg({ ...cfg, params: { ...cfg.params, [k]: parseFloat(v) || 0 } });
  const cambiaRegime = async (r) => { try { await api.put("/contabilita/fiscale/config", { regime: r, params: {}, imposte_anno_prec: null, acconti_versati: 0 }, { params: { centro_id: centroId } }); load(); } catch (e) { toast.error(apiError(e)); } };
  return (
    <div className="space-y-4" data-testid="fiscale-dashboard">
      <div className="flex flex-wrap items-center gap-2">
        <select value={centroId} onChange={(e) => setCentroId(e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" data-testid="fiscale-centro-select">{centri.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select>
        <input type="number" value={anno} onChange={(e) => setAnno(Number(e.target.value))} className="h-9 w-24 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="fiscale-anno" />
        <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs text-indigo-800" data-testid="fiscale-regime">{REGIMI[d.config.regime]}</span>
        {d.config.da_verificare && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800" data-testid="fiscale-da-verificare">Parametri da confermare</span>}
      </div>
      {d.avvertenze.length > 0 && <ul className="list-disc rounded-lg border border-amber-200 bg-amber-50 py-2 pl-7 pr-3 text-xs text-amber-900" data-testid="fiscale-avvertenze">{d.avvertenze.map((a, i) => <li key={i}>{a}</li>)}</ul>}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="fiscale-card-reddito">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-900"><Calculator className="h-4 w-4" /> Reddito e imposte stimate {anno}</h3>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between"><span className="text-slate-600">Ricavi YTD ({d.mesi_con_dati} mesi){d.ytd.netto_iva_tutti_mesi ? " netti IVA" : <span className="text-rose-700"> (lordi in alcuni mesi)</span>}</span><b className="tabular-nums">{eur(d.ytd.ricavi)}</b></div>
            <div className="flex justify-between"><span className="text-slate-600">Costi YTD</span><b className="tabular-nums">{eur(d.ytd.costi)}</b></div>
            <div className="flex justify-between"><span className="text-slate-600">Risultato YTD</span><b className={`tabular-nums ${d.ytd.risultato >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{eur(d.ytd.risultato)}</b></div>
            <div className="my-1 border-t border-slate-100" />
            <div className="flex justify-between"><span className="text-slate-600">Previsione ricavi anno</span><span className="tabular-nums">{eur(d.previsione.ricavi)}</span></div>
            <div className="flex justify-between"><span className="text-slate-600">Previsione costi anno</span><span className="tabular-nums">{eur(d.previsione.costi)}</span></div>
            <div className="flex justify-between"><span className="font-semibold text-slate-900">Reddito imponibile previsto</span><b className="tabular-nums" data-testid="fiscale-reddito">{eur(d.previsione.reddito)}</b></div>
            <div className="my-1 border-t border-slate-100" />
            {Object.entries(d.imposte.voci).map(([k, v]) => <div key={k} className="flex justify-between"><span className="text-slate-600">{k}</span><span className="tabular-nums">{eur(v)}</span></div>)}
            <div className="flex justify-between"><span className="font-semibold text-slate-900">Totale imposte e contributi stimati</span><b className="tabular-nums text-rose-700" data-testid="fiscale-imposte">{eur(d.imposte.totale)}</b></div>
            <p className="text-[11px] text-slate-400">Accantonamento consigliato: {eur(d.accantonamento_mese)}/mese</p>
          </div>
          <div className="mt-3 rounded-lg bg-slate-50 p-2 text-xs" data-testid="fiscale-simulazione">
            <b>Simulazione:</b> ricavi <input type="number" value={sim.ricavi_pct} onChange={(e) => setSim({ ...sim, ricavi_pct: parseFloat(e.target.value) || 0 })} className="mx-1 h-6 w-16 rounded border border-slate-300 px-1" data-testid="fiscale-sim-ricavi" />% · costi <input type="number" value={sim.costi_pct} onChange={(e) => setSim({ ...sim, costi_pct: parseFloat(e.target.value) || 0 })} className="mx-1 h-6 w-16 rounded border border-slate-300 px-1" data-testid="fiscale-sim-costi" />%
          </div>
          <ul className="mt-2 list-disc pl-4 text-[11px] text-slate-400">{d.imposte.regole.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="fiscale-card-scadenze">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-900"><CalendarClock className="h-4 w-4" /> Acconti e scadenze</h3>
          <p className="mb-2 text-xs text-slate-500">Acconto {d.config.params.acconto_pct}% su base {eur(d.acconti.base)} → 1ª rata {eur(d.acconti.prima_rata)} (30/06) · 2ª rata {eur(d.acconti.seconda_rata)} (30/11) · versati {eur(d.acconti.versati)} · saldo stimato {eur(d.acconti.saldo_stimato)}</p>
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-xs"><tbody className="divide-y divide-slate-100">
              {d.scadenze.map((s, i) => <tr key={i} data-testid="fiscale-scadenza"><td className="py-1 text-slate-500">{s.data.split("-").reverse().join("/")}</td><td className="py-1">{s.voce}</td><td className="py-1 text-right tabular-nums">{eur(s.importo)}</td><td className="py-1 pl-2 text-[10px] uppercase text-slate-400">{s.certezza}</td></tr>)}
            </tbody></table>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="fiscale-card-liquidita">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-900"><Wallet className="h-4 w-4" /> Liquidità mensile</h3>
          <p className="mb-1 text-[11px] text-slate-500">Incassato = contanti + POS delle chiusure + fatture emesse AdE (considerate incassate); costi = uscite PDP; IVA = saldo del mese se a debito.</p>
          <table className="w-full text-xs"><thead className="text-[10px] uppercase text-slate-400"><tr><th className="text-left">Mese</th><th className="text-right">Incassato</th><th className="text-right">Costi</th><th className="text-right">IVA</th><th className="text-right">Imposte</th><th className="text-right">Netto</th><th className="text-right">Cumulato</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{d.liquidita.map((l) => <tr key={l.mese} data-testid={`fiscale-liq-${l.mese}`}><td className="py-1">{MESI[l.mese].slice(0, 3)}</td><td className="py-1 text-right tabular-nums">{eur(l.incassato)}</td><td className="py-1 text-right tabular-nums">{eur(l.costi)}</td><td className="py-1 text-right tabular-nums">{eur(l.iva)}</td><td className="py-1 text-right tabular-nums">{eur(l.accantonamento_imposte)}</td><td className={`py-1 text-right tabular-nums ${l.netto >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{eur(l.netto)}</td><td className={`py-1 text-right font-semibold tabular-nums ${l.cumulato >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{eur(l.cumulato)}</td></tr>)}</tbody></table>
        </div>
      </div>

      {isAdmin && (
        <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4" data-testid="fiscale-config">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-900">Parametri fiscali {d.centro.nome}
            <select value={cfg.regime} onChange={(e) => cambiaRegime(e.target.value)} className="h-8 rounded-md border border-slate-300 bg-white px-2 text-xs font-normal" data-testid="fiscale-regime-select">{Object.entries(REGIMI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {Object.entries(cfg.params).filter(([k]) => LABEL[k]).map(([k, v]) => <label key={k} className="text-[11px] text-slate-600">{LABEL[k]}<input type="number" step="0.01" value={v} onChange={(e) => setP(k, e.target.value)} className="mt-0.5 h-8 w-full rounded border border-slate-300 bg-white px-2 text-xs" data-testid={`fiscale-param-${k}`} /></label>)}
            <label className="text-[11px] text-slate-600">Imposte anno precedente € (base acconti storico)<input type="number" step="0.01" value={cfg.imposte_anno_prec} onChange={(e) => setCfg({ ...cfg, imposte_anno_prec: e.target.value })} className="mt-0.5 h-8 w-full rounded border border-slate-300 bg-white px-2 text-xs" data-testid="fiscale-imposte-prec" /></label>
            <label className="text-[11px] text-slate-600">Acconti già versati {anno} €<input type="number" step="0.01" value={cfg.acconti_versati} onChange={(e) => setCfg({ ...cfg, acconti_versati: e.target.value })} className="mt-0.5 h-8 w-full rounded border border-slate-300 bg-white px-2 text-xs" data-testid="fiscale-acconti-versati" /></label>
          </div>
          {cfg.regime === "ditta_individuale" && <p className="mt-1 text-[11px] text-slate-500">Scaglioni IRPEF: {cfg.params.irpef_scaglioni.map(([l, p]) => `${p}% ${l ? `fino a ${eur(l)}` : "oltre"}`).join(" · ")}</p>}
          <Button size="sm" className="mt-2 h-8 text-xs" onClick={salvaCfg} data-testid="fiscale-config-salva">Conferma parametri</Button>
        </div>)}
      <p className="text-[11px] text-slate-400">Stime gestionali su regole dichiarate; non sostituiscono la dichiarazione del commercialista. Dati certi: incassi, costi registrati, IVA da AdE. Stime: proiezione annuale, imposte, acconti.</p>
    </div>
  );
};
