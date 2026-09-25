import { useCallback, useEffect, useState } from "react";
import { Target, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const CON_OPERATORE = ["sim_nuova", "sim_mnp", "fisso"];
const AREA_LABEL = { generale: "Generale", energia: "Energia", telefonia: "Telefonia", internet: "Internet", chiamate: "Chiamate", riparazioni: "Riparazioni" };

export function BarraObiettivo({ o, compact = false }) {
  const done = o.pct >= 100;
  return (
    <div data-testid={`obiettivo-bar-${o.voce}`}>
      <div className="flex items-center justify-between text-[11px]">
        <span className={compact ? "truncate text-slate-600" : "text-slate-700"}>{o.label}</span>
        <span className={`ml-2 shrink-0 font-semibold ${done ? "text-emerald-700" : "text-slate-700"}`}>{o.attuale} / {o.target}</span>
      </div>
      <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full transition-[width] duration-500 ${done ? "bg-emerald-500" : o.pct >= 60 ? "bg-amber-400" : "bg-rose-400"}`} style={{ width: `${o.pct}%` }} />
      </div>
    </div>
  );
}

export default function ObiettiviDialog({ open, onOpenChange, utenti, voci, anno, mese, userId: initialUser, onChanged }) {
  const [userId, setUserId] = useState(initialUser || "");
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ voce: "", operatore: "", target: 1, ricorrente: true });

  useEffect(() => { if (initialUser) setUserId(initialUser); }, [initialUser]);
  const load = useCallback(() => { if (userId) api.get("/kpi/obiettivi", { params: { anno, mese, user_id: userId } }).then((r) => setList(r.data)).catch(() => {}); }, [userId, anno, mese]);
  useEffect(() => { if (open) load(); }, [open, load]);

  const add = async (e) => {
    e.preventDefault();
    try {
      await api.post("/kpi/obiettivi", { user_id: userId, voce: form.voce, operatore: form.operatore, target: parseInt(form.target) || 1, anno: form.ricorrente ? null : anno, mese: form.ricorrente ? null : mese });
      toast.success("Obiettivo salvato"); setForm({ ...form, operatore: "", target: 1 }); load(); onChanged?.();
    } catch (err) { toast.error(apiError(err)); }
  };
  const del = async (o) => { try { await api.delete(`/kpi/obiettivi/${o.id}`); load(); onChanged?.(); } catch (err) { toast.error(apiError(err)); } };

  const aree = [...new Set(voci.map((v) => v.area))];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="obiettivi-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl"><Target className="mr-2 inline h-5 w-5" />Obiettivi mensili</DialogTitle>
          <DialogDescription>Scegli l'operatore, la voce (anche per singolo operatore telefonico) e il numero da raggiungere. "Ogni mese" vale finché non lo togli.</DialogDescription></DialogHeader>
        <div className="space-y-1.5"><Label>Operatore / dipendente</Label>
          <Select value={userId || "none"} onValueChange={(v) => setUserId(v === "none" ? "" : v)}><SelectTrigger data-testid="obiettivi-utente"><SelectValue placeholder="Scegli…" /></SelectTrigger>
            <SelectContent><SelectItem value="none">Scegli…</SelectItem>{utenti.map((u) => <SelectItem key={u.id} value={u.id}>{u.name} <span className="text-slate-400">({u.role})</span></SelectItem>)}</SelectContent></Select></div>
        {userId && (
          <>
            <form onSubmit={add} className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:grid-cols-12" data-testid="obiettivi-form">
              <div className="space-y-1 sm:col-span-5"><Label className="text-xs">Su cosa</Label>
                <Select value={form.voce || "none"} onValueChange={(v) => setForm({ ...form, voce: v === "none" ? "" : v })}><SelectTrigger data-testid="obiettivi-voce"><SelectValue placeholder="Voce KPI…" /></SelectTrigger>
                  <SelectContent className="max-h-72"><SelectItem value="none">Voce KPI…</SelectItem>
                    {aree.map((a) => [<div key={`h-${a}`} className="px-2 py-1 text-[10px] font-bold uppercase text-slate-400">{AREA_LABEL[a] || a}</div>, ...voci.filter((v) => v.area === a).map((v) => <SelectItem key={v.id} value={v.id}>{v.label}</SelectItem>)])}
                  </SelectContent></Select></div>
              <div className="space-y-1 sm:col-span-3"><Label className="text-xs">Operatore tel. (opz.)</Label>
                <Input disabled={!CON_OPERATORE.includes(form.voce)} placeholder={CON_OPERATORE.includes(form.voce) ? "es. WIND3, ILIAD, EOLO" : "—"} value={form.operatore} onChange={(e) => setForm({ ...form, operatore: e.target.value })} data-testid="obiettivi-operatore" /></div>
              <div className="space-y-1 sm:col-span-2"><Label className="text-xs">Obiettivo</Label><Input type="number" min="1" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} data-testid="obiettivi-target" /></div>
              <div className="flex flex-col justify-end gap-1 sm:col-span-2">
                <label className="flex items-center gap-1 text-xs text-slate-600"><input type="checkbox" checked={form.ricorrente} onChange={(e) => setForm({ ...form, ricorrente: e.target.checked })} data-testid="obiettivi-ricorrente" /> Ogni mese</label>
                <Button type="submit" size="sm" disabled={!form.voce} className="gap-1 bg-slate-900 hover:bg-slate-800" data-testid="obiettivi-submit"><Plus className="h-3.5 w-3.5" /> Aggiungi</Button>
              </div>
            </form>
            <div className="space-y-2" data-testid="obiettivi-lista">
              {list.length === 0 && <p className="text-sm text-slate-500" data-testid="obiettivi-vuoto">Nessun obiettivo per questo operatore.</p>}
              {list.map((o) => (
                <div key={o.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2" data-testid={`obiettivo-row-${o.voce}`}>
                  <div className="flex-1"><BarraObiettivo o={o} /></div>
                  <span className="text-[10px] text-slate-400">{o.mese ? `solo ${String(o.mese).padStart(2, "0")}/${o.anno}` : "ogni mese"}</span>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => del(o)} data-testid={`obiettivo-del-${o.voce}`}><Trash2 className="h-4 w-4 text-rose-500" /></Button>
                </div>
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
