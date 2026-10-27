import { useState } from "react";
import { CalendarCheck, Check, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";

export const AgendaGiorno = ({ scadute, oggi, onChanged }) => {
  const [nota, setNota] = useState("");
  const [data, setData] = useState(oggi);
  const add = async () => {
    try { await api.post("/lavorazioni/agenda", { data, nota }); setNota(""); onChanged(); } catch (e) { toast.error(apiError(e)); }
  };
  const fatto = async (id) => { try { await api.patch(`/lavorazioni/agenda/${id}`, { fatto: true }); onChanged(); } catch (e) { toast.error(apiError(e)); } };
  const del = async (id) => { try { await api.delete(`/lavorazioni/agenda/${id}`); onChanged(); } catch (e) { toast.error(apiError(e)); } };
  return (
    <section className="rounded-xl border border-violet-200 bg-violet-50/60 p-3" data-testid="agenda-oggi">
      <h2 className="mb-2 flex items-center gap-2 text-base font-bold text-slate-800"><CalendarCheck className="h-4 w-4 text-violet-600" /> La mia agenda – oggi e arretrati <span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-600" data-testid="agenda-count">{scadute.length}</span></h2>
      <div className="mb-2 flex flex-wrap gap-2">
        <Input type="date" value={data} onChange={(e) => setData(e.target.value)} className="h-8 w-40 bg-white" data-testid="agenda-data" />
        <Input placeholder="Promemoria (es. richiamare sig. Rossi per bollette)" value={nota} onChange={(e) => setNota(e.target.value)} className="h-8 flex-1 bg-white" data-testid="agenda-nota" onKeyDown={(e) => e.key === "Enter" && nota.trim() && add()} />
        <Button size="sm" className="h-8" onClick={add} disabled={!nota.trim()} data-testid="agenda-add">Aggiungi</Button>
      </div>
      {scadute.length === 0 ? <p className="text-xs text-slate-400">Nessun promemoria per oggi.</p> : (
        <ul className="space-y-1">
          {scadute.map((a) => (
            <li key={a.id} className={`flex items-center gap-2 rounded-lg bg-white px-2.5 py-1.5 text-sm ${a.data < oggi ? "border border-red-200" : ""}`} data-testid={`agenda-item-${a.id}`}>
              <span className={`text-xs font-mono ${a.data < oggi ? "text-red-600 font-semibold" : "text-slate-500"}`}>{a.data.split("-").reverse().join("/")}</span>
              <span className="flex-1 truncate"><b>{a.client_name}</b> {a.client_name && "– "}{a.nota}</span>
              <Button size="sm" variant="ghost" className="h-7 px-2 text-emerald-700" onClick={() => fatto(a.id)} data-testid={`agenda-fatto-${a.id}`}><Check className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" className="h-7 px-2 text-slate-400" onClick={() => del(a.id)} data-testid={`agenda-del-${a.id}`}><Trash2 className="h-4 w-4" /></Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export const AgendaNuovo = ({ riga, onClose, onSaved }) => {
  const domani = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const [data, setData] = useState(domani);
  const [nota, setNota] = useState("");
  const save = async () => {
    try { await api.post("/lavorazioni/agenda", { client_id: riga.id, data, nota }); toast.success("Aggiunto in agenda"); onSaved(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="agenda-dialog">
        <DialogHeader><DialogTitle>Agenda – {riga.client_name}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input type="date" value={data} onChange={(e) => setData(e.target.value)} data-testid="agenda-dialog-data" />
          <Input placeholder="Cosa devi fare?" value={nota} onChange={(e) => setNota(e.target.value)} data-testid="agenda-dialog-nota" autoFocus />
          <Button onClick={save} disabled={!nota.trim()} className="w-full" data-testid="agenda-dialog-save">Salva promemoria</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
