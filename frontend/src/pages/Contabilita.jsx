import { useCallback, useEffect, useState } from "react";
import { Receipt, Table2, Activity, ChevronDown } from "lucide-react";
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
import { PdpSpecchio } from "../components/contabilita/PdpSpecchio";

const oggi = new Date();
// vecchie schede → nuova scheda (per i link "Vai" della chiusura mese e del riquadro Cose da sistemare)
const MAPPA_TAB = { corrispettivi: ["cassa", null], pdp: ["pdp", null], iva: ["altro", "iva"], estere: ["altro", "estere"], banche: ["altro", "banche"], scadenzario: ["altro", "scadenzario"], chiusura: ["altro", "chiusura"], fiscale: ["altro", "fiscale"], report: ["altro", "report"], impostazioni: ["altro", "impostazioni"], analisi: ["altro", "conto"] };
const ALTRO = [["banche", "Banca & fatture AdE", true], ["estere", "Fatture estere", true], ["scadenzario", "Scadenzario", false], ["chiusura", "Chiusura mese", true], ["iva", "IVA del mese", false], ["conto", "Conto economico", true], ["report", "Report fatturato", false], ["fiscale", "Pianificazione fiscale", false], ["impostazioni", "Invii e impostazioni", false]];

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
  const [altro, setAltro] = useState("banche");
  const loadMeta = useCallback(() => api.get("/contabilita/meta").then((r) => {
    setMeta(r.data);
    setStoreId((cur) => cur || (r.data.stores.find((s) => s.completo) || {}).id || "");
  }).catch(() => {}), []);
  useEffect(() => { loadMeta(); }, [loadMeta]);
  const [centriEstere, setCentriEstere] = useState([]);
  useEffect(() => { if (meta?.is_admin) api.get("/contabilita/pdp/centri").then((r) => setCentriEstere(r.data)).catch(() => {}); }, [meta?.is_admin]);

  const goTab = (vecchia) => {
    const [t, s] = MAPPA_TAB[vecchia] || ["altro", vecchia];
    setTab(t);
    if (s) setAltro(s);
  };

  if (!meta) return <div className="p-6 text-sm text-slate-500" data-testid="contabilita-loading">Caricamento…</div>;
  const completi = meta.stores.filter((s) => s.completo);
  const soloStato = meta.stores.filter((s) => !s.completo);
  const periodo = { storeId, anno, mese, setAnno, setMese };
  const adm = meta.is_admin;
  const vociAltro = ALTRO.filter(([, , soloAdmin]) => adm || !soloAdmin);
  const altroAttivo = vociAltro.some(([id]) => id === altro) ? altro : vociAltro[0][0];

  return (
    <div className="space-y-6" data-testid="contabilita-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Corrispettivi & Contabilità</h1>
          <p className="mt-1 text-sm text-slate-500">Cassa e corrispettivi dei negozi; il PDP del mese letto dal tuo foglio Google. Tutto il resto sotto "Altro".</p>
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
            {adm && <TabsTrigger value="pdp" className="gap-1.5 px-4 py-2" data-testid="contabilita-tab-pdp"><Table2 className="h-4 w-4" /> PDP del mese</TabsTrigger>}
            <TabsTrigger value="altro" className="gap-1.5 px-4 py-2" data-testid="contabilita-tab-altro"><ChevronDown className="h-4 w-4" /> Altro</TabsTrigger>
          </TabsList>

          <TabsContent value="cassa" className="space-y-4">
            <Corrispettivi {...periodo} isAdmin={adm} stores={meta.stores} goTab={goTab} />
          </TabsContent>

          {adm && (
            <TabsContent value="pdp" className="space-y-4">
              <PdpSpecchio anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
            </TabsContent>
          )}

          <TabsContent value="altro" className="space-y-4">
            <SottoMenu testid="contabilita-sub-altro" valore={altroAttivo} onChange={setAltro} voci={vociAltro.map(([id, label]) => [id, label])} />
            {altroAttivo === "banche" && <Banche anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} centri={centriEstere} />}
            {altroAttivo === "estere" && <FattureEstere anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} centri={centriEstere} />}
            {altroAttivo === "scadenzario" && <Scadenzario anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} centri={centriEstere} isAdmin={adm} />}
            {altroAttivo === "chiusura" && <ChiusuraMese anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} goTab={goTab} />}
            {altroAttivo === "iva" && <IvaDashboard {...periodo} isAdmin={adm} compatto />}
            {altroAttivo === "conto" && <ContoEconomico anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />}
            {altroAttivo === "report" && <ReportAnnuale storeId={storeId} anno={anno} setAnno={setAnno} isAdmin={adm} />}
            {altroAttivo === "fiscale" && <PianoFiscale anno={anno} setAnno={setAnno} isAdmin={adm} />}
            {altroAttivo === "impostazioni" && <ContabilitaImpostazioni meta={meta} storeId={storeId} reload={loadMeta} />}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
