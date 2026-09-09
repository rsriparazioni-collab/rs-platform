import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, XCircle, MessageCircle, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDateTime } from "../lib/constants";
import { Button } from "./ui/button";

const TIPO_LABEL = { privacy: "Privacy", recensione: "Recensione", pronto: "Pronto per ritiro", promemoria: "Promemoria ritiro", avviso_negozio: "Avviso negozio", vincolo: "Scadenza vincolo", offerta_annuale: "Scadenza offerta annuale", rinnovo_energia: "Rinnovo luce/gas", truffe: "Attenzione truffe" };

export default function WhatsAppLog({ url, refreshKey, onResent, title = "Registro WhatsApp inviati" }) {
  const [logs, setLogs] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [resending, setResending] = useState("");

  const load = useCallback(() => {
    if (!url) return;
    api.get(url).then((r) => setLogs(r.data)).catch(() => setLogs([]));
  }, [url]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const resend = async (l) => {
    setResending(l.id);
    try {
      await api.post(`/whatsapp-log/${l.id}/resend`);
      toast.success("Messaggio reinviato");
      load();
      onResent?.();
    } catch (e) {
      toast.error(apiError(e, "Reinvio fallito"));
      load();
    } finally {
      setResending("");
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 p-4" data-testid="whatsapp-log-card">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
        <MessageCircle className="mr-1 inline h-3.5 w-3.5" /> {title} ({logs.length})
      </p>
      <div className="max-h-56 space-y-1.5 overflow-y-auto" data-testid="whatsapp-log-list">
        {logs.map((l, i) => (
          <div key={l.id || `${l.at}-${i}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs" data-testid={`whatsapp-log-${i}`}>
            <div className="flex items-center justify-between gap-2">
              <button type="button" onClick={() => setExpanded(expanded === i ? null : i)}
                      className="flex flex-1 items-center gap-1.5 text-left font-medium text-slate-800 hover:text-sky-700">
                {l.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : <XCircle className="h-3.5 w-3.5 text-rose-500" />}
                {TIPO_LABEL[l.tipo] || "Messaggio"}
                {l.resent_at && <span className="text-[10px] text-slate-400">· reinviato {fmtDateTime(l.resent_at)}</span>}
              </button>
              <span className="text-slate-500">{fmtDateTime(l.at)}</span>
              {!l.ok && l.id && (
                <Button type="button" size="sm" variant="outline" className="h-6 gap-1 px-2 text-[11px]" disabled={resending === l.id}
                        onClick={() => resend(l)} data-testid={`whatsapp-log-resend-${i}`}>
                  <RotateCcw className="h-3 w-3" /> {resending === l.id ? "..." : "Reinvia"}
                </Button>
              )}
            </div>
            {!l.ok && l.error && <p className="mt-0.5 text-rose-600">Non inviato: {l.error}</p>}
            {expanded === i && <p className="mt-1.5 whitespace-pre-wrap text-slate-600">{l.message}</p>}
          </div>
        ))}
        {logs.length === 0 && <p className="text-xs text-slate-400">Nessun messaggio inviato</p>}
      </div>
    </div>
  );
}
