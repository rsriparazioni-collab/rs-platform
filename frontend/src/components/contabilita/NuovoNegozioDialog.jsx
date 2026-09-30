import { useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";

const VUOTO = { nome: "", referente: "", telefono_avvisi: "", wa_numero: "3792773557", email_to: "", email_from: "", condividi_admin: true };

export const NuovoNegozioDialog = ({ onCreated }) => {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState(VUOTO);
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const salva = async () => {
    setSaving(true);
    try { const r = await api.post("/contabilita/negozi", f); toast.success(`Negozio ${r.data.nome} creato e attivato`); setOpen(false); setF(VUOTO); onCreated(r.data.id); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const Campo = ({ label, k, placeholder, type = "text" }) => <label className="text-xs text-slate-500">{label}<Input type={type} value={f[k]} onChange={set(k)} placeholder={placeholder} className="mt-1" data-testid={`nuovo-negozio-${k}`} /></label>;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" variant="outline" data-testid="nuovo-negozio-btn"><Plus className="mr-1 h-4 w-4" /> Nuovo negozio</Button></DialogTrigger>
      <DialogContent className="max-w-md" data-testid="nuovo-negozio-dialog">
        <DialogHeader><DialogTitle>Nuovo negozio</DialogTitle></DialogHeader>
        <p className="text-xs text-slate-500">Crea il negozio in Gestione Negozi e lo attiva subito in Contabilità con le impostazioni di invio. Ricordati poi di creare l'utente del negozio in Utenti e collegare il suo WhatsApp.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Campo label="Nome negozio *" k="nome" placeholder="es. Chiavenna" />
          <Campo label="Referente" k="referente" placeholder="Nome referente" />
          <Campo label="Telefono avvisi negozio" k="telefono_avvisi" placeholder="39..." />
          <Campo label="WhatsApp corrispettivi (20:30) a" k="wa_numero" placeholder="3792773557" />
          <Campo label="Email mensile a" k="email_to" placeholder="commercialista@studio.it" type="email" />
          <Campo label="Email mittente" k="email_from" placeholder="rscontabilita@gmail.com" type="email" />
        </div>
        <label className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm"><span>Condividi corrispettivi con l'amministrazione</span><Switch checked={f.condividi_admin} onCheckedChange={set("condividi_admin")} data-testid="nuovo-negozio-condividi" /></label>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setOpen(false)}>Annulla</Button><Button onClick={salva} disabled={saving || !f.nome.trim()} data-testid="nuovo-negozio-salva">Crea e attiva</Button></div>
      </DialogContent>
    </Dialog>
  );
};
