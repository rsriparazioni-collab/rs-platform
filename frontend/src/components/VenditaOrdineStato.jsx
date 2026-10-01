import { useState } from "react";
import { toast } from "sonner";
import { PackageCheck, Handshake, Clock } from "lucide-react";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

export default function VenditaOrdineStato({ detail, refresh }) {
  const [busy, setBusy] = useState(false);
  if (!detail.ordine_at) return null;
  const saldo = ((detail.importo || 0) - (detail.acconto || 0)).toFixed(2);
  const run = async (fn, okMsg) => { setBusy(true); try { await fn(); toast.success(okMsg); refresh(); } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); } };
  const stati = { in_ordine: ["In ordine dal fornitore", "bg-rose-100 text-rose-700 border-rose-300", Clock], pronto_ritiro: ["Arrivato: pronto per il ritiro", "bg-teal-100 text-teal-700 border-teal-300", PackageCheck], consegnato: ["Consegnato e saldato", "bg-emerald-100 text-emerald-700 border-emerald-300", Handshake] };
  const [label, cls, Icon] = stati[detail.stato] || [detail.stato, "bg-slate-100 text-slate-700", Clock];
  return (
    <div className="rounded-xl border border-slate-200 p-4" data-testid="vendita-ordine-card">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Vendita su ordinazione</p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className={`status-badge ${cls}`} data-testid="vendita-ordine-stato"><Icon className="mr-1 inline h-3.5 w-3.5" />{label}</span>
          <p className="mt-2 text-sm text-slate-600">{detail.ordine_fornitore && <>Fornitore <b>{detail.ordine_fornitore}</b> · </>}Acconto € {detail.acconto || 0} · Saldo <b>€ {saldo}</b>{detail.arrivo_msg_sent_at && <span className="ml-2 text-xs text-emerald-700">WhatsApp "arrivato" inviato</span>}{detail.arrivo_msg_error && <span className="ml-2 text-xs text-rose-700">WhatsApp non inviato: {detail.arrivo_msg_error}</span>}</p>
        </div>
        <div className="flex gap-2">
          {detail.stato === "in_ordine" && <Button size="sm" variant="outline" className="border-emerald-300 text-emerald-700" disabled={busy} onClick={() => run(() => api.post(`/magazzino/${detail.magazzino_item_id}/arrivo`, { quantita: detail.quantita || 1 }), "Arrivo registrato: cliente avvisato via WhatsApp")} data-testid="vendita-ordine-arrivato"><PackageCheck className="mr-1 h-4 w-4" /> Arrivato</Button>}
          {["in_ordine", "pronto_ritiro"].includes(detail.stato) && <Button size="sm" disabled={busy} onClick={() => run(() => api.post(`/servizi/${detail.id}/consegna-ordine`), `Consegnato: incassato saldo € ${saldo}`)} data-testid="vendita-ordine-consegna"><Handshake className="mr-1 h-4 w-4" /> Consegnato e saldato</Button>}
        </div>
      </div>
    </div>
  );
}
