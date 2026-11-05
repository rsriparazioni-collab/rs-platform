import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Check, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { ClienteLink } from "./ClienteLink";
import { Button } from "./ui/button";

const fmt = (iso) => { try { return new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return iso; } };

export default function RisposteSocial() {
  const [rows, setRows] = useState([]);
  const load = useCallback(() => { api.get("/social-followup/risposte").then((r) => setRows(r.data)).catch(() => {}); }, []);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  const gestita = async (id) => {
    try { await api.post(`/social-followup/risposte/${id}/gestita`); setRows((r) => r.filter((x) => x.id !== id)); }
    catch (e) { toast.error(apiError(e, "Operazione fallita")); }
  };

  if (!rows.length) return null;
  return (
    <div className="rounded-xl border border-pink-200 bg-pink-50 shadow-sm" data-testid="risposte-social-panel">
      <div className="flex items-center gap-2 border-b border-pink-200 px-5 py-3">
        <MessageCircle className="h-4 w-4 text-pink-600" />
        <h2 className="font-heading text-base font-semibold text-pink-900">Clienti che hanno risposto al messaggio social ({rows.length})</h2>
      </div>
      <ul className="divide-y divide-pink-100">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-wrap items-start gap-3 px-5 py-3" data-testid={`risposta-social-${r.id}`}>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-900">
                <ClienteLink clientId={r.client_id}>{r.client_name || r.tel}</ClienteLink>
                <span className="ml-2 rounded-full border border-pink-300 bg-white px-2 py-0.5 text-[11px] font-medium text-pink-700">{r.marchio === "rs" ? "RS Riparazioni" : "CambiaOra"}</span>
                <span className="ml-2 text-xs font-normal text-slate-500">{fmt(r.at)} · {r.tel}</span>
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{r.text}</p>
            </div>
            <div className="flex gap-2">
              <a href={`https://wa.me/${r.tel}`} target="_blank" rel="noreferrer" data-testid={`risposta-social-wa-${r.id}`}
                 className="inline-flex h-8 items-center gap-1 rounded-md border border-emerald-300 bg-white px-3 text-xs font-semibold text-emerald-700 hover:bg-emerald-50">
                Rispondi su WhatsApp <ExternalLink className="h-3 w-3" />
              </a>
              <Button size="sm" variant="outline" className="h-8 gap-1 text-xs" onClick={() => gestita(r.id)} data-testid={`risposta-social-gestita-${r.id}`}>
                <Check className="h-3 w-3" /> Gestita
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
