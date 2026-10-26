import { useCallback, useEffect, useState } from "react";
import { Trophy, Settings2, FileCheck2, Calculator, FlaskConical, Scale, Image as ImageIcon, History, Rocket, Lock } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { IncentiviRegole } from "../components/incentivi/IncentiviRegole";
import { IncentiviInPagamento } from "../components/incentivi/IncentiviInPagamento";
import { IncentiviCalcolo } from "../components/incentivi/IncentiviCalcolo";
import { IncentiviSimulazione } from "../components/incentivi/IncentiviSimulazione";
import { IncentiviEstrattoConto } from "../components/incentivi/IncentiviEstrattoConto";
import { IncentiviSoglie } from "../components/incentivi/IncentiviSoglie";
import { IncentiviStorico } from "../components/incentivi/IncentiviStorico";
import { VaiOnlineDialog } from "../components/incentivi/VaiOnlineDialog";

const oggi = new Date();
export const meseDefault = `${oggi.getFullYear()}-${String(oggi.getMonth() + 1).padStart(2, "0")}`;

export default function Incentivi() {
  const [cfg, setCfg] = useState(null);
  const [meta, setMeta] = useState(null);
  const [mese, setMese] = useState(meseDefault);
  const [onlineOpen, setOnlineOpen] = useState(false);
  const load = useCallback(() => Promise.all([api.get("/incentivi/config"), api.get("/incentivi/meta")]).then(([c, m]) => { setCfg(c.data); setMeta(m.data); }).catch((e) => toast.error(apiError(e))), []);
  useEffect(() => { load(); }, [load]);

  const toggleOnline = async () => {
    if (!cfg.online) return setOnlineOpen(true);
    if (!window.confirm("Nascondere di nuovo la gara ai partecipanti?")) return;
    try { await api.post("/incentivi/online", { online: false }); toast.success("Incentivi nascosti ai partecipanti"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  if (!cfg || !meta) return <p className="text-sm text-slate-500" data-testid="incentivi-loading">Caricamento…</p>;
  return (
    <div className="space-y-6" data-testid="incentivi-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Incentivi RS</h1>
          <p className="mt-1 text-sm text-slate-500">Fondo premi autofinanziato da EOLO ed energia, gettoni per contratto, classifica mensile, simulazione e estratti conto negozi esterni.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${cfg.online ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="incentivi-stato-online">
            {cfg.online ? "ONLINE – visibile ai ragazzi" : "BOZZA – visibile solo a te"}
          </span>
          <Button onClick={toggleOnline} variant={cfg.online ? "outline" : "default"} className="gap-2" data-testid="incentivi-vai-online">
            {cfg.online ? <><Lock className="h-4 w-4" /> Torna in bozza</> : <><Rocket className="h-4 w-4" /> Vai online</>}
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-600">Mese di liquidazione</label>
        <input type="month" value={mese} onChange={(e) => setMese(e.target.value)} className="h-9 rounded-md border border-slate-200 px-2 text-sm" data-testid="incentivi-mese" />
      </div>
      <Tabs defaultValue="calcolo">
        <TabsList className="flex-wrap">
          <TabsTrigger value="calcolo" className="gap-1.5" data-testid="inc-tab-calcolo"><Calculator className="h-4 w-4" /> Fondo & classifica</TabsTrigger>
          <TabsTrigger value="pagamento" className="gap-1.5" data-testid="inc-tab-pagamento"><FileCheck2 className="h-4 w-4" /> In pagamento</TabsTrigger>
          <TabsTrigger value="simulazione" className="gap-1.5" data-testid="inc-tab-simulazione"><FlaskConical className="h-4 w-4" /> Simulazione</TabsTrigger>
          <TabsTrigger value="estratto" className="gap-1.5" data-testid="inc-tab-estratto"><Scale className="h-4 w-4" /> Estratti conto</TabsTrigger>
          <TabsTrigger value="soglie" className="gap-1.5" data-testid="inc-tab-soglie"><ImageIcon className="h-4 w-4" /> Gara EOLO</TabsTrigger>
          <TabsTrigger value="regole" className="gap-1.5" data-testid="inc-tab-regole"><Settings2 className="h-4 w-4" /> Regole</TabsTrigger>
          <TabsTrigger value="storico" className="gap-1.5" data-testid="inc-tab-storico"><History className="h-4 w-4" /> Storico</TabsTrigger>
        </TabsList>
        <TabsContent value="calcolo"><IncentiviCalcolo mese={mese} /></TabsContent>
        <TabsContent value="pagamento"><IncentiviInPagamento mese={mese} meta={meta} /></TabsContent>
        <TabsContent value="simulazione"><IncentiviSimulazione mese={mese} cfg={cfg} /></TabsContent>
        <TabsContent value="estratto"><IncentiviEstrattoConto mese={mese} meta={meta} /></TabsContent>
        <TabsContent value="soglie"><IncentiviSoglie mese={mese} /></TabsContent>
        <TabsContent value="regole"><IncentiviRegole cfg={cfg} meta={meta} reload={load} /></TabsContent>
        <TabsContent value="storico"><IncentiviStorico /></TabsContent>
      </Tabs>
      <p className="flex items-center gap-2 text-xs text-slate-400"><Trophy className="h-3.5 w-3.5" /> Nessun pagamento automatico: i premi vanno confermati con la chiusura mese e verificati con consulente del lavoro e commercialista.</p>
      <VaiOnlineDialog open={onlineOpen} onOpenChange={setOnlineOpen} onDone={load} />
    </div>
  );
}
