import { useCallback, useEffect, useState } from "react";
import { Receipt, Landmark, CalendarClock, TrendingUp, Activity } from "lucide-react";
import api from "../lib/api";
import { FattureEstere } from "../components/contabilita/FattureEstere";
import { Banche } from "../components/contabilita/Banche";
import { Scadenzario } from "../components/contabilita/Scadenzario";
import { ChiusuraMese } from "../components/contabilita/ChiusuraMese";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Corrispettivi } from "../components/contabilita/Corrispettivi";
import { IvaDashboard } from "../components/contabilita/IvaDashboard";
import { PianoFiscale } from "../components/contabilita/PianoFiscale";
import { ContoEconomico } from "../components/contabilita/ContoEconomico";
import { ReportAnnuale } from "../components/contabilita/ReportAnnuale";
import { ContabilitaImpostazioni } from "../components/contabilita/ContabilitaImpostazioni";
import { NuovoNegozioDialog } from "../components/contabilita/NuovoNegozioDialog";

const oggi = new Date();
// vecchie schede → nuova scheda (per i link "Vai" della chiusura mese e del riquadro Cose da sistemare)
const MAPPA_TAB = { corrispettivi: ["cassa", "corrispettivi"], pdp: ["analisi", "pdp"], iva: ["scadenze", null], estere: ["banche", "estere"], banche: ["banche", "banche"], scadenzario: ["scadenze", null], chiusura: ["scadenze", null], fiscale: ["analisi", "fiscale"], report: ["analisi", "report"], impostazioni: ["analisi", "impostazioni"] };

const SottoMenu = ({ voci, valore, onChange, testid }) => (
  <div className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1" data-testid={testid}>
    {voci.map(([id, label]) => (
      <button key={id} type="button" onClick={() => onChange(id)} className={`rounded-md px-3 py-1.5 text-sm transition-colors ${valore === id ? "bg-white font-semibold text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`} data-testid={`${testid}-${id}`}>{label}</button>
    ))}
  </div>
);

export default function Contabilita() {
  const [meta, setMeta] = useState(null);
  const [storeId, setStoreId] = useState("");
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [tab, setTab] = useState("cassa");
  const [sub, setSub] = useState({ cassa: "corrispettivi", banche: "banche", scadenze: "scadenzario", analisi: "pdp" });
  const loadMeta = useCallback(() => api.get("/contabilita/meta").then((r) => {
    setMeta(r.data);
    setStoreId((cur) => cur || (r.data.stores.find((s) => s.completo) || {}).id || "");
  }).catch(() => {}), []);
  useEffect(() => { loadMeta(); }, [loadMeta]);
  const [centriEstere, setCentriEstere] = useState([]);
  useEffect(() => { if (meta?.is_admin) api.get("/contabilita/pdp/centri").then((r) => setCentriEstere(r.data)).catch(() => {}); }, [meta?.is_admin]);

  const goTab = (vecchia) => {
    const [t, s] = MAPPA_TAB[vecchia] || [vecchia, null];
    setTab(t);
    if (s) setSub((cur) => ({ ...cur, [t]: s, ...(s === "fiscale" || s === "impostazioni" ? { analisi: "altro", altro: s } : {}) }));
  };

  if (!meta) return <div className="p-6 text-sm text-slate-500" data-testid="contabilita-loading">Caricamento…</div>;
  const completi = meta.stores.filter((s) => s.completo);
  const soloStato = meta.stores.filter((s) => !s.completo);
  const periodo = { storeId, anno, mese, setAnno, setMese };
  const adm = meta.is_admin;
  const setS = (t) => (v) => setSub((cur) => ({ ...cur, [t]: v }));

  return (
    <div className="space-y-6" data-testid="contabilita-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Corrispettivi & Contabilità</h1>
          <p className="mt-1 text-sm text-slate-500">Cassa e corrispettivi, banche e fatture, scadenze e chiusura mese, analisi: tutto per negozio, con le cose da sistemare in evidenza.</p>
        </div>
        <div className="flex items-center gap-2">
          {adm && <NuovoNegozioDialog onCreated={(id) => { setStoreId(id); loadMeta(); }} />}
          {completi.length > 0 && (
            <select value={storeId} onChange={(e) => setStoreId(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" data-testid="contabilita-store-select">
              {completi.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          )}
        </div>
      </div>
      {soloStato.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="contabilita-stato-altri">
          {soloStato.map((s) => (
            <span key={s.id} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600" data-testid={`store-stato-${s.id}`}>
              <Activity className={`h-3 w-3 ${s.attivo ? "text-emerald-500" : "text-slate-300"}`} />{s.nome}: {s.attivo ? `attivo (ultimo ${s.ultimo_inserimento})` : "non attivo"}
            </span>
          ))}
        </div>
      )}
      {!storeId ? <p className="text-sm text-slate-500" data-testid="contabilita-nessun-negozio">Nessun negozio con corrispettivi condivisi.</p> : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="h-auto flex-wrap">
            <TabsTrigger value="cassa" className="gap-1.5 px-4 py-2" data-testid="contabilita-tab-cassa"><Receipt className="h-4 w-4" /> Cassa & Corrispettivi</TabsTrigger>
            {adm && <TabsTrigger value="banche" className="gap-1.5 px-4 py-2" data-testid="contabilita-tab-banche"><Landmark className="h-4 w-4" /> Banche & Fatture</TabsTrigger>}
            <TabsTrigger value="scadenze" className="gap-1.5 px-4 py-2" data-testid="contabilita-tab-scadenze"><CalendarClock className="h-4 w-4" /> Scadenze, Chiusura & IVA</TabsTrigger>
            <TabsTrigger value="analisi" className="gap-1.5 px-4 py-2" data-testid="contabilita-tab-analisi"><TrendingUp className="h-4 w-4" /> Analisi</TabsTrigger>
          </TabsList>

          <TabsContent value="cassa" className="space-y-4">
            <Corrispettivi {...periodo} isAdmin={adm} stores={meta.stores} goTab={goTab} />
          </TabsContent>

          {adm && (
            <TabsContent value="banche" className="space-y-4">
              <SottoMenu testid="contabilita-sub-banche" valore={sub.banche} onChange={setS("banche")} voci={[["banche", "Banca: estratti, fatture e scadenze"], ["estere", "Fatture estere"]]} />
              {sub.banche === "banche" && <Banche anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} centri={centriEstere} />}
              {sub.banche === "estere" && <FattureEstere anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} centri={centriEstere} />}
            </TabsContent>
          )}

          <TabsContent value="scadenze" className="space-y-4">
            <Scadenzario anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} centri={centriEstere} isAdmin={adm} />
            {adm && <ChiusuraMese anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} goTab={goTab} />}
            <details className="rounded-xl border border-slate-200 bg-white" data-testid="iva-dettaglio">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-900">Dettaglio IVA del mese <span className="text-xs font-normal text-slate-500">(corrispettivi RT, fatture emesse/ricevute, saldo)</span></summary>
              <div className="border-t border-slate-100 p-4"><IvaDashboard {...periodo} isAdmin={adm} compatto /></div>
            </details>
          </TabsContent>

          <TabsContent value="analisi" className="space-y-4">
            <SottoMenu testid="contabilita-sub-analisi" valore={sub.analisi} onChange={setS("analisi")} voci={[["pdp", "Conto economico"], ["report", "Report fatturato"], ["altro", "Altro"]]} />
            {sub.analisi === "pdp" && (adm ? <ContoEconomico anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} /> : <p className="text-sm text-slate-500">Riservato all'amministrazione.</p>)}
            {sub.analisi === "report" && <ReportAnnuale storeId={storeId} anno={anno} setAnno={setAnno} isAdmin={adm} />}
            {(sub.analisi === "altro" || sub.analisi === "fiscale" || sub.analisi === "impostazioni") && (
              <div className="space-y-4">
                <SottoMenu testid="contabilita-sub-altro" valore={sub.altro || "impostazioni"} onChange={setS("altro")} voci={[["impostazioni", "Invii e impostazioni"], ["fiscale", "Pianificazione fiscale"]]} />
                {(sub.altro || "impostazioni") === "impostazioni" && <ContabilitaImpostazioni meta={meta} storeId={storeId} reload={loadMeta} />}
                {sub.altro === "fiscale" && <PianoFiscale anno={anno} setAnno={setAnno} isAdmin={adm} />}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
