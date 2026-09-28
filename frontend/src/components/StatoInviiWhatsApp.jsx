import { useCallback, useEffect, useState } from "react";
import { MessageCircle, RefreshCw, AlertTriangle, CheckCircle2, ChevronDown } from "lucide-react";
import api from "../lib/api";
import { fmtDateTime } from "../lib/constants";

const TIPI = { privacy: "Privacy", recensione: "Recensione", pronto: "Pronto ritiro", avviso_negozio: "Avviso negozio", scadenza: "Scadenza", digest: "Digest", obiettivo: "Obiettivo", test: "Test" };

export default function StatoInviiWhatsApp() {
  const [data, setData] = useState(null);
  const [aperto, setAperto] = useState(null);
  const load = useCallback(() => api.get("/whatsapp/stato-invii", { params: { giorni: 7 } }).then((r) => setData(r.data)).catch(() => {}), []);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);
  if (!data) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="stato-invii-wa">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-3">
        <MessageCircle className="h-5 w-5 text-emerald-600" />
        <div className="flex-1">
          <h2 className="font-heading text-base font-semibold text-slate-900 md:text-lg">Stato invii WhatsApp <span className="text-xs font-normal text-slate-400">ultimi 7 giorni</span></h2>
          <p className="text-xs text-slate-500">
            <span className="text-emerald-700" data-testid="stato-invii-ok">{data.totale_inviati} inviati</span> · <span className={data.totale_falliti ? "text-rose-700 font-semibold" : "text-slate-500"} data-testid="stato-invii-ko">{data.totale_falliti} falliti</span>
            {data.dry_run && <span className="ml-2 status-badge bg-amber-500/15 text-amber-700 border-amber-300">modalità test attiva: nessun invio reale</span>}
            {!data.servizio_ok && <span className="ml-2 status-badge bg-rose-500/15 text-rose-700 border-rose-300">servizio WhatsApp non raggiungibile</span>}
          </p>
        </div>
        <button type="button" onClick={load} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100" data-testid="stato-invii-refresh"><RefreshCw className="h-4 w-4" /></button>
      </div>
      <div className="grid gap-2 p-4 md:grid-cols-2 xl:grid-cols-3">
        {data.negozi.map((n) => (
          <div key={n.session} className={`rounded-lg border p-3 ${n.falliti ? "border-rose-200 bg-rose-50/40" : "border-slate-200"}`} data-testid={`stato-invii-negozio-${n.session}`}>
            <button type="button" onClick={() => setAperto(aperto === n.session ? null : n.session)} className="flex w-full items-center gap-2 text-left">
              <span className={`h-2.5 w-2.5 rounded-full ${n.connessa === true ? "bg-emerald-500" : n.connessa === false ? "bg-rose-500" : "bg-slate-300"}`} title={n.connessa === true ? "WhatsApp collegato" : n.connessa === false ? "WhatsApp non collegato" : "Stato sconosciuto"} />
              <span className="flex-1 truncate text-sm font-semibold text-slate-900">{n.nome}</span>
              <span className="text-xs text-emerald-700">{n.inviati} ✓</span>
              {n.falliti > 0 && <span className="text-xs font-semibold text-rose-700">{n.falliti} ✗</span>}
              <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${aperto === n.session ? "rotate-180" : ""}`} />
            </button>
            <p className="mt-1 text-xs text-slate-400">{n.ultimo_at ? `Ultimo: ${fmtDateTime(n.ultimo_at)}` : "Nessun invio nel periodo"}{n.connessa === false && <span className="ml-2 text-rose-600">· da ricollegare (WHP Collegamento)</span>}</p>
            {n.errori.length > 0 && aperto !== n.session && (
              <p className="mt-1 flex items-start gap-1 text-xs text-rose-700"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {TIPI[n.errori[0].tipo] || n.errori[0].tipo} → {n.errori[0].phone}: {n.errori[0].error}</p>
            )}
            {aperto === n.session && (
              <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2" data-testid={`stato-invii-dettaglio-${n.session}`}>
                {n.ultimi.length === 0 && <li className="text-xs text-slate-400">Nessun messaggio</li>}
                {n.ultimi.map((m) => (
                  <li key={m.id} className="flex items-start gap-2 text-xs">
                    {m.ok ? <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-600" /> : <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-rose-600" />}
                    <span className="text-slate-500">{fmtDateTime(m.at)}</span>
                    <span className="font-medium text-slate-700">{TIPI[m.tipo] || m.tipo}</span>
                    <span className="text-slate-500">→ {m.phone}</span>
                    {!m.ok && <span className="text-rose-700">{m.error}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
