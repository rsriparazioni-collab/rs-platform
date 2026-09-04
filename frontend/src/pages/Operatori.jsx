import { useEffect, useState } from "react";
import { UserCog, TrendingUp, CheckCircle2, Users } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { lavorazioneLabel, lavorazioneBadge } from "../lib/constants";

export default function Operatori() {
  const [stats, setStats] = useState([]);

  useEffect(() => {
    api.get("/operators/stats").then((r) => setStats(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare le statistiche")));
  }, []);

  const monthName = new Date().toLocaleDateString("it-IT", { month: "long", year: "numeric" });

  return (
    <div className="space-y-6" data-testid="operatori-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Operatori</h1>
        <p className="mt-1 text-sm text-slate-500">Lavorazioni e risultati di {monthName}</p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {stats.map((op) => (
          <div key={op.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`operator-card-${op.name.toLowerCase()}`}>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-100">
                <UserCog className="h-5 w-5 text-sky-700" />
              </div>
              <div>
                <p className="font-heading text-base font-bold text-slate-900">{op.name}</p>
                <p className="text-xs text-slate-500">{op.role === "admin" ? "Amministratore" : "Operatore"}</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-slate-50 p-3 text-center">
                <TrendingUp className="mx-auto h-4 w-4 text-sky-600" />
                <p className="mt-1 font-heading text-xl font-bold" data-testid={`op-lavorazioni-${op.id}`}>{op.lavorazioni_mese}</p>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Lavorazioni</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-center">
                <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-600" />
                <p className="mt-1 font-heading text-xl font-bold">{op.chiusi_mese}</p>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Chiusi</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-center">
                <Users className="mx-auto h-4 w-4 text-amber-600" />
                <p className="mt-1 font-heading text-xl font-bold">{op.clienti_gestiti}</p>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Clienti</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {Object.entries(op.per_status).map(([status, count]) => (
                <span key={status} className={`status-badge ${lavorazioneBadge(status)}`}>
                  {lavorazioneLabel(status)} · {count}
                </span>
              ))}
              {Object.keys(op.per_status).length === 0 && (
                <p className="text-xs text-slate-400">Nessuna lavorazione questo mese</p>
              )}
            </div>
          </div>
        ))}
        {stats.length === 0 && (
          <p className="col-span-full py-10 text-center text-sm text-slate-500" data-testid="operators-empty">
            Nessun operatore presente. Aggiungili dalla sezione Utenti.
          </p>
        )}
      </div>
    </div>
  );
}
