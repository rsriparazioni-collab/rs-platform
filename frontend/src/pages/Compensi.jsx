import { useCallback, useEffect, useState } from "react";
import { Euro, Settings2, Wallet, Percent, FileSpreadsheet, Trophy } from "lucide-react";
import api from "../lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { CompensiCalcolo } from "../components/compensi/CompensiCalcolo";
import { CompensiRegole } from "../components/compensi/CompensiRegole";
import { CompensiTrattenute } from "../components/compensi/CompensiTrattenute";
import { CompensiPlafond } from "../components/compensi/CompensiPlafond";
import { CompensiRicariche } from "../components/compensi/CompensiRicariche";
import { GaraWindTre } from "../components/compensi/GaraWindTre";

export default function Compensi() {
  const [meta, setMeta] = useState(null);
  const loadMeta = useCallback(() => api.get("/compensi/meta").then((r) => setMeta(r.data)).catch(() => {}), []);
  useEffect(() => { loadMeta(); }, [loadMeta]);

  return (
    <div className="space-y-6" data-testid="compensi-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Compensi</h1>
        <p className="mt-1 text-sm text-slate-500">Calcolo mensile in euro dei compensi maturati da negozi e venditori, regole modificabili nel tempo, gare, trattenute e plafond ricariche.</p>
      </div>
      <Tabs defaultValue="calcolo">
        <TabsList className="flex-wrap">
          <TabsTrigger value="calcolo" className="gap-1.5" data-testid="compensi-tab-calcolo"><Euro className="h-4 w-4" /> Calcolo mensile</TabsTrigger>
          <TabsTrigger value="regole" className="gap-1.5" data-testid="compensi-tab-regole"><Settings2 className="h-4 w-4" /> Regole e gare</TabsTrigger>
          <TabsTrigger value="trattenute" className="gap-1.5" data-testid="compensi-tab-trattenute"><Percent className="h-4 w-4" /> Trattenute</TabsTrigger>
          <TabsTrigger value="plafond" className="gap-1.5" data-testid="compensi-tab-plafond"><Wallet className="h-4 w-4" /> Plafond</TabsTrigger>
          <TabsTrigger value="ricariche" className="gap-1.5" data-testid="compensi-tab-ricariche"><FileSpreadsheet className="h-4 w-4" /> Ricariche (CSV)</TabsTrigger>
          <TabsTrigger value="gara" className="gap-1.5" data-testid="compensi-tab-gara"><Trophy className="h-4 w-4" /> Gara WindTre</TabsTrigger>
        </TabsList>
        <TabsContent value="gara"><GaraWindTre /></TabsContent>
        <TabsContent value="ricariche">{meta && <CompensiRicariche meta={meta} />}</TabsContent>
        <TabsContent value="calcolo"><CompensiCalcolo /></TabsContent>
        <TabsContent value="regole">{meta && <CompensiRegole meta={meta} />}</TabsContent>
        <TabsContent value="trattenute">{meta && <CompensiTrattenute meta={meta} reload={loadMeta} />}</TabsContent>
        <TabsContent value="plafond">{meta && <CompensiPlafond meta={meta} />}</TabsContent>
      </Tabs>
    </div>
  );
}
