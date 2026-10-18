import { useCallback, useEffect, useState } from "react";
import { Receipt, Scale, TrendingUp, Settings2, Activity, Landmark } from "lucide-react";
import api from "../lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Corrispettivi } from "../components/contabilita/Corrispettivi";
import { IvaDashboard } from "../components/contabilita/IvaDashboard";
import { PuntoPareggio } from "../components/contabilita/PuntoPareggio";
import { ReportAnnuale } from "../components/contabilita/ReportAnnuale";
import { ContabilitaImpostazioni } from "../components/contabilita/ContabilitaImpostazioni";
import { NuovoNegozioDialog } from "../components/contabilita/NuovoNegozioDialog";

const oggi = new Date();

export default function Contabilita() {
  const [meta, setMeta] = useState(null);
  const [storeId, setStoreId] = useState("");
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const loadMeta = useCallback(() => api.get("/contabilita/meta").then((r) => {
    setMeta(r.data);
    setStoreId((cur) => cur || (r.data.stores.find((s) => s.completo) || {}).id || "");
  }).catch(() => {}), []);
  useEffect(() => { loadMeta(); }, [loadMeta]);

  if (!meta) return <div className="p-6 text-sm text-slate-500" data-testid="contabilita-loading">Caricamento…</div>;
  const completi = meta.stores.filter((s) => s.completo);
  const soloStato = meta.stores.filter((s) => !s.completo);
  const periodo = { storeId, anno, mese, setAnno, setMese };

  return (
    <div className="space-y-6" data-testid="contabilita-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Corrispettivi & Contabilità</h1>
          <p className="mt-1 text-sm text-slate-500">Corrispettivi giornalieri, spese di cassa, punto di pareggio e andamento del fatturato per negozio.</p>
        </div>
        <div className="flex items-center gap-2">
          {meta.is_admin && <NuovoNegozioDialog onCreated={(id) => { setStoreId(id); loadMeta(); }} />}
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
        <Tabs defaultValue="corrispettivi">
          <TabsList className="flex-wrap">
            <TabsTrigger value="corrispettivi" className="gap-1.5" data-testid="contabilita-tab-corrispettivi"><Receipt className="h-4 w-4" /> Corrispettivi</TabsTrigger>
            <TabsTrigger value="pdp" className="gap-1.5" data-testid="contabilita-tab-pdp"><Scale className="h-4 w-4" /> Punto di pareggio</TabsTrigger>
            <TabsTrigger value="iva" className="gap-1.5" data-testid="contabilita-tab-iva"><Landmark className="h-4 w-4" /> IVA</TabsTrigger>
            <TabsTrigger value="report" className="gap-1.5" data-testid="contabilita-tab-report"><TrendingUp className="h-4 w-4" /> Report fatturato</TabsTrigger>
            <TabsTrigger value="impostazioni" className="gap-1.5" data-testid="contabilita-tab-impostazioni"><Settings2 className="h-4 w-4" /> Invii e impostazioni</TabsTrigger>
          </TabsList>
          <TabsContent value="corrispettivi"><Corrispettivi {...periodo} isAdmin={meta.is_admin} stores={meta.stores} /></TabsContent>
          <TabsContent value="pdp"><PuntoPareggio {...periodo} isAdmin={meta.is_admin} /></TabsContent>
          <TabsContent value="iva"><IvaDashboard {...periodo} isAdmin={meta.is_admin} /></TabsContent>
          <TabsContent value="report"><ReportAnnuale storeId={storeId} anno={anno} setAnno={setAnno} isAdmin={meta.is_admin} /></TabsContent>
          <TabsContent value="impostazioni"><ContabilitaImpostazioni meta={meta} storeId={storeId} reload={loadMeta} /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}
