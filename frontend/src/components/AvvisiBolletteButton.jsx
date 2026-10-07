import { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { lavorazioneLabel } from "../lib/constants";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

export default function AvvisiBolletteButton({ onSent }) {
  const [lista, setLista] = useState([]);
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);

  const load = () => api.get("/energia/avvisi-bollette/anteprima").then((r) => setLista(r.data)).catch(() => setLista([]));
  useEffect(() => { load(); }, []);

  const invia = async () => {
    setSending(true);
    try {
      const r = await api.post("/energia/avvisi-bollette/invia-ora");
      toast.success(`WhatsApp bollette: ${r.data.inviati} inviati${r.data.falliti ? `, ${r.data.falliti} falliti` : ""}`);
      setOpen(false); load(); onSent?.();
    } catch (e) { toast.error(apiError(e, "Invio fallito")); }
    finally { setSending(false); }
  };

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)} disabled={lista.length === 0} data-testid="avvisi-bollette-button"
              className="gap-1.5 border-violet-300 text-violet-800">
        <MessageCircle className="h-3.5 w-3.5" /> WA bollette ({lista.length})
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg" data-testid="avvisi-bollette-dialog">
          <DialogHeader><DialogTitle>Invito a inviare le bollette</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-600">Clienti in Centro Alert da almeno 20 giorni, non ancora lavorati. Il messaggio parte dal numero WhatsApp del negozio di ciascun cliente (una sola volta per scadenza).</p>
          <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200 text-sm" data-testid="avvisi-bollette-lista">
            {lista.map((c) => (
              <li key={c.client_id} className="flex items-center justify-between px-3 py-2">
                <span>{c.cognome} {c.nome} <span className="text-xs text-slate-500">· {lavorazioneLabel(c.lavorazione)}</span></span>
                <span className="text-xs text-slate-500">{c.giorni < 0 ? `${-c.giorni} gg fa` : `${c.giorni} gg`}</span>
              </li>
            ))}
          </ul>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="outline" onClick={() => setOpen(false)}>Annulla</Button>
            <Button size="sm" onClick={invia} disabled={sending || lista.length === 0} data-testid="avvisi-bollette-invia" className="gap-2 bg-violet-700 hover:bg-violet-800">
              <MessageCircle className="h-4 w-4" /> {sending ? "Invio..." : `Invia a ${lista.length} clienti`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
