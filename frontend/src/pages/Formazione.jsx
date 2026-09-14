import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Presentation, Briefcase, Plus, Pencil, Trash2, Download, Link2, Copy, RotateCcw, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import Markdown from "../components/Markdown";
import SlideViewer from "../components/SlideViewer";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const TABS = [
  { key: "slide", label: "Presentazione", icon: Presentation },
  { key: "manuale", label: "Manuale operativo", icon: BookOpen },
  { key: "servizi", label: "Servizi & Operatori", icon: Briefcase },
];
const CATEGORIE = { generale: "Generale", clienti: "Clienti", energia: "Energia", riparazioni: "Riparazioni", telefonia: "Telefonia", magazzino: "Magazzino", whatsapp: "WhatsApp", sicurezza: "Sicurezza & GDPR", admin: "Amministrazione" };
const EMPTY = { sezione: "manuale", titolo: "", sottotitolo: "", contenuto: "", categoria: "", link: "", ordine: 0 };

function AdminBar({ item, onEdit, onDelete, i }) {
  return (
    <div className="flex shrink-0 gap-1">
      <Button variant="ghost" size="icon" onClick={() => onEdit(item)} data-testid={`formazione-edit-${i}`}><Pencil className="h-4 w-4 text-slate-500" /></Button>
      <Button variant="ghost" size="icon" onClick={() => onDelete(item)} data-testid={`formazione-delete-${i}`}><Trash2 className="h-4 w-4 text-rose-500" /></Button>
    </div>
  );
}

function Manuale({ rows, isAdmin, onEdit, onDelete }) {
  const [active, setActive] = useState(rows[0]?.id);
  const cur = rows.find((r) => r.id === active) || rows[0];
  const groups = useMemo(() => rows.reduce((acc, r) => { (acc[r.categoria || "generale"] ||= []).push(r); return acc; }, {}), [rows]);
  if (!cur) return <p className="text-sm text-slate-500" data-testid="manuale-empty">Nessun capitolo.</p>;
  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]" data-testid="manuale">
      <nav className="space-y-4 lg:sticky lg:top-4 lg:self-start">
        {Object.entries(groups).map(([cat, list]) => (
          <div key={cat}>
            <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{CATEGORIE[cat] || cat}</p>
            {list.map((r) => (
              <button key={r.id} onClick={() => setActive(r.id)} className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm transition-colors ${r.id === cur.id ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`} data-testid={`manuale-nav-${r.id}`}>{r.titolo}</button>
            ))}
          </div>
        ))}
      </nav>
      <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" data-testid="manuale-capitolo">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700">{CATEGORIE[cur.categoria] || cur.categoria || "Generale"}</p>
            <h2 className="font-heading text-2xl font-bold text-slate-900" data-testid="manuale-titolo">{cur.titolo}</h2>
          </div>
          {isAdmin && <AdminBar item={cur} onEdit={onEdit} onDelete={onDelete} i="cur" />}
        </div>
        <Markdown className="mt-4">{cur.contenuto}</Markdown>
        <p className="mt-6 border-t border-slate-100 pt-3 text-[11px] text-slate-400">Aggiornato il {new Date(cur.updated_at).toLocaleDateString("it-IT")}{cur.updated_by ? ` da ${cur.updated_by}` : ""}</p>
      </article>
    </div>
  );
}

function Servizi({ rows, isAdmin, onEdit, onDelete }) {
  const servizi = rows.filter((r) => r.sottotitolo !== "Operatore");
  const operatori = rows.filter((r) => r.sottotitolo === "Operatore");
  const Card = ({ r, i }) => (
    <div className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`servizio-card-${i}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{CATEGORIE[r.categoria] || r.categoria}</p>
          <h3 className="font-heading text-lg font-semibold text-slate-900">{r.titolo}</h3>
        </div>
        {isAdmin && <AdminBar item={r} onEdit={onEdit} onDelete={onDelete} i={r.id} />}
      </div>
      <Markdown className="mt-2 flex-1">{r.contenuto}</Markdown>
      {r.link && <a href={r.link} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline"><ExternalLink className="h-3 w-3" /> Apri portale</a>}
    </div>
  );
  return (
    <div className="space-y-8" data-testid="servizi">
      <section>
        <h2 className="mb-3 font-heading text-xl font-bold text-slate-900">Cosa offriamo</h2>
        <div className="grid gap-4 md:grid-cols-2">{servizi.map((r, i) => <Card key={r.id} r={r} i={i} />)}</div>
      </section>
      <section>
        <h2 className="mb-3 font-heading text-xl font-bold text-slate-900">Operatori e fornitori</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{operatori.map((r, i) => <Card key={r.id} r={r} i={`op-${i}`} />)}</div>
      </section>
    </div>
  );
}

export default function Formazione() {
  const { user } = useAuth();
  const isAdmin = user.role === "admin";
  const [tab, setTab] = useState("slide");
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = useCallback(() => api.get("/formazione").then((r) => setRows(r.data)).catch((e) => toast.error(apiError(e))), []);
  useEffect(() => { load(); }, [load]);
  const cur = rows.filter((r) => r.sezione === tab);
  const publicUrl = `${window.location.origin}/formazione/presentazione`;

  const openNew = () => { setEditing(null); setForm({ ...EMPTY, sezione: tab }); setOpen(true); };
  const openEdit = (r) => { setEditing(r); setForm({ sezione: r.sezione, titolo: r.titolo, sottotitolo: r.sottotitolo || "", contenuto: r.contenuto || "", categoria: r.categoria || "", link: r.link || "", ordine: r.ordine || 0 }); setOpen(true); };
  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editing) await api.patch(`/formazione/${editing.id}`, form); else await api.post("/formazione", form);
      toast.success("Salvato"); setOpen(false); load();
    } catch (err) { toast.error(apiError(err)); }
  };
  const remove = async (r) => {
    if (!window.confirm(`Eliminare "${r.titolo}"?`)) return;
    try { await api.delete(`/formazione/${r.id}`); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const pdf = async () => {
    try { await downloadBlob(`/formazione/pdf?sezione=${tab}`, `formazione_${tab}.pdf`); }
    catch (e) { toast.error(apiError(e)); }
  };
  const reset = async () => {
    if (!window.confirm("Ripristinare i contenuti predefiniti? Le modifiche fatte andranno perse.")) return;
    try { await api.post("/formazione/ripristina-default"); toast.success("Contenuti ripristinati"); load(); } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-6" data-testid="formazione-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Formazione</h1>
          <p className="mt-1 text-sm text-slate-500">Presentazione, manuale operativo e schede dei servizi: tutto quello che serve a un nuovo negozio per partire.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="gap-2" onClick={() => navigator.clipboard.writeText(publicUrl).then(() => toast.success("Link copiato"))} data-testid="formazione-copy-link"><Copy className="h-4 w-4" /> Copia link presentazione</Button>
          <Button variant="outline" className="gap-2" onClick={pdf} data-testid="formazione-pdf"><Download className="h-4 w-4" /> Scarica PDF</Button>
          {isAdmin && <Button variant="ghost" className="gap-2 text-slate-500" onClick={reset} data-testid="formazione-reset"><RotateCcw className="h-4 w-4" /> Ripristina</Button>}
          {isAdmin && <Button className="gap-2 bg-slate-900 hover:bg-slate-800" onClick={openNew} data-testid="formazione-add"><Plus className="h-4 w-4" /> Nuova voce</Button>}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200" data-testid="formazione-tabs">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${tab === t.key ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-900"}`} data-testid={`formazione-tab-${t.key}`}>
            <t.icon className="h-4 w-4" /> {t.label} <span className="text-xs text-slate-400">{rows.filter((r) => r.sezione === t.key).length}</span>
          </button>
        ))}
      </div>

      {tab === "slide" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800" data-testid="formazione-public-link">
            <Link2 className="h-3.5 w-3.5" /> Link pubblico (senza login): <a href={publicUrl} target="_blank" rel="noreferrer" className="font-mono underline">{publicUrl}</a>
          </div>
          <SlideViewer slides={cur} embedded />
          {isAdmin && (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="slide-admin-list">
              {cur.map((s, i) => (
                <div key={s.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
                  <span className="truncate"><span className="mr-2 text-slate-400">{s.ordine}.</span>{s.titolo}</span>
                  <AdminBar item={s} onEdit={openEdit} onDelete={remove} i={i} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {tab === "manuale" && <Manuale rows={cur} isAdmin={isAdmin} onEdit={openEdit} onDelete={remove} />}
      {tab === "servizi" && <Servizi rows={cur} isAdmin={isAdmin} onEdit={openEdit} onDelete={remove} />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl" data-testid="formazione-form-dialog">
          <DialogHeader><DialogTitle className="font-heading">{editing ? "Modifica voce" : "Nuova voce"}</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1.5"><Label>Sezione</Label>
                <Select value={form.sezione} onValueChange={(v) => setForm({ ...form, sezione: v })}>
                  <SelectTrigger data-testid="formazione-form-sezione"><SelectValue /></SelectTrigger>
                  <SelectContent>{TABS.map((t) => <SelectItem key={t.key} value={t.key}>{t.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5"><Label>Categoria</Label>
                <Select value={form.categoria || "generale"} onValueChange={(v) => setForm({ ...form, categoria: v })}>
                  <SelectTrigger data-testid="formazione-form-categoria"><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(CATEGORIE).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5"><Label>Ordine</Label><Input type="number" value={form.ordine} onChange={(e) => setForm({ ...form, ordine: parseInt(e.target.value) || 0 })} data-testid="formazione-form-ordine" /></div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Titolo *</Label><Input required value={form.titolo} onChange={(e) => setForm({ ...form, titolo: e.target.value })} data-testid="formazione-form-titolo" /></div>
              <div className="space-y-1.5"><Label>Sottotitolo {form.sezione === "servizi" && <span className="text-xs text-slate-400">("Operatore" per le schede operatore)</span>}</Label><Input value={form.sottotitolo} onChange={(e) => setForm({ ...form, sottotitolo: e.target.value })} data-testid="formazione-form-sottotitolo" /></div>
            </div>
            <div className="space-y-1.5"><Label>Link (portale, video, documento)</Label><Input value={form.link} onChange={(e) => setForm({ ...form, link: e.target.value })} placeholder="https://..." data-testid="formazione-form-link" /></div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-1.5"><Label>Contenuto (Markdown: **grassetto**, - elenchi, ## titoli, | tabelle |)</Label><Textarea rows={16} value={form.contenuto} onChange={(e) => setForm({ ...form, contenuto: e.target.value })} className="font-mono text-xs" data-testid="formazione-form-contenuto" /></div>
              <div className="space-y-1.5"><Label>Anteprima</Label><div className="max-h-[420px] overflow-y-auto rounded-lg border border-slate-200 p-3"><Markdown>{form.contenuto}</Markdown></div></div>
            </div>
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annulla</Button>
              <Button type="submit" className="bg-slate-900 hover:bg-slate-800" data-testid="formazione-form-submit">Salva</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
