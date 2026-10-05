import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, PackageCheck, Smartphone, User } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

const eur = (v) => `€ ${Number(v || 0).toFixed(2)}`;

export default function DaOrdinare({ onChanged }) {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get("/magazzino/da-ordinare").then((r) => setItems(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const arrivo = async (m) => {
    try {
      const r = await api.post(`/magazzino/${m.id}/arrivo`, { quantita: m.da_ordinare || 1 });
      toast.success(r.data.vendite_pronte?.length ? `Arrivato: cliente avvisato su WhatsApp per ${r.data.vendite_pronte.join(", ")}` : r.data.riparazioni_sbloccate?.length ? `Arrivato: riparazioni ${r.data.riparazioni_sbloccate.join(", ")} in lavorazione` : "Arrivo registrato");
      load(); onChanged?.();
    } catch (e) { toast.error(apiError(e)); }
  };

  if (items.length === 0) return null;
  const clienti = items.filter((m) => m.tipo_ordine === "vendita");
  const ricambi = items.filter((m) => m.tipo_ordine !== "vendita");
  const dal = (m) => (m.ordine_at ? ` · dal ${new Date(m.ordine_at).toLocaleDateString("it-IT")}` : "");
  return (
    <div className="space-y-3" data-testid="da-ordinare-card">
      {clienti.length > 0 && (
        <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4" data-testid="ordinati-clienti-card">
          <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-sky-900"><Smartphone className="h-4 w-4" /> Telefoni ordinati per i clienti ({clienti.length})</p>
          <div className="grid gap-2 md:grid-cols-2">
            {clienti.map((m, i) => (
              <div key={m.id} className="flex items-center justify-between gap-3 rounded-lg border border-sky-100 bg-white px-3 py-2 text-sm" data-testid={`ordinato-cliente-row-${i}`}>
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-900">{m.nome} <span className="text-xs font-semibold text-sky-700">x{m.da_ordinare}</span></p>
                  <p className="flex items-center gap-1 text-xs text-slate-700"><User className="h-3 w-3" /> {m.cliente || "cliente"}{m.cliente_telefono ? ` · ${m.cliente_telefono}` : ""}</p>
                  <p className="text-[11px] text-slate-500">{m.store_name}{m.fornitore ? ` · ${m.fornitore}` : ""}{m.prezzo != null ? ` · ${eur(m.prezzo)}${m.acconto ? ` (acconto ${eur(m.acconto)})` : ""}` : ""}{dal(m)}</p>
                </div>
                <Button size="sm" className="h-8 shrink-0 gap-1 bg-emerald-600 text-xs hover:bg-emerald-700" onClick={() => arrivo(m)} data-testid={`ordinato-cliente-arrivo-${i}`}>
                  <PackageCheck className="h-3.5 w-3.5" /> Arrivato
                </Button>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-sky-800">Premendo "Arrivato" il telefono torna a giacenza 0 e il cliente riceve il WhatsApp dal negozio.</p>
        </div>
      )}
      {ricambi.length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-4" data-testid="da-ordinare-ricambi-card">
          <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-rose-800"><AlertTriangle className="h-4 w-4" /> Ricambi da ordinare dai fornitori ({ricambi.length})</p>
          <div className="grid gap-2 md:grid-cols-2">
            {ricambi.map((m, i) => (
              <div key={m.id} className="flex items-center justify-between rounded-lg border border-rose-100 bg-white px-3 py-2 text-sm" data-testid={`da-ordinare-row-${i}`}>
                <div>
                  <p className="font-medium text-slate-900">{m.nome} <span className="text-xs font-semibold text-rose-700">x{m.da_ordinare}</span></p>
                  <p className="text-[11px] text-slate-500">{m.store_name}{m.fornitore ? ` · ${m.fornitore}` : ""}{m.ordine_servizio_numero ? ` · riparazione ${m.ordine_servizio_numero}` : ""}{dal(m)}</p>
                </div>
                <Button size="sm" variant="outline" className="h-7 gap-1 border-emerald-300 text-xs text-emerald-700" onClick={() => arrivo(m)} data-testid={`da-ordinare-arrivo-${i}`}>
                  <PackageCheck className="h-3.5 w-3.5" /> Arrivato
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
