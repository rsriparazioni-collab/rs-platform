import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, PackageCheck } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

export default function DaOrdinare({ onChanged }) {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get("/magazzino/da-ordinare").then((r) => setItems(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const arrivo = async (m) => {
    try {
      const r = await api.post(`/magazzino/${m.id}/arrivo`, { quantita: m.da_ordinare || 1 });
      toast.success(r.data.riparazioni_sbloccate?.length ? `Arrivato: riparazioni ${r.data.riparazioni_sbloccate.join(", ")} in lavorazione` : "Arrivo registrato");
      load(); onChanged?.();
    } catch (e) { toast.error(apiError(e)); }
  };

  if (items.length === 0) return null;
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-4" data-testid="da-ordinare-card">
      <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-rose-800"><AlertTriangle className="h-4 w-4" /> Ricambi da ordinare ({items.length})</p>
      <div className="grid gap-2 md:grid-cols-2">
        {items.map((m, i) => (
          <div key={m.id} className="flex items-center justify-between rounded-lg border border-rose-100 bg-white px-3 py-2 text-sm" data-testid={`da-ordinare-row-${i}`}>
            <div>
              <p className="font-medium text-slate-900">{m.nome} <span className="text-xs font-semibold text-rose-700">x{m.da_ordinare}</span></p>
              <p className="text-[11px] text-slate-500">{m.store_name}{m.ordine_servizio_numero ? ` · riparazione ${m.ordine_servizio_numero}` : ""}{m.ordine_at ? ` · dal ${new Date(m.ordine_at).toLocaleDateString("it-IT")}` : ""}</p>
            </div>
            <Button size="sm" variant="outline" className="h-7 gap-1 border-emerald-300 text-xs text-emerald-700" onClick={() => arrivo(m)} data-testid={`da-ordinare-arrivo-${i}`}>
              <PackageCheck className="h-3.5 w-3.5" /> Arrivato
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
