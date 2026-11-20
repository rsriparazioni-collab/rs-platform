import { useEffect, useState } from "react";
import { MessageSquareText } from "lucide-react";
import api from "../lib/api";

export default function MessaggiPanoramica() {
  const [d, setD] = useState(null);
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(null);
  useEffect(() => { if (open && !d) api.get("/messaggi-panoramica").then((r) => setD(r.data)).catch(() => {}); }, [open, d]);
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50/40 p-5 shadow-sm" data-testid="messaggi-panoramica">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between text-left" data-testid="messaggi-panoramica-toggle">
        <div>
          <h2 className="flex items-center gap-2 font-heading text-lg font-semibold text-slate-800"><MessageSquareText className="h-5 w-5 text-sky-600" /> Tutti i messaggi WhatsApp automatici</h2>
          <p className="text-xs text-slate-500">CambiaOra, ENEL e RS Riparazioni: cosa parte, quando, e con quale testo. Clicca una voce per leggerla.</p>
        </div>
        <span className="text-xs text-slate-500">{open ? "Nascondi" : "Mostra"}</span>
      </button>
      {open && d && (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {d.gruppi.map((g) => (
            <div key={g.id} className="rounded-lg border border-slate-200 bg-white" data-testid={`panoramica-${g.id}`}>
              <p className="border-b border-slate-100 px-3 py-2 text-sm font-semibold text-slate-800">{g.titolo}</p>
              <ul className="divide-y divide-slate-50">
                {g.voci.map((v) => {
                  const k = `${g.id}:${v.key}`;
                  return (
                    <li key={k}>
                      <button type="button" onClick={() => setSel(sel === k ? null : k)} className="flex w-full items-start justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50" data-testid={`panoramica-voce-${g.id}-${v.key}`}>
                        <span>
                          <span className="text-sm text-slate-800">{v.label}</span>{v.personalizzato && <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] text-amber-800">personalizzato</span>}
                          <span className="block text-[11px] text-slate-500">{v.quando}</span>
                        </span>
                        <span className="text-xs text-slate-400">{sel === k ? "−" : "+"}</span>
                      </button>
                      {sel === k && <pre className="whitespace-pre-wrap border-t border-slate-100 bg-slate-50 px-3 py-2 font-sans text-xs text-slate-700" data-testid={`panoramica-testo-${g.id}-${v.key}`}>{v.testo}</pre>}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {Object.keys(d.negozi_personalizzati).length > 0 && (
            <p className="text-xs text-slate-500 lg:col-span-3">Negozi con testi RS personalizzati: {Object.entries(d.negozi_personalizzati).map(([n, ks]) => `${n} (${ks.length})`).join(" · ")}</p>
          )}
        </div>
      )}
    </div>
  );
}
