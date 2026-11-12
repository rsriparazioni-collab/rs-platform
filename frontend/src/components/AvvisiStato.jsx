import { useEffect, useState } from "react";
import { BellRing, CheckCircle2, XCircle } from "lucide-react";
import api from "../lib/api";

const LABEL = { "rinnovo-energia": "Rinnovo energia", bollette: "Richiesta bollette", "avvisi-vincolo": "Vincolo telefonia", "riparazioni-ferme": "Riparazioni ferme", "promemoria-ritiro": "Promemoria ritiro", "avvisi-truffe": "Avvisi truffe", "ordini-fermi": "Ordini fermi", "ritiri-in-attesa": "Ritiri in attesa" };
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "mai");

export default function AvvisiStato() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/avvisi/stato").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return null;
  const giri = Object.entries(LABEL).map(([k, l]) => [k, l, d.giri[k]]);
  return (
    <details className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="avvisi-stato">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-5 py-3 text-sm font-semibold text-slate-800">
        <BellRing className="h-4 w-4 text-sky-600" /> Avvisi automatici WhatsApp (ogni mattina 8:30)
        {d.dry_run && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800" data-testid="avvisi-dry-run">MODALITÀ TEST: nessun invio reale</span>}
        <span className="ml-auto text-xs font-normal text-slate-500">in attesa: {d.in_attesa.rinnovo_energia} rinnovi · {d.in_attesa.bollette} bollette · ultimi 7 gg: {Object.values(d.invii).reduce((a, v) => a + v.inviati_7gg, 0)} inviati, {Object.values(d.invii).reduce((a, v) => a + v.errori_7gg, 0)} errori</span>
      </summary>
      <div className="grid gap-2 border-t px-5 py-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
        {giri.map(([k, l, g]) => (
          <div key={k} className="flex items-start gap-2 rounded-lg border border-slate-100 p-2" data-testid={`avvisi-giro-${k}`}>
            {g ? (g.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-emerald-600" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 text-rose-600" />) : <span className="mt-0.5 h-3.5 w-3.5 rounded-full border border-slate-300" />}
            <div>
              <div className="font-medium text-slate-800">{l}</div>
              <div className="text-slate-500">ultimo giro {fmt(g?.last_run)}{g?.n != null && ` · ${g.n} elaborati`}</div>
              {g?.error && <div className="text-rose-600">{g.error}</div>}
            </div>
          </div>
        ))}
      </div>
      <div className="border-t px-5 py-2 text-[11px] text-slate-500">{Object.values(d.regole).join(" · ")}</div>
    </details>
  );
}
