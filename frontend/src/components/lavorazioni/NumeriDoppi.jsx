import { useEffect, useState } from "react";
import { PhoneForwarded, ChevronDown, ChevronUp } from "lucide-react";
import api from "../../lib/api";

export const NumeriDoppi = ({ onOpen }) => {
  const [d, setD] = useState(null);
  const [aperto, setAperto] = useState(false);
  useEffect(() => { api.get("/lavorazioni/numeri-doppi").then((r) => setD(r.data)).catch(() => setD(null)); }, []);
  if (!d || !d.da_verificare) return null;
  const gruppi = d.gruppi.filter((g) => !g.stessa_persona);
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50/60 p-3" data-testid="numeri-doppi">
      <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setAperto((o) => !o)} data-testid="numeri-doppi-toggle">
        <span className="flex items-center gap-2 text-sm font-bold text-amber-900"><PhoneForwarded className="h-4 w-4" /> {d.da_verificare} numeri di telefono condivisi da persone diverse</span>
        <span className="flex items-center gap-2 text-xs text-amber-800">le bollette inviate su WhatsApp potrebbero finire sulla scheda sbagliata {aperto ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}</span>
      </button>
      {aperto && (
        <div className="mt-2 space-y-1.5">
          {gruppi.map((g) => (
            <div key={g.telefono} className="flex flex-wrap items-center gap-1.5 rounded-lg bg-white px-2 py-1.5 text-xs" data-testid={`numero-doppio-${g.telefono}`}>
              <span className="w-28 shrink-0 font-mono font-semibold text-slate-700">{g.telefono}</span>
              {g.clienti.map((c) => <button key={c.id} type="button" onClick={() => onOpen?.({ id: c.id })} className="rounded border border-slate-200 px-1.5 py-0.5 hover:bg-sky-50" data-testid={`numero-doppio-cliente-${c.id}`}><b>{c.nome}</b> <span className="text-slate-500">· {c.negozio}{c.utenza ? ` · ${c.utenza}` : ""}</span></button>)}
            </div>
          ))}
          <p className="text-[11px] text-amber-800">Apri la scheda e correggi il numero (o aggiungi il numero giusto nei "telefoni extra") così i documenti arrivano alla persona corretta. {d.stessa_persona > 0 && `Altri ${d.stessa_persona} numeri sono condivisi dalla stessa persona con più utenze: va bene così.`}</p>
        </div>
      )}
    </div>
  );
};
