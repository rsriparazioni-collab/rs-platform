import { useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Trash2, KeyRound, Eye, EyeOff, Copy, ExternalLink, Download, Search, Store } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

const EMPTY = { servizio: "", titolo: "", username: "", password: "", url: "", contenuto: "", store_ids: [], user_ids: [] };

const copyText = (text, label) => navigator.clipboard.writeText(text).then(() => toast.success(`${label} copiato`));

function PasswordCard({ p, i, stores, users, isAdmin, onEdit, onDelete }) {
  const [secret, setSecret] = useState(null);
  const [loading, setLoading] = useState(false);
  const storeNames = (p.store_ids || []).map((id) => stores.find((s) => s.id === id)?.nome).filter(Boolean);
  const userNames = (p.user_ids || []).map((id) => users.find((u) => u.id === id)?.name).filter(Boolean);

  const reveal = async () => {
    if (secret) { setSecret(null); return; }
    setLoading(true);
    try { const r = await api.get(`/passwords/${p.id}/reveal`); setSecret(r.data); }
    catch (e) { toast.error(apiError(e)); }
    finally { setLoading(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md" data-testid={`password-card-${i}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-heading text-base font-semibold text-slate-900" data-testid={`password-servizio-${i}`}>{p.servizio}</h3>
          {p.titolo && <p className="text-xs text-slate-500">{p.titolo}</p>}
        </div>
        {isAdmin && (
          <div className="flex shrink-0 gap-1">
            <Button variant="ghost" size="icon" onClick={() => onEdit(p)} data-testid={`password-edit-${i}`}><Pencil className="h-4 w-4 text-slate-500" /></Button>
            <Button variant="ghost" size="icon" onClick={() => onDelete(p)} data-testid={`password-delete-${i}`}><Trash2 className="h-4 w-4 text-rose-500" /></Button>
          </div>
        )}
      </div>

      <div className="mt-3 space-y-2 text-sm">
        {p.username && (
          <div className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
            <span className="truncate font-mono text-slate-700" data-testid={`password-username-${i}`}>{p.username}</span>
            <button type="button" onClick={() => copyText(p.username, "Utente")} className="text-slate-400 hover:text-slate-900" data-testid={`password-copy-user-${i}`}><Copy className="h-3.5 w-3.5" /></button>
          </div>
        )}
        {p.has_password && (
          <div className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
            <span className="truncate font-mono text-slate-700" data-testid={`password-value-${i}`}>{secret ? secret.password : "••••••••••"}</span>
            <div className="flex shrink-0 gap-2">
              {secret && <button type="button" onClick={() => copyText(secret.password, "Password")} className="text-slate-400 hover:text-slate-900" data-testid={`password-copy-${i}`}><Copy className="h-3.5 w-3.5" /></button>}
              <button type="button" onClick={reveal} disabled={loading} className="text-slate-400 hover:text-slate-900" data-testid={`password-reveal-${i}`}>{secret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}</button>
            </div>
          </div>
        )}
        {p.has_contenuto && (
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            {secret ? (
              <pre className="whitespace-pre-wrap break-words font-mono text-xs text-slate-700" data-testid={`password-contenuto-${i}`}>{secret.contenuto}</pre>
            ) : (
              <button type="button" onClick={reveal} disabled={loading} className="flex items-center gap-1.5 text-xs font-medium text-sky-700 hover:underline" data-testid={`password-reveal-contenuto-${i}`}><Eye className="h-3.5 w-3.5" /> Mostra dettagli / credenziali</button>
            )}
            {secret && <button type="button" onClick={() => setSecret(null)} className="mt-2 flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900"><EyeOff className="h-3.5 w-3.5" /> Nascondi</button>}
          </div>
        )}
        {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-sky-700 hover:underline" data-testid={`password-url-${i}`}><ExternalLink className="h-3 w-3" /> {p.url.replace(/^https?:\/\//, "").slice(0, 40)}</a>}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1" data-testid={`password-stores-${i}`}>
        <Store className="h-3 w-3 text-slate-400" />
        {storeNames.length ? storeNames.map((n) => <span key={n} className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">{n}</span>) : null}
        {userNames.map((n) => <span key={n} className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700">{n}</span>)}
        {!storeNames.length && !userNames.length && <span className="text-[11px] text-slate-400">Solo amministratore</span>}
      </div>
    </div>
  );
}

export default function PasswordManager() {
  const { user } = useAuth();
  const isAdmin = user.role === "admin";
  const [rows, setRows] = useState([]);
  const [stores, setStores] = useState([]);
  const [users, setUsers] = useState([]);
  const [splitting, setSplitting] = useState(false);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [importOpen, setImportOpen] = useState(false);
  const [sheetUrl, setSheetUrl] = useState("");
  const [importing, setImporting] = useState(false);

  const load = useCallback(() => api.get("/passwords").then((r) => setRows(r.data)).catch((e) => toast.error(apiError(e))), []);
  useEffect(() => {
    load();
    api.get("/meta").then((r) => setStores(r.data.stores)).catch(() => {});
    if (isAdmin) api.get("/users").then((r) => setUsers(r.data.filter((u) => u.role !== "admin" && u.active !== false))).catch(() => {});
  }, [load, isAdmin]);

  const runSplit = async () => {
    if (!window.confirm("Dividere le voci importate in una scheda per negozio? Colico e Somaggia saranno visibili solo ad admin e Deborah.")) return;
    setSplitting(true);
    try {
      const r = await api.post("/passwords/dividi-per-negozio");
      toast.success(`Analizzate ${r.data.voci_analizzate} voci, create ${r.data.schede_create} schede per negozio`); load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setSplitting(false); }
  };
  const toggleUser = (id) => setForm((f) => ({ ...f, user_ids: f.user_ids.includes(id) ? f.user_ids.filter((s) => s !== id) : [...f.user_ids, id] }));

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = async (p) => {
    setEditing(p);
    let secret = { password: "", contenuto: "" };
    try { secret = (await api.get(`/passwords/${p.id}/reveal`)).data; } catch (e) { toast.error(apiError(e)); }
    setForm({ servizio: p.servizio, titolo: p.titolo || "", username: p.username || "", password: secret.password, url: p.url || "", contenuto: secret.contenuto, store_ids: p.store_ids || [], user_ids: p.user_ids || [] });
    setOpen(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editing) await api.patch(`/passwords/${editing.id}`, form); else await api.post("/passwords", form);
      toast.success("Voce salvata"); setOpen(false); load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const remove = async (p) => {
    if (!window.confirm(`Eliminare la voce "${p.servizio}"?`)) return;
    try { await api.delete(`/passwords/${p.id}`); load(); } catch (e) { toast.error(apiError(e)); }
  };

  const runImport = async (e) => {
    e.preventDefault();
    setImporting(true);
    try {
      const r = await api.post("/passwords/import-sheet", { sheet_url: sheetUrl });
      if (r.data.status === "gia_importato") toast.info("Foglio già importato in precedenza");
      else toast.success(`Importate ${r.data.imported} pagine (${r.data.skipped} saltate)`);
      setImportOpen(false); load();
    } catch (err) { toast.error(apiError(err)); }
    finally { setImporting(false); }
  };

  const toggleStore = (id) => setForm((f) => ({ ...f, store_ids: f.store_ids.includes(id) ? f.store_ids.filter((s) => s !== id) : [...f.store_ids, id] }));
  const filtered = rows.filter((p) => !q || [p.servizio, p.titolo, p.username, p.url].join(" ").toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-6" data-testid="password-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Password</h1>
          <p className="mt-1 text-sm text-slate-500">{isAdmin ? "Credenziali di portali e servizi, cifrate. Scegli per ogni voce quali negozi possono vederla." : "Credenziali dei servizi condivise con il tuo negozio dall'amministratore."}</p>
        </div>
        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={runSplit} disabled={splitting} className="gap-2" data-testid="split-passwords-button"><Store className="h-4 w-4" /> {splitting ? "Divisione..." : "Dividi per negozio"}</Button>
            <Button variant="outline" onClick={() => setImportOpen(true)} className="gap-2" data-testid="import-passwords-button"><Download className="h-4 w-4" /> Importa da Google Sheet</Button>
            <Button onClick={openNew} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="add-password-button"><Plus className="h-4 w-4" /> Nuova voce</Button>
          </div>
        )}
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cerca servizio, utente, sito..." className="pl-9" data-testid="password-search" />
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-16 text-center text-sm text-slate-500" data-testid="password-empty">
          <KeyRound className="mx-auto mb-2 h-6 w-6 text-slate-300" />
          {rows.length === 0 ? (isAdmin ? "Nessuna password salvata: aggiungi una voce o importa il foglio Google." : "Nessuna password condivisa con il tuo negozio.") : "Nessun risultato per la ricerca."}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="password-grid">
          {filtered.map((p, i) => <PasswordCard key={p.id} p={p} i={i} stores={stores} users={users} isAdmin={isAdmin} onEdit={openEdit} onDelete={remove} />)}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl" data-testid="password-form-dialog">
          <DialogHeader><DialogTitle className="font-heading">{editing ? "Modifica voce" : "Nuova voce"}</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Servizio / sito *</Label><Input required value={form.servizio} onChange={(e) => setForm({ ...form, servizio: e.target.value })} placeholder="es. Kolme, Gmail, BRT" data-testid="password-form-servizio" /></div>
              <div className="space-y-1.5"><Label>Etichetta (es. negozio o account)</Label><Input value={form.titolo} onChange={(e) => setForm({ ...form, titolo: e.target.value })} placeholder="es. Sondrio" data-testid="password-form-titolo" /></div>
              <div className="space-y-1.5"><Label>Utente / email</Label><Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} data-testid="password-form-username" /></div>
              <div className="space-y-1.5"><Label>Password</Label><Input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="font-mono" data-testid="password-form-password" /></div>
            </div>
            <div className="space-y-1.5"><Label>Link (URL)</Label><Input type="url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://..." data-testid="password-form-url" /></div>
            <div className="space-y-1.5"><Label>Dettagli / altre credenziali (cifrato)</Label><Textarea rows={6} value={form.contenuto} onChange={(e) => setForm({ ...form, contenuto: e.target.value })} className="font-mono text-xs" data-testid="password-form-contenuto" /></div>
            <div className="space-y-2">
              <Label>Negozi che possono vedere questa voce (nessuno = solo amministratore)</Label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="password-form-stores">
                {stores.map((s) => (
                  <label key={s.id} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                    <Checkbox checked={form.store_ids.includes(s.id)} onCheckedChange={() => toggleStore(s.id)} data-testid={`password-form-store-${s.id}`} /> {s.nome}
                  </label>
                ))}
              </div>
            </div>
            {users.length > 0 && (
              <div className="space-y-2">
                <Label>Utenti singoli autorizzati (oltre ai negozi)</Label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="password-form-users">
                  {users.map((u) => (
                    <label key={u.id} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                      <Checkbox checked={form.user_ids.includes(u.id)} onCheckedChange={() => toggleUser(u.id)} data-testid={`password-form-user-${u.id}`} /> {u.name}
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annulla</Button>
              <Button type="submit" className="bg-slate-900 hover:bg-slate-800" data-testid="password-form-submit">Salva</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent data-testid="password-import-dialog">
          <DialogHeader><DialogTitle className="font-heading">Importa da Google Sheet</DialogTitle></DialogHeader>
          <form onSubmit={runImport} className="space-y-4">
            <p className="text-sm text-slate-500">Ogni pagina del foglio diventa una voce (nome pagina = servizio) con il contenuto cifrato. Il foglio deve essere condiviso "Chiunque con il link". Le pagine già importate vengono saltate.</p>
            <div className="space-y-1.5"><Label>Link del foglio</Label><Input required type="url" value={sheetUrl} onChange={(e) => setSheetUrl(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/..." data-testid="password-import-url" /></div>
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setImportOpen(false)}>Annulla</Button>
              <Button type="submit" disabled={importing} className="bg-slate-900 hover:bg-slate-800" data-testid="password-import-submit">{importing ? "Importazione..." : "Importa"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
