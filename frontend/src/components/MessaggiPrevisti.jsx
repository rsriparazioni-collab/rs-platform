import { useEffect, useState } from "react";
import { CalendarClock, CheckCircle2, Clock, MinusCircle } from "lucide-react";
import api from "../lib/api";
import { fmtDate } from "../lib/constants";

const STATO = {
  previsto: { icon: Clock, cls: "text-sky-700", label: "Previsto" },
  inviato: { icon: CheckCircle2, cls: "text-emerald-700", label: "Inviato" },
  saltato: { icon: MinusCircle, cls: "text-slate-400", label: "Non inviato (fuori finestra)" },
};

export default function MessaggiPrevisti({ clientId, refreshKey }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (!clientId) return;
    api.get(`/clients/${clientId}/messaggi-previsti`).then((r) => setItems(r.data)).catch(() => setItems([]));
  }, [clientId, refreshKey]);

  return (
    <div className="rounded-xl border border-slate-200 p-4" data-testid="messaggi-previsti-card">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
        <CalendarClock className="mr-1 inline h-3.5 w-3.5" /> Calendario WhatsApp automatici
      </p>
      {items.length === 0 && <p className="text-xs text-slate-400">Nessun messaggio automatico previsto (servono data contratto o servizi telefonia con attivazione).</p>}
      <ol className="relative ml-2 space-y-3 border-l border-slate-200 pl-4" data-testid="messaggi-previsti-list">
        {items.map((it, i) => {
          const st = STATO[it.stato] || STATO.previsto;
          const Icon = st.icon;
          return (
            <li key={`${it.tipo}-${i}`} className="relative text-xs" data-testid={`messaggio-previsto-${i}`}>
              <span className={`absolute -left-[23px] top-0.5 rounded-full bg-white ${st.cls}`}><Icon className="h-3.5 w-3.5" /></span>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-slate-800">{it.label}</span>
                <span className={`font-semibold ${st.cls}`}>{it.stato === "inviato" ? `Inviato il ${fmtDate(it.inviato_il)}` : fmtDate(it.data)}</span>
              </div>
              <p className="text-slate-500">
                {it.stato === "previsto" ? "Invio automatico previsto" : st.label}
                {it.scadenza ? ` · scadenza ${fmtDate(it.scadenza)}` : ""}
              </p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
