import { useCallback, useEffect, useState } from "react";
import { Plus, ShieldCheck, Store, KeyRound, Power } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { RUOLI } from "../lib/constants";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Checkbox } from "../components/ui/checkbox";
import { Switch } from "../components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export default function Utenti() {
  const { user } = useAuth();
  const isAdmin = user.role === "admin";
  const [users, setUsers] = useState([]);
  const [stores, setStores] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "negozio", store_ids: [], can_view_all: false, sections: ["energia", "riparazioni", "telefonia"] });

  const SECTIONS_LIST = [
    { id: "energia", label: "Energia" },
    { id: "riparazioni", label: "Riparazioni" },
    { id: "telefonia", label: "Telefonia" },
  ];

  const toggleSection = (id) => {
    setForm((f) => ({
      ...f,
      sections: f.sections.includes(id) ? f.sections.filter((s) => s !== id) : [...f.sections, id],
    }));
  };

  const load = useCallback(() => {
    if (isAdmin) {
      api.get("/users").then((r) => setUsers(r.data))
        .catch((e) => toast.error(apiError(e, "Impossibile caricare gli utenti")));
    }
    api.get("/meta").then((r) => setStores(r.data.stores)).catch(() => {});
  }, [isAdmin]);
  useEffect(() => { load(); }, [load]);

  const toggleStore = (id) => {
    setForm((f) => ({
      ...f,
      store_ids: f.store_ids.includes(id) ? f.store_ids.filter((s) => s !== id) : [...f.store_ids, id],
    }));
  };

  const visibleStores = isAdmin ? stores : stores.filter((s) => user.store_ids?.includes(s.id));

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/users", form);
      toast.success("Utente creato");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "negozio", store_ids: [], can_view_all: false, sections: ["energia", "riparazioni", "telefonia"] });
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const toggleActive = async (u) => {
    try {
      await api.patch(`/users/${u.id}`, { active: !u.active });
      toast.success(u.active ? "Utente disattivato" : "Utente attivato");
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const resetPassword = async (u) => {
    const pwd = window.prompt(`Nuova password per ${u.name}:`);
    if (!pwd) return;
    try {
      await api.patch(`/users/${u.id}`, { password: pwd });
      toast.success("Password aggiornata");
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const storeNames = (ids) =>
    ids.map((id) => stores.find((s) => s.id === id)?.nome).filter(Boolean).join(", ") || "-";

  return (
    <div className="space-y-6" data-testid="utenti-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Utenti & Accessi</h1>
          <p className="mt-1 text-sm text-slate-500">Ogni negozio vede solo i propri clienti, salvo autorizzazione</p>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="add-user-button" className="gap-2 bg-slate-900 hover:bg-slate-800">
          <Plus className="h-4 w-4" /> Nuovo utente
        </Button>
      </div>

      {isAdmin && (
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="users-table">        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Ruolo</th>
                <th className="px-4 py-3">Negozi visibili</th>
                <th className="px-4 py-3">Sezioni</th>
                <th className="px-4 py-3">Vede tutto</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((u, i) => (
                <tr key={u.id} data-testid={`user-row-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{u.name}</td>
                  <td className="px-4 py-3 text-slate-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`status-badge ${u.role === "admin" ? "bg-amber-500/15 text-amber-700 border-amber-300" : u.role === "operatore" ? "bg-sky-500/15 text-sky-700 border-sky-300" : "bg-slate-500/15 text-slate-700 border-slate-300"}`}>
                      {u.role === "negozio" ? <Store className="h-3 w-3" /> : <ShieldCheck className="h-3 w-3" />}
                      {RUOLI[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{storeNames(u.store_ids)}</td>
                  <td className="px-4 py-3 text-xs text-slate-600">{(u.sections || ["energia", "riparazioni", "telefonia"]).join(", ")}</td>
                  <td className="px-4 py-3">{u.can_view_all ? "Sì" : "No"}</td>
                  <td className="px-4 py-3">
                    <span className={`status-badge ${u.active ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-rose-500/15 text-rose-700 border-rose-300"}`}>
                      {u.active ? "Attivo" : "Disattivato"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" title="Reimposta password" data-testid={`user-reset-pwd-${i}`} onClick={() => resetPassword(u)}>
                        <KeyRound className="h-4 w-4 text-slate-500" />
                      </Button>
                      <Button variant="ghost" size="icon" title={u.active ? "Disattiva" : "Attiva"} data-testid={`user-toggle-${i}`} onClick={() => toggleActive(u)}>
                        <Power className={`h-4 w-4 ${u.active ? "text-emerald-600" : "text-rose-500"}`} />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}

      {!isAdmin && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm" data-testid="utenti-info-box">
          Puoi creare account di accesso per i collaboratori dei tuoi negozi con il pulsante "Nuovo utente".
          Gli account creati vedranno solo i clienti dei negozi che gli assegni. La gestione completa degli utenti è riservata all'amministratore.
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="user-form-dialog">
          <DialogHeader><DialogTitle className="font-heading text-xl">Nuovo utente</DialogTitle></DialogHeader>
          <form onSubmit={create} className="space-y-4" data-testid="user-form">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Nome *</Label>
                <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="user-input-name" />
              </div>
              {isAdmin && (
                <div className="space-y-1.5">
                  <Label>Ruolo</Label>
                  <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                    <SelectTrigger data-testid="user-select-role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Amministratore</SelectItem>
                      <SelectItem value="operatore">Operatore</SelectItem>
                      <SelectItem value="negozio">Negozio</SelectItem>
                      <SelectItem value="tecnico">Tecnico (vede tutte le riparazioni)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Email *</Label>
              <Input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="user-input-email" />
            </div>
            <div className="space-y-1.5">
              <Label>Password *</Label>
              <Input required type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="user-input-password" />
            </div>
            {form.role === "negozio" && (
              <div className="space-y-2">
                <Label>Negozi assegnati</Label>
                <div className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 p-3" data-testid="user-stores-checkboxes">
                  {visibleStores.map((s) => (
                    <label key={s.id} className="flex items-center gap-2 text-sm">
                      <Checkbox checked={form.store_ids.includes(s.id)} onCheckedChange={() => toggleStore(s.id)}
                                data-testid={`user-store-check-${s.id}`} />
                      {s.nome}
                    </label>
                  ))}
                </div>
              </div>
            )}
            {isAdmin && (
              <div className="space-y-2">
                <Label>Sezioni visibili</Label>
                <div className="flex gap-4 rounded-lg border border-slate-200 p-3" data-testid="user-sections-checkboxes">
                  {SECTIONS_LIST.map((s) => (
                    <label key={s.id} className="flex items-center gap-2 text-sm">
                      <Checkbox checked={form.sections.includes(s.id)} onCheckedChange={() => toggleSection(s.id)}
                                data-testid={`user-section-check-${s.id}`} />
                      {s.label}
                    </label>
                  ))}
                </div>
              </div>
            )}
            {isAdmin && (
              <div className="flex items-center gap-3">
                <Switch checked={form.can_view_all} onCheckedChange={(v) => setForm({ ...form, can_view_all: v })} data-testid="user-switch-view-all" />
                <Label className="text-sm">Può vedere tutti i clienti (es. Deborah)</Label>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)} data-testid="user-form-cancel">Annulla</Button>
              <Button type="submit" className="bg-slate-900 hover:bg-slate-800" data-testid="user-form-submit">Crea utente</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
