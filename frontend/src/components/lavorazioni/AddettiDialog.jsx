import { useState } from "react";
import { Users } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";

export const AddettiDialog = () => {
  const [open, setOpen] = useState(false);
  const [utenti, setUtenti] = useState([]);
  const [sel, setSel] = useState([]);
  const load = () => api.get("/lavorazioni/addetti").then((r) => { setUtenti(r.data.utenti); setSel(r.data.addetti); }).catch((e) => toast.error(apiError(e)));
  const save = async () => {
    try { await api.put("/lavorazioni/addetti", { addetti: sel }); toast.success("Addetti aggiornati"); setOpen(false); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (o) load(); }}>
      <DialogTrigger asChild><Button size="sm" variant="outline" data-testid="addetti-btn"><Users className="mr-1.5 h-4 w-4" /> Addetti</Button></DialogTrigger>
      <DialogContent data-testid="addetti-dialog">
        <DialogHeader><DialogTitle>Chi lavora le pratiche energia</DialogTitle></DialogHeader>
        <p className="text-sm text-slate-500">Gli utenti selezionati vedono questa sezione e ricevono il riepilogo WhatsApp del mattino (serve il telefono in Utenti). L'amministratore la vede sempre.</p>
        <div className="max-h-80 space-y-1.5 overflow-y-auto">
          {utenti.map((u) => (
            <label key={u.id} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50" data-testid={`addetto-${u.id}`}>
              <Checkbox checked={sel.includes(u.id)} onCheckedChange={(c) => setSel((s) => (c ? [...s, u.id] : s.filter((x) => x !== u.id)))} />
              <span className="flex-1"><b>{u.name}</b> <span className="text-slate-500">· {u.role}</span></span>
              <span className={`text-xs ${u.telefono ? "text-slate-500" : "text-amber-600"}`}>{u.telefono || "senza telefono"}</span>
            </label>
          ))}
        </div>
        <Button onClick={save} className="w-full" data-testid="addetti-save">Salva</Button>
      </DialogContent>
    </Dialog>
  );
};
