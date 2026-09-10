import { useCallback, useEffect, useState } from "react";
import { Plus, ExternalLink, Pencil, Trash2, Link2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export const SEZIONI_PORTALE = { energia: "Energia (luce/gas)", mobile: "Telefonia Mobile", fisso: "Telefonia Fisso", riparazioni: "Riparazioni" };
const EMPTY = { sezione: "mobile", operatore: "", nome: "", url: "", note: "" };

export default function Portali() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = useCallback(() => api.get("/portali").then((r) => setRows(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (p) => { setEditing(p); setForm({ sezione: p.sezione, operatore: p.operatore, nome: p.nome || "", url: p.url, note: p.note || "" }); setOpen(true); };

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editing) await api.patch(`/portali/${editing.id}`, form); else await api.post("/portali", form);
      toast.success("Portale salvato"); setOpen(false); load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const remove = async (p) => {
    if (!window.confirm(`Eliminare il portale ${p.operatore}?`)) return;
    await api.delete(`/portali/${p.id}`); load();
  };

  return (
    <div className="space-y-6" data-testid="portali-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Portali operatori</h1>
          <p className="mt-1 text-sm text-slate-500">Link ai portali di inserimento (es. Kolme per WINDTRE). Dopo il salvataggio di un servizio il gestionale propone il portale giusto.</p>
        </div>
        <Button onClick={openNew} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="add-portale-button"><Plus className="h-4 w-4" /> Nuovo portale</Button>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3">Sezione</th><th className="px-4 py-3">Operatore</th><th className="px-4 py-3">Portale</th><th className="px-4 py-3">Link</th><th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((p, i) => (
              <tr key={p.id} data-testid={`portale-row-${i}`}>
                <td className="px-4 py-3 text-slate-600">{SEZIONI_PORTALE[p.sezione] || p.sezione}</td>
                <td className="px-4 py-3 font-semibold text-slate-900">{p.operatore}</td>
                <td className="px-4 py-3 text-slate-700">{p.nome || "-"}{p.note && <span className="block text-xs text-slate-400">{p.note}</span>}</td>
                <td className="px-4 py-3"><a href={p.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sky-700 hover:underline" data-testid={`portale-link-${i}`}><ExternalLink className="h-3.5 w-3.5" /> {p.url.replace(/^https?:\/\//, "").slice(0, 45)}</a></td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(p)} data-testid={`portale-edit-${i}`}><Pencil className="h-4 w-4 text-slate-500" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => remove(p)} data-testid={`portale-delete-${i}`}><Trash2 className="h-4 w-4 text-rose-500" /></Button>
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="portali-empty"><Link2 className="mx-auto mb-2 h-6 w-6 text-slate-300" />Nessun portale configurato: aggiungi il primo (es. Mobile – WINDTRE – link Kolme).</td></tr>}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="portale-form-dialog">
          <DialogHeader><DialogTitle className="font-heading">{editing ? "Modifica portale" : "Nuovo portale"}</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Sezione</Label>
                <Select value={form.sezione} onValueChange={(v) => setForm({ ...form, sezione: v })}>
                  <SelectTrigger data-testid="portale-sezione"><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(SEZIONI_PORTALE).map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Operatore / fornitore (come appare nel gestionale)</Label>
                <Input required value={form.operatore} onChange={(e) => setForm({ ...form, operatore: e.target.value })} placeholder="es. WINDTRE" data-testid="portale-operatore" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Nome portale</Label>
              <Input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="es. Kolme" data-testid="portale-nome" />
            </div>
            <div className="space-y-1.5">
              <Label>Link (URL)</Label>
              <Input required type="url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://..." data-testid="portale-url" />
            </div>
            <div className="space-y-1.5">
              <Label>Note / istruzioni</Label>
              <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} data-testid="portale-note" />
            </div>
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annulla</Button>
              <Button type="submit" className="bg-slate-900 hover:bg-slate-800" data-testid="portale-submit">Salva</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
