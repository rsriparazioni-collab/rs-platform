import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PhoneCall } from "lucide-react";
import api from "../lib/api";
import { fmtDate } from "../lib/constants";
import ContattoDialog, { ContattoButton, ESITI, MOTIVI } from "./ContattoDialog";

const linkFor = (r) => (r.target_type === "servizio" ? (r.motivo === "riparazione_pronta" ? "/riparazioni" : "/telefonia") : "/clienti");

export default function DaRichiamare({ refreshKey, onChanged }) {
  const [rows, setRows] = useState([]);
  const [target, setTarget] = useState(null);
  const load = useCallback(() => api.get("/followup/da-richiamare").then((r) => setRows(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load, refreshKey]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="da-richiamare-panel">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div className="flex items-center gap-2">
          <PhoneCall className="h-4 w-4 text-violet-600" />
          <h2 className="font-heading text-lg font-semibold text-slate-800">Da richiamare</h2>
        </div>
        <span className="rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-bold text-violet-800" data-testid="da-richiamare-count">{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p className="px-5 py-6 text-center text-xs text-slate-400" data-testid="da-richiamare-empty">Nessun contatto in sospeso: quando un cliente non risponde, segna "Non risponde" e lo ritrovi qui.</p>
      ) : (
        <div className="divide-y divide-slate-100">
          {rows.map((r) => (
            <div key={r.id} className={`flex items-center justify-between gap-3 px-5 py-2.5 ${r.scaduto ? "bg-rose-50/60" : r.oggi ? "bg-amber-50/60" : ""}`} data-testid={`da-richiamare-${r.id}`}>
              <Link to={linkFor(r)} className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{r.label}{r.dettaglio ? <span className="text-slate-500"> · {r.dettaglio}</span> : null}</p>
                <p className="text-xs text-slate-500">{MOTIVI[r.motivo] || r.motivo} · {ESITI[r.esito]?.short}{r.note ? ` — ${r.note}` : ""} · {r.user_name}</p>
              </Link>
              <div className="flex items-center gap-2">
                {r.telefono && <a href={`tel:${r.telefono}`} className="hidden text-xs text-slate-500 sm:inline" data-testid={`da-richiamare-tel-${r.id}`}>{r.telefono}</a>}
                <span className={`text-xs font-bold ${r.scaduto ? "text-rose-600" : r.oggi ? "text-amber-600" : "text-slate-600"}`} data-testid={`da-richiamare-data-${r.id}`}>
                  {r.scaduto ? "In ritardo · " : r.oggi ? "Oggi · " : ""}{fmtDate(r.richiamare_il)}
                </span>
                <ContattoButton onClick={() => setTarget({ target_type: r.target_type, target_id: r.target_id, motivo: r.motivo, label: r.label, dettaglio: r.dettaglio, telefono: r.telefono })} testid={`da-richiamare-contatta-${r.id}`} />
              </div>
            </div>
          ))}
        </div>
      )}
      <ContattoDialog target={target} onClose={() => setTarget(null)} onSaved={() => { load(); onChanged?.(); }} />
    </div>
  );
}
