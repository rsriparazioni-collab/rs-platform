import { useEffect, useState } from "react";
import { Merge } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";

export const UnisciSchedeDialog = ({ detail, onDone }) => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    const term = q.trim() || detail.cognome || "";
    if (term.length < 2) return;
    const t = setTimeout(() => api.get("/clients", { params: { q: term } }).then((r) => setRes((Array.isArray(r.data) ? r.data : r.data.items || []).filter((c) => c.id !== detail.id).slice(0, 15))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [q, open, detail]);
  const unisci = async () => {
    if (!sel) return;
    if (!window.confirm(`Unire la scheda di ${sel.cognome} ${sel.nome} (${sel.telefono || "senza telefono"}) dentro ${detail.cognome} ${detail.nome}?\nUtenze, documenti, storico e WhatsApp passano qui; l'altra scheda viene chiusa. Operazione non reversibile.`)) return;
    setBusy(true);
    try {
      const r = await api.post(`/clients/${detail.id}/unisci`, { sorgente_id: sel.id });
      const sp = Object.entries(r.data.spostati).map(([k, v]) => `${v} ${k}`).join(", ");
      toast.success(`Schede unite${sp ? `: spostati ${sp}` : ""}`);
      setOpen(false); onDone?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (o) { setQ(""); setSel(null); } }}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="border-violet-300 text-violet-700" data-testid="detail-unisci-button" title="Unisci un'altra scheda della stessa persona in questa"><Merge className="mr-2 h-4 w-4" /> Unisci scheda</Button>
      </DialogTrigger>
      <DialogContent data-testid="unisci-dialog">
        <DialogHeader><DialogTitle>Unisci un'altra scheda in «{detail.cognome} {detail.nome}»</DialogTitle></DialogHeader>
        <p className="text-xs text-slate-500">Cerca il doppione: le sue utenze, documenti, storico e messaggi passeranno in questa scheda; i campi vuoti qui verranno riempiti con i suoi dati; il suo numero finisce nei telefoni extra.</p>
        <Input autoFocus placeholder={`Cerca per cognome… (proposti: ${detail.cognome})`} value={q} onChange={(e) => setQ(e.target.value)} data-testid="unisci-search" />
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {res.map((c) => (
            <button key={c.id} type="button" onClick={() => setSel(c)} className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm ${sel?.id === c.id ? "border-violet-500 bg-violet-50" : "border-slate-200 hover:bg-slate-50"}`} data-testid={`unisci-cand-${c.id}`}>
              <span><b>{c.cognome} {c.nome}</b> <span className="text-slate-500">· {c.telefono || "—"}{c.codice_fiscale ? ` · ${c.codice_fiscale}` : ""}</span></span>
              <span className="text-xs text-slate-500">{c.tipo_bolletta || ""} {c.pod || c.pdr || ""} · {c.lavorazione || ""}</span>
            </button>
          ))}
          {res.length === 0 && <p className="py-2 text-center text-xs text-slate-400">Nessun'altra scheda trovata</p>}
        </div>
        <Button onClick={unisci} disabled={!sel || busy} className="w-full bg-violet-700 hover:bg-violet-800" data-testid="unisci-confirm"><Merge className="mr-2 h-4 w-4" /> Unisci in questa scheda</Button>
      </DialogContent>
    </Dialog>
  );
};
