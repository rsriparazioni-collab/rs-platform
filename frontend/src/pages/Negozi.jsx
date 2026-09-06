import { useCallback, useEffect, useState } from "react";
import { Plus, Building2, User, Wallet, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtDate } from "../lib/constants";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export default function Negozi() {
  const { user } = useAuth();
  const [stores, setStores] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nome: "", referente: "", tipo: "negozio", note: "", review_link: "" });
  const [editing, setEditing] = useState(null);
  const isAdmin = user.role === "admin";

  const load = useCallback(() => {
    api.get("/stores").then((r) => setStores(r.data)).catch((e) => toast.error(apiError(e, "Impossibile caricare i negozi")));
  }, []);
  useEffect(() => { load(); }, [load]);

  const markPaid = async (s) => {
    try {
      await api.post(`/stores/${s.id}/mark-paid`);
      toast.success(`Compenso registrato per ${s.nome}. Reset automatico tra 6 mesi.`);
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const create = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await api.patch(`/stores/${editing.id}`, form);
        toast.success("Negozio aggiornato");
      } else {
        await api.post("/stores", form);
        toast.success("Negozio aggiunto");
      }
      setOpen(false);
      setEditing(null);
      setForm({ nome: "", referente: "", tipo: "negozio", note: "", review_link: "" });
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  return (
    <div className="space-y-6" data-testid="negozi-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Negozi & Venditori</h1>
          <p className="mt-1 text-sm text-slate-500">Contratti del mese, compensi e reset pagamento a 6 mesi</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setOpen(true)} data-testid="add-store-button" className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Plus className="h-4 w-4" /> Aggiungi negozio
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {stores.map((s) => (
          <div key={s.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`store-card-${s.id}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-900">
                  <Building2 className="h-5 w-5 text-amber-400" />
                </div>
                <div>
                  <p className="font-heading text-base font-bold text-slate-900">{s.nome}</p>
                  <p className="flex items-center gap-1 text-xs text-slate-500"><User className="h-3 w-3" /> {s.referente || "-"}</p>
                </div>
              </div>
              <span className={`status-badge ${s.tipo === "freelance" ? "bg-violet-500/15 text-violet-700 border-violet-300" : "bg-sky-500/15 text-sky-700 border-sky-300"}`}>
                {s.tipo === "freelance" ? "Freelance" : "Negozio"}
              </span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Contratti nel mese</p>
                <p className="font-heading text-2xl font-bold text-slate-900" data-testid={`store-contratti-mese-${s.id}`}>{s.contratti_mese}</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Clienti totali</p>
                <p className="font-heading text-2xl font-bold text-slate-900">{s.totale_clienti}</p>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between rounded-lg border border-slate-200 p-3">
              {s.pagato_effettivo ? (
                <span className="flex items-center gap-2 text-sm font-semibold text-emerald-700" data-testid={`store-pagato-${s.id}`}>
                  <CheckCircle2 className="h-4 w-4" /> Pagato il {fmtDate(s.last_payment_date)}
                </span>
              ) : (
                <span className="flex items-center gap-2 text-sm font-semibold text-rose-600" data-testid={`store-non-pagato-${s.id}`}>
                  <AlertTriangle className="h-4 w-4" /> Da pagare
                </span>
              )}
              {isAdmin && !s.pagato_effettivo && (
                <Button size="sm" onClick={() => markPaid(s)} data-testid={`store-mark-paid-${s.id}`}
                        className="gap-1.5 bg-emerald-600 hover:bg-emerald-700">
                  <Wallet className="h-3.5 w-3.5" /> Paga
                </Button>
              )}
            </div>
            {s.note && <p className="mt-3 text-xs text-slate-500">{s.note}</p>}
            <div className="mt-3 flex items-center justify-between">
              {s.review_link
                ? <span className="text-xs font-medium text-emerald-700" data-testid={`store-review-ok-${s.id}`}>✓ Link recensioni configurato</span>
                : <span className="text-xs font-medium text-amber-600" data-testid={`store-review-missing-${s.id}`}>Link recensioni mancante</span>}
              {isAdmin && (
                <Button variant="ghost" size="sm" data-testid={`store-edit-${s.id}`}
                        onClick={() => { setEditing(s); setForm({ nome: s.nome, referente: s.referente || "", tipo: s.tipo, note: s.note || "", review_link: s.review_link || "" }); setOpen(true); }}>
                  Modifica
                </Button>
              )}
            </div>
          </div>
        ))}
        {stores.length === 0 && (
          <p className="col-span-full py-10 text-center text-sm text-slate-500" data-testid="stores-empty">Nessun negozio presente.</p>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="store-form-dialog">
          <DialogHeader><DialogTitle className="font-heading text-xl">{editing ? `Modifica ${editing.nome}` : "Nuovo negozio / venditore"}</DialogTitle></DialogHeader>
          <form onSubmit={create} className="space-y-4" data-testid="store-form">
            <div className="space-y-1.5">
              <Label>Nome negozio *</Label>
              <Input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} data-testid="store-input-nome" />
            </div>
            <div className="space-y-1.5">
              <Label>Referente</Label>
              <Input value={form.referente} onChange={(e) => setForm({ ...form, referente: e.target.value })} data-testid="store-input-referente" />
            </div>
            <div className="space-y-1.5">
              <Label>Tipo</Label>
              <Select value={form.tipo} onValueChange={(v) => setForm({ ...form, tipo: v })}>
                <SelectTrigger data-testid="store-select-tipo"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="negozio">Negozio</SelectItem>
                  <SelectItem value="freelance">Freelance (es. Devis)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Note</Label>
              <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} data-testid="store-input-note" />
            </div>
            <div className="space-y-1.5">
              <Label>Link recensioni Google (RS Riparazioni)</Label>
              <Input value={form.review_link} onChange={(e) => setForm({ ...form, review_link: e.target.value })}
                     placeholder="https://g.page/r/.../review" data-testid="store-input-review-link" />
              <p className="text-xs text-slate-500">Usato nel messaggio recensione WhatsApp per riparazioni/SIM/internet di questo negozio.</p>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)} data-testid="store-form-cancel">Annulla</Button>
              <Button type="submit" className="bg-slate-900 hover:bg-slate-800" data-testid="store-form-submit">{editing ? "Salva" : "Aggiungi"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
