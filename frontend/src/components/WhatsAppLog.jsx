import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, MessageCircle } from "lucide-react";
import api from "../lib/api";
import { fmtDateTime } from "../lib/constants";

const TIPO_LABEL = { privacy: "Privacy", recensione: "Recensione", pronto: "Pronto per ritiro", promemoria: "Promemoria ritiro", avviso_negozio: "Avviso negozio" };

export default function WhatsAppLog({ clientId, refreshKey }) {
  const [logs, setLogs] = useState([]);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    if (!clientId) return;
    api.get(`/clients/${clientId}/whatsapp-log`).then((r) => setLogs(r.data)).catch(() => setLogs([]));
  }, [clientId, refreshKey]);

  return (
    <div className="rounded-xl border border-slate-200 p-4" data-testid="whatsapp-log-card">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
        <MessageCircle className="mr-1 inline h-3.5 w-3.5" /> Registro WhatsApp inviati ({logs.length})
      </p>
      <div className="max-h-56 space-y-1.5 overflow-y-auto" data-testid="whatsapp-log-list">
        {logs.map((l, i) => (
          <button type="button" key={`${l.at}-${i}`} onClick={() => setExpanded(expanded === i ? null : i)}
                  className="w-full rounded-lg bg-slate-50 px-3 py-2 text-left text-xs hover:bg-slate-100" data-testid={`whatsapp-log-${i}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 font-medium text-slate-800">
                {l.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : <XCircle className="h-3.5 w-3.5 text-rose-500" />}
                {TIPO_LABEL[l.tipo] || "Messaggio"}
              </span>
              <span className="text-slate-500">{fmtDateTime(l.at)}</span>
            </div>
            {!l.ok && l.error && <p className="mt-0.5 text-rose-600">Non inviato: {l.error}</p>}
            {expanded === i && <p className="mt-1.5 whitespace-pre-wrap text-slate-600">{l.message}</p>}
          </button>
        ))}
        {logs.length === 0 && <p className="text-xs text-slate-400">Nessun messaggio inviato a questo cliente</p>}
      </div>
    </div>
  );
}
