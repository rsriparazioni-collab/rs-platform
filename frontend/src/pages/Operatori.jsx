import { useCallback, useEffect, useState } from "react";
import { UserCog, Plus, Store, Trash2, Pencil, CheckCircle2, XCircle, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtDate, lavorazioneLabel, lavorazioneBadge } from "../lib/constants";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";

const EMPTY = { nome: "", store_id: "", tipo: "interno" };

export default function Operatori() {
  const { user } = useAuth();
  const [venditori, setVenditori] = useState([]);
  const [stores, setStores] = useState([]);
  const [vendite, setVendite] = useState({});
  const [open, setOpen] = useState({});
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const isAdmin = user.role === "admin";

  const load = useCallback(() => {
    api.get("/venditori").then((r) => setVenditori(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare i venditori")));
  }, []);

  useEffect(() => {
    load();
    api.get("/meta").then((r) => setStores(r.data.stores || [])).catch(() => {});
  }, [load]);

  const toggleOpen = async (v) => {
    const isOpen = !open[v.id];
    setOpen((s) => ({ ...s, [v.id]: isOpen }));
    if (isOpen && !vendite[v.id]) {
      try {
        const r = await api.get(`/venditori/${v.id}/vendite`);
        setVendite((s) => ({ ...s, [v.id]: r.data }));
      } catch (e) {
        toast.error(apiError(e, "Impossibile caricare le vendite"));
      }
    }
  };

  const togglePagato = async (v, c) => {
    try {
      const r = await api.post(`/clients/${c.id}/venditore-pagato`);
      setVendite((s) => ({
        ...s,
        [v.id]: (s[v.id] || []).map((x) => (x.id === c.id ? { ...x, venditore_pagato: r.data.venditore_pagato } : x)),
      }));
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const openNew = () => {
    setEditing(null);
    setForm(EMPTY);
    setFormOpen(true);
  };
  const openEdit = (v) => {
    setEditing(v);
    setForm({ nome: v.nome, store_id: v.store_id || "", tipo: v.tipo || "interno" });
    setFormOpen(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form, store_id: form.tipo === "esterno" ? "" : form.store_id };
      if (editing) {
        await api.patch(`/venditori/${editing.id}`, payload);
        toast.success("Venditore aggiornato");
      } else {
        await api.post("/venditori", payload);
        toast.success("Venditore aggiunto");
      }
      setFormOpen(false);
      load();
    } catch (err) {
      toast.error(apiError(err, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (v) => {
    if (!window.confirm(`Eliminare il venditore ${v.nome}? Le vendite associate restano ai clienti.`)) return;
    try {
      await api.delete(`/venditori/${v.id}`);
      toast.success("Venditore eliminato");
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <div className="space-y-6" data-testid="venditori-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Venditori</h1>
          <p className="mt-1 text-sm text-slate-500">Chi vende cosa, per quale negozio, e se il compenso è stato pagato</p>
        </div>
        {isAdmin && (
          <Button onClick={openNew} data-testid="add-venditore-button" className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Plus className="h-4 w-4" /> Nuovo venditore
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {venditori.map((v) => (
          <div key={v.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`venditore-card-${v.nome.toLowerCase()}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-fuchsia-100">
                  <UserCog className="h-5 w-5 text-fuchsia-700" />
                </div>
                <div>
                  <p className="font-heading text-base font-bold text-slate-900">{v.nome}</p>
                  <p className="flex items-center gap-1 text-xs text-slate-500">
                    <Store className="h-3 w-3" /> {v.store_name}
                  </p>
                </div>
              </div>
              <span className={`status-badge ${v.tipo === "esterno" ? "bg-slate-500/15 text-slate-700 border-slate-300" : "bg-sky-500/15 text-sky-700 border-sky-300"}`}>
                {v.tipo === "esterno" ? "Esterno" : "Interno"}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-slate-50 p-3 text-center">
                <p className="font-heading text-xl font-bold text-slate-900" data-testid={`venditore-vendite-${v.id.slice(0, 8)}`}>{v.vendite}</p>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Vendite</p>
              </div>
              <div className={`rounded-lg p-3 text-center ${v.da_pagare > 0 ? "bg-amber-50" : "bg-emerald-50"}`}>
                <p className={`font-heading text-xl font-bold ${v.da_pagare > 0 ? "text-amber-700" : "text-emerald-700"}`} data-testid={`venditore-dapagare-${v.id.slice(0, 8)}`}>{v.da_pagare}</p>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Da pagare</p>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-2">
              <Button variant="outline" size="sm" className="flex-1 gap-1.5" onClick={() => toggleOpen(v)} data-testid={`venditore-toggle-${v.id.slice(0, 8)}`}>
                {open[v.id] ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                Vendite
              </Button>
              {isAdmin && (
                <>
                  <Button variant="ghost" size="icon" onClick={() => openEdit(v)} data-testid={`venditore-edit-${v.id.slice(0, 8)}`}>
                    <Pencil className="h-4 w-4 text-slate-500" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => remove(v)} data-testid={`venditore-del-${v.id.slice(0, 8)}`}>
                    <Trash2 className="h-4 w-4 text-rose-500" />
                  </Button>
                </>
              )}
            </div>

            {open[v.id] && (
              <div className="mt-3 max-h-64 space-y-1.5 overflow-y-auto rounded-lg border border-slate-100 p-2" data-testid={`venditore-vendite-list-${v.id.slice(0, 8)}`}>
                {(vendite[v.id] || []).map((c) => (
                  <div key={c.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-2 text-xs">
                    <div>
                      <p className="font-medium text-slate-900">{c.cognome} {c.nome}</p>
                      <p className="text-slate-500">{c.store_name} · {fmtDate(c.data_contratto || c.created_at)}</p>
                      <p className={`mt-0.5 text-[10px] font-semibold ${c.incassato_struttura ? "text-emerald-600" : "text-slate-400"}`}
                         data-testid={`vendita-incassato-${c.id.slice(0, 8)}`}>
                        {c.incassato_struttura ? "Incassato dalla struttura" : "Non ancora incassato dalla struttura"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`status-badge ${lavorazioneBadge(c.lavorazione)}`}>{lavorazioneLabel(c.lavorazione)}</span>
                      <button
                        onClick={() => togglePagato(v, c)}
                        data-testid={`vendita-pagato-${c.id.slice(0, 8)}`}
                        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold transition-colors ${
                          c.venditore_pagato
                            ? "border-emerald-300 bg-emerald-500/15 text-emerald-700"
                            : "border-amber-300 bg-amber-500/15 text-amber-700"
                        }`}>
                        {c.venditore_pagato ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {c.venditore_pagato ? "Pagato" : "Da pagare"}
                      </button>
                    </div>
                  </div>
                ))}
                {(vendite[v.id] || []).length === 0 && (
                  <p className="py-4 text-center text-xs text-slate-400">Nessuna vendita associata. Assegna i clienti da "Servito da" nella scheda cliente.</p>
                )}
              </div>
            )}
          </div>
        ))}
        {venditori.length === 0 && (
          <p className="col-span-full py-10 text-center text-sm text-slate-500" data-testid="venditori-empty">Nessun venditore presente.</p>
        )}
      </div>

      <Dialog open={formOpen} onOpenChange={(o) => !o && setFormOpen(false)}>
        <DialogContent className="max-w-md" data-testid="venditore-form-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl">{editing ? "Modifica venditore" : "Nuovo venditore"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-4" data-testid="venditore-form">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Nome *</Label>
              <Input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} data-testid="venditore-form-nome" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipo</Label>
              <Select value={form.tipo} onValueChange={(v) => setForm({ ...form, tipo: v })}>
                <SelectTrigger data-testid="venditore-form-tipo"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="interno">Interno (di un negozio)</SelectItem>
                  <SelectItem value="esterno">Esterno (freelance)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.tipo === "interno" && (
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Negozio associato *</Label>
                <Select value={form.store_id} onValueChange={(v) => setForm({ ...form, store_id: v })}>
                  <SelectTrigger data-testid="venditore-form-store"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                  <SelectContent>
                    {stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)} data-testid="venditore-form-cancel">Annulla</Button>
              <Button type="submit" disabled={saving || !form.nome.trim() || (form.tipo === "interno" && !form.store_id)}
                      className="bg-slate-900 hover:bg-slate-800" data-testid="venditore-form-submit">
                {saving ? "Salvataggio..." : editing ? "Salva modifiche" : "Aggiungi venditore"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
