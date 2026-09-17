import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Clock, CheckCircle2, XCircle } from "lucide-react";
import api from "../lib/api";
import { fmtDateTime } from "../lib/constants";

export default function CodaWhatsApp() {
  const [s, setS] = useState(null);

  useEffect(() => {
    const load = () => api.get("/whatsapp/coda-stato").then((r) => setS(r.data)).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  if (!s) return null;
  const loopOk = s.ultimo_giro_coda && Date.now() - new Date(s.ultimo_giro_coda).getTime() < 5 * 60 * 1000;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="coda-whatsapp-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-heading text-lg font-semibold text-slate-800">
          <MessageCircle className="h-5 w-5 text-green-600" /> Coda WhatsApp
        </h2>
        <div className="flex items-center gap-2 text-xs">
          {s.dry_run && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800" data-testid="coda-dry-run">MODALITÀ TEST</span>}
          <span className={`rounded-full px-2 py-0.5 font-medium ${loopOk ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`} data-testid="coda-loop-stato">
            {loopOk ? "Invio automatico attivo" : "Invio automatico NON attivo"}
          </span>
          <Link to="/whatsapp" className="text-sky-700 hover:underline">Collegamenti</Link>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg bg-slate-50 p-3" data-testid="coda-in-coda">
          <p className="text-xs text-slate-500">In coda</p>
          <p className="text-2xl font-bold text-slate-900">{s.in_coda}</p>
          <p className="text-xs text-slate-500 flex items-center gap-1"><Clock className="h-3 w-3" /> {s.prossimo_invio ? fmtDateTime(s.prossimo_invio) : "nessun invio previsto"}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3" data-testid="coda-inviati-24h">
          <p className="text-xs text-slate-500">Inviati ultime 24h</p>
          <p className="text-2xl font-bold text-emerald-700">{s.inviati_24h}</p>
          <p className="text-xs text-slate-500">{s.falliti_24h} falliti</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3" data-testid="coda-ultimo-ok">
          <p className="text-xs text-slate-500 flex items-center gap-1"><CheckCircle2 className="h-3 w-3 text-emerald-600" /> Ultimo invio riuscito</p>
          <p className="text-sm font-medium text-slate-900">{s.ultimo_invio_ok ? fmtDateTime(s.ultimo_invio_ok.at) : "-"}</p>
          <p className="text-xs text-slate-500">{s.ultimo_invio_ok?.tipo || ""}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3" data-testid="coda-ultimo-errore">
          <p className="text-xs text-slate-500 flex items-center gap-1"><XCircle className="h-3 w-3 text-rose-600" /> Ultimo errore</p>
          <p className="text-sm font-medium text-slate-900">{s.ultimo_errore ? fmtDateTime(s.ultimo_errore.at) : "-"}</p>
          <p className="truncate text-xs text-rose-600" title={s.ultimo_errore?.error || ""}>{s.ultimo_errore?.error || ""}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-500">Ultimo giro della coda: {s.ultimo_giro_coda ? fmtDateTime(s.ultimo_giro_coda) : "mai"} (ogni 60 secondi)</p>
    </div>
  );
}
