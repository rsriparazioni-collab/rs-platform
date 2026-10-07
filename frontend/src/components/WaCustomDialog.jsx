import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Send } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDateTime } from "../lib/constants";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

export default function WaCustomDialog({ client, open, onOpenChange, onSent }) {
  const phones = [client.telefono, ...(client.telefoni_extra || [])].filter(Boolean);
  const [phone, setPhone] = useState(phones[0] || "");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!open) return;
    setPhone(phones[0] || "");
    setMessage(`Ciao ${client.nome || ""}, `);
    api.get(`/clients/${client.id}/whatsapp/custom`).then((r) => setHistory(r.data)).catch(() => setHistory([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, client.id]);

  const send = async () => {
    setSending(true);
    try {
      await api.post(`/clients/${client.id}/whatsapp/custom`, { message, phone });
      toast.success("WhatsApp inviato");
      onSent?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(apiError(e, "Invio fallito"));
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="wa-custom-dialog">
        <DialogHeader><DialogTitle>Scrivi WhatsApp a {client.nome}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">Destinatario</label>
            <select value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="wa-custom-phone"
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
              {phones.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">Messaggio</label>
            <Textarea rows={6} value={message} onChange={(e) => setMessage(e.target.value)} data-testid="wa-custom-message"
                      placeholder="Scrivi il messaggio... puoi usare {nome}" className="mt-1" />
            <p className="mt-1 text-xs text-slate-500">Inviato dal numero WhatsApp del negozio del cliente.</p>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} data-testid="wa-custom-cancel">Annulla</Button>
            <Button size="sm" onClick={send} disabled={sending || !message.trim() || !phone} data-testid="wa-custom-send" className="gap-2">
              <Send className="h-4 w-4" /> {sending ? "Invio..." : "Invia"}
            </Button>
          </div>
          {history.length > 0 && (
            <div className="border-t border-slate-200 pt-3" data-testid="wa-custom-history">
              <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-500">Ultimi messaggi personalizzati</p>
              <ul className="max-h-40 space-y-1 overflow-y-auto text-xs">
                {history.map((h) => (
                  <li key={h.id} className="flex items-start gap-2 rounded bg-slate-50 p-2">
                    {h.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-600" />}
                    <div className="min-w-0">
                      <p className="text-slate-500">{fmtDateTime(h.at)} · {h.phone}</p>
                      <p className="whitespace-pre-wrap text-slate-700">{h.message}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
