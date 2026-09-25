import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Package, Pencil, Trash2, Minus, PlusCircle, FileDown, BadgeEuro } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import RigeneratiVenduti from "../components/RigeneratiVenduti";
import { useAuth } from "../context/AuthContext";
import { MAGAZZINO_CATEGORIE, magazzinoCategoriaLabel, CONDIZIONI, REGIMI_IVA, regimeIvaLabel, regimeIvaBadge, RICAMBIO_TIPOLOGIE, tipologiaLabel } from "../lib/constants";
import DaOrdinare from "../components/DaOrdinare";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

const EMPTY = { nome: "", barcode: "", categoria: "altro", condizione: "", regime_iva: "", store_id: "", quantita: 0, prezzo_acquisto: "", prezzo_vendita: "", note: "", marca: "", modello: "", tipologia: "" };

export default function Magazzino() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ stores: [] });
  const [filters, setFilters] = useState({ q: "", categoria: "all", venditore_id: "all", tipologia: "all", marca: "", in_ordine: false });
  const [daOrdinareKey, setDaOrdinareKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const canSeeAll = user.role === "admin" || user.role === "tecnico" || user.can_view_all;

  const load = useCallback(() => {
    const params = {};
    if (filters.q) params.q = filters.q;
    if (filters.categoria !== "all") params.categoria = filters.categoria;
    if (filters.regime_iva && filters.regime_iva !== "all") params.regime_iva = filters.regime_iva;
    if (filters.venditore_id !== "all") params.venditore_id = filters.venditore_id;
    if (filters.tipologia !== "all") params.tipologia = filters.tipologia;
    if (filters.marca.trim()) params.marca = filters.marca.trim();
    if (filters.in_ordine) params.in_ordine = true;
    api.get("/magazzino", { params }).then((r) => setItems(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare il magazzino")));
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/meta").then((r) => setMeta(r.data)).catch(() => {}); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...EMPTY, store_id: meta.stores[0]?.id || "" });
    setFormOpen(true);
  };
  const openEdit = (m) => {
    setEditing(m);
    setForm({ ...EMPTY, ...m, prezzo_acquisto: m.prezzo_acquisto ?? "", prezzo_vendita: m.prezzo_vendita ?? "" });
    setFormOpen(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        quantita: parseInt(form.quantita) || 0,
        prezzo_acquisto: form.prezzo_acquisto === "" ? null : parseFloat(form.prezzo_acquisto),
        prezzo_vendita: form.prezzo_vendita === "" ? null : parseFloat(form.prezzo_vendita),
      };
      if (editing) {
        await api.patch(`/magazzino/${editing.id}`, payload);
        toast.success("Articolo aggiornato");
      } else {
        await api.post("/magazzino", payload);
        toast.success("Articolo inserito");
      }
      setFormOpen(false);
      load();
    } catch (err) {
      toast.error(apiError(err, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  const movimento = async (m, delta) => {
    try {
      const r = await api.post(`/magazzino/${m.id}/movimento`, { delta, motivo: delta > 0 ? "carico" : "scarico manuale" });
      if (r.data.riparazioni_sbloccate?.length) toast.success(`Arrivo registrato: riparazioni ${r.data.riparazioni_sbloccate.join(", ")} passate in lavorazione`);
      load(); setDaOrdinareKey((k) => k + 1);
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const [vendita, setVendita] = useState(null);
  const [prezzoVendita, setPrezzoVendita] = useState("");
  const [venditeKey, setVenditeKey] = useState(0);
  const confermaVendita = async (e) => {
    e.preventDefault();
    try {
      const r = await api.post(`/magazzino/${vendita.id}/vendi`, { prezzo_vendita: parseFloat(prezzoVendita) });
      toast.success(`Venduto a € ${r.data.prezzo_vendita.toFixed(2)} · margine netto € ${r.data.margine.toFixed(2)}`);
      setVendita(null); setVenditeKey((k) => k + 1); load();
    } catch (err) { toast.error(apiError(err, "Vendita non registrata")); }
  };

  const remove = async (m) => {
    if (!window.confirm(`Eliminare "${m.nome}" dal magazzino?`)) return;
    try {
      await api.delete(`/magazzino/${m.id}`);
      toast.success("Articolo eliminato");
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const qtyBadge = (q) =>
    q <= 0 ? "bg-rose-500/15 text-rose-700 border-rose-300"
      : q <= 2 ? "bg-amber-500/15 text-amber-700 border-amber-300"
        : "bg-emerald-500/15 text-emerald-700 border-emerald-300";

  return (
    <div className="space-y-6" data-testid="magazzino-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Magazzino</h1>
          <p className="mt-1 text-sm text-slate-500">
            {items.length} articoli {canSeeAll ? "in tutti i negozi" : "del tuo negozio"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadBlob("/magazzino/export", `magazzino_${new Date().toISOString().slice(0, 10)}.xlsx`)} data-testid="magazzino-export-button" className="gap-2">
            <FileDown className="h-4 w-4" /> Excel
          </Button>
          <Button onClick={openNew} data-testid="add-articolo-button" className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Plus className="h-4 w-4" /> Nuovo articolo
          </Button>
        </div>
      </div>

      <DaOrdinare key={daOrdinareKey} onChanged={() => { load(); setDaOrdinareKey((k) => k + 1); }} />

      <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="magazzino-filters">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Cerca per marca, modello, nome o barcode (es. iphone 12 display)..." className="pl-9" value={filters.q}
                 onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} data-testid="magazzino-search" />
        </div>
        <Select value={filters.tipologia} onValueChange={(v) => setFilters((f) => ({ ...f, tipologia: v }))}>
          <SelectTrigger className="w-[180px]" data-testid="magazzino-tipologia-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutte le tipologie</SelectItem>
            {RICAMBIO_TIPOLOGIE.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input placeholder="Marca (es. Apple)" className="w-[150px]" value={filters.marca}
               onChange={(e) => setFilters((f) => ({ ...f, marca: e.target.value }))} data-testid="magazzino-marca-filter" />
        <Button type="button" variant={filters.in_ordine ? "default" : "outline"} className={filters.in_ordine ? "bg-rose-700 hover:bg-rose-800" : "border-rose-300 text-rose-700"} onClick={() => setFilters((f) => ({ ...f, in_ordine: !f.in_ordine }))} data-testid="magazzino-in-ordine-filter">
          Solo in ordine
        </Button>
        <Select value={filters.categoria} onValueChange={(v) => setFilters((f) => ({ ...f, categoria: v }))}>
          <SelectTrigger className="w-[180px]" data-testid="magazzino-categoria-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutte le categorie</SelectItem>
            {MAGAZZINO_CATEGORIE.map((c) => <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.regime_iva || "all"} onValueChange={(v) => setFilters((f) => ({ ...f, regime_iva: v }))}>
          <SelectTrigger className="w-[180px]" data-testid="magazzino-iva-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti i regimi IVA</SelectItem>
            {REGIMI_IVA.map((r) => <SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>
        {canSeeAll && (
          <Select value={filters.venditore_id} onValueChange={(v) => setFilters((f) => ({ ...f, venditore_id: v }))}>
            <SelectTrigger className="w-[200px]" data-testid="magazzino-negozio-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti i negozi</SelectItem>
              {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="magazzino-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Articolo</th>
                <th className="px-4 py-3">Categoria</th>
                {canSeeAll && <th className="px-4 py-3">Negozio</th>}
                <th className="px-4 py-3">Giacenza</th>
                <th className="px-4 py-3">Prezzo vendita</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((m, i) => (
                <tr key={m.id} className="transition-colors hover:bg-slate-50" data-testid={`magazzino-row-${i}`}>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 font-medium text-slate-900">
                      <Package className="h-3.5 w-3.5 text-slate-400" /> {m.nome}
                      {m.in_ordine && <span className="ml-2 rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-rose-700" data-testid={`magazzino-in-ordine-${i}`}>In ordine{m.ordine_servizio_numero ? ` · rip. ${m.ordine_servizio_numero}` : ""}</span>}
                      {m.barcode && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600" data-testid={`magazzino-barcode-${m.id}`}>{m.barcode}</span>}
                    </span>
                    {(m.marca || m.modello || m.tipologia) && <p className="text-xs text-slate-500">{[tipologiaLabel(m.tipologia), m.marca, m.modello].filter(Boolean).join(" · ")}</p>}
                    {m.note && <p className="text-xs text-slate-400">{m.note}</p>}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{magazzinoCategoriaLabel(m.categoria)}
                    {m.condizione && <span className="ml-1 text-xs text-slate-500">· {CONDIZIONI.find((c) => c.id === m.condizione)?.label}</span>}
                    {m.regime_iva && <span className={`ml-2 status-badge ${regimeIvaBadge(m.regime_iva)}`} data-testid={`magazzino-iva-${i}`}>{regimeIvaLabel(m.regime_iva)}</span>}
                  </td>
                  {canSeeAll && <td className="px-4 py-3 text-slate-600">{m.store_name || "-"}</td>}
                  <td className="px-4 py-3">
                    <span className={`status-badge ${qtyBadge(m.quantita || 0)}`} data-testid={`magazzino-qty-${i}`}>{m.quantita || 0} pz</span>
                    {m.in_ordine && (
                      <Button variant="outline" size="sm" className="ml-2 h-6 border-emerald-300 px-2 text-[11px] text-emerald-700" onClick={() => movimento(m, -(m.quantita || 0) || 1)} data-testid={`magazzino-arrivo-${i}`}>Carica arrivo</Button>
                    )}
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-800">
                    {m.prezzo_vendita != null ? `€ ${Number(m.prezzo_vendita).toFixed(2)}` : "-"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {m.categoria === "rigenerati" && (m.quantita || 0) > 0 && (
                        <Button variant="outline" size="sm" className="h-7 gap-1 border-violet-300 text-violet-700" onClick={() => { setVendita(m); setPrezzoVendita(m.prezzo_vendita != null ? String(m.prezzo_vendita) : ""); }} data-testid={`magazzino-vendi-${i}`}>
                          <BadgeEuro className="h-3.5 w-3.5" /> Venduto
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" title="Scarica 1 pz" onClick={() => movimento(m, -1)} data-testid={`magazzino-meno-${i}`}>
                        <Minus className="h-4 w-4 text-rose-500" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Carica 1 pz" onClick={() => movimento(m, 1)} data-testid={`magazzino-piu-${i}`}>
                        <PlusCircle className="h-4 w-4 text-emerald-600" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openEdit(m)} data-testid={`magazzino-edit-${i}`}>
                        <Pencil className="h-4 w-4 text-slate-500" />
                      </Button>
                      {user.role === "admin" && (
                        <Button variant="ghost" size="icon" onClick={() => remove(m)} data-testid={`magazzino-del-${i}`}>
                          <Trash2 className="h-4 w-4 text-rose-500" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="magazzino-empty">
                  Nessun articolo in magazzino. Aggiungi il primo con "Nuovo articolo".
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <RigeneratiVenduti key={venditeKey} canSeeAll={canSeeAll} />

      <Dialog open={!!vendita} onOpenChange={(o) => !o && setVendita(null)}>
        <DialogContent className="max-w-sm" data-testid="vendita-dialog">
          <DialogHeader><DialogTitle className="font-heading text-xl">Vendita rigenerato</DialogTitle></DialogHeader>
          {vendita && (
            <form onSubmit={confermaVendita} className="space-y-4">
              <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <p className="font-medium text-slate-900">{vendita.nome}{vendita.imei ? ` · IMEI ${vendita.imei}` : ""}</p>
                <p className="text-xs text-slate-500">Costo dispositivo: € {Number(vendita.prezzo_acquisto || 0).toFixed(2)}{vendita.ritiro_numero ? ` · Ritiro ${vendita.ritiro_numero}` : ""}</p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prezzo di vendita € (IVA inclusa)</Label>
                <Input required type="number" step="0.01" min="0" autoFocus value={prezzoVendita} onChange={(e) => setPrezzoVendita(e.target.value)} data-testid="vendita-prezzo" />
                {prezzoVendita !== "" && <p className="text-xs text-emerald-700">Margine netto stimato: € {((parseFloat(prezzoVendita) || 0) / 1.22 - Number(vendita.prezzo_acquisto || 0)).toFixed(2)}</p>}
              </div>
              <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
                <Button type="button" variant="outline" onClick={() => setVendita(null)}>Annulla</Button>
                <Button type="submit" className="bg-violet-700 hover:bg-violet-800" data-testid="vendita-submit">Registra vendita</Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={formOpen} onOpenChange={(o) => !o && setFormOpen(false)}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto" data-testid="magazzino-form-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl">{editing ? "Modifica articolo" : "Nuovo articolo"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-4" data-testid="magazzino-form">
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipologia</Label>
                <Select value={form.tipologia || "none"} onValueChange={(v) => setForm({ ...form, tipologia: v === "none" ? "" : v, categoria: v === "display" ? "display" : v === "accessorio" ? "accessori" : ["batteria", "fotocamera", "connettore_ricarica", "vetro_posteriore", "altoparlante", "microfono", "tasti_flex", "scocca"].includes(v) ? "ricambi" : form.categoria })}>
                  <SelectTrigger data-testid="magazzino-form-tipologia"><SelectValue placeholder="-" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">-</SelectItem>
                    {RICAMBIO_TIPOLOGIE.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Marca</Label>
                <Input placeholder="es. Apple" value={form.marca || ""} onChange={(e) => setForm({ ...form, marca: e.target.value })} data-testid="magazzino-form-marca" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Modello</Label>
                <Input placeholder="es. iPhone 12" value={form.modello || ""} onChange={(e) => setForm({ ...form, modello: e.target.value })} data-testid="magazzino-form-modello" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Nome articolo {form.tipologia || form.modello ? "(auto se vuoto)" : "*"}</Label>
              <Input placeholder={[tipologiaLabel(form.tipologia), form.marca, form.modello].filter(Boolean).join(" ") || "es. Display iPhone 13"} value={form.nome}
                     onChange={(e) => setForm({ ...form, nome: e.target.value })} data-testid="magazzino-form-nome" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Barcode / codice fornitore</Label>
              <Input placeholder="Scansiona o digita il codice a barre (EAN / codice Sifar)" value={form.barcode || ""}
                     onChange={(e) => setForm({ ...form, barcode: e.target.value.trim() })} data-testid="magazzino-form-barcode" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Categoria</Label>
                <Select value={form.categoria} onValueChange={(v) => setForm({ ...form, categoria: v })}>
                  <SelectTrigger data-testid="magazzino-form-categoria"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {MAGAZZINO_CATEGORIE.map((c) => <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Negozio *</Label>
                <Select value={form.store_id} onValueChange={(v) => setForm({ ...form, store_id: v })} disabled={user.role === "negozio"}>
                  <SelectTrigger data-testid="magazzino-form-store"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                  <SelectContent>
                    {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Condizione</Label>
                <Select value={form.condizione || "none"} onValueChange={(v) => setForm({ ...form, condizione: v === "none" ? "" : v, regime_iva: v === "nuovo" || v === "none" ? "" : form.regime_iva })}>
                  <SelectTrigger data-testid="magazzino-form-condizione"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">-</SelectItem>
                    {CONDIZIONI.map((c) => <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {(form.condizione === "rigenerato" || form.condizione === "usato" || form.categoria === "rigenerati") && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Regime IVA (rigenerato/usato)</Label>
                  <Select value={form.regime_iva || "none"} onValueChange={(v) => setForm({ ...form, regime_iva: v === "none" ? "" : v })}>
                    <SelectTrigger data-testid="magazzino-form-regime-iva"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">-</SelectItem>
                      {REGIMI_IVA.map((r) => <SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Giacenza (pz)</Label>
                <Input type="number" value={form.quantita}
                       onChange={(e) => setForm({ ...form, quantita: e.target.value })} data-testid="magazzino-form-quantita" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prezzo acquisto €</Label>
                <Input type="number" step="0.01" value={form.prezzo_acquisto}
                       onChange={(e) => setForm({ ...form, prezzo_acquisto: e.target.value })} data-testid="magazzino-form-acquisto" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prezzo vendita €</Label>
                <Input type="number" step="0.01" value={form.prezzo_vendita}
                       onChange={(e) => setForm({ ...form, prezzo_vendita: e.target.value })} data-testid="magazzino-form-vendita" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Note</Label>
              <Textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} data-testid="magazzino-form-note" />
            </div>
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)} data-testid="magazzino-form-cancel">Annulla</Button>
              <Button type="submit" disabled={saving || (!form.nome.trim() && !form.modello?.trim()) || !form.store_id} className="bg-slate-900 hover:bg-slate-800" data-testid="magazzino-form-submit">
                {saving ? "Salvataggio..." : editing ? "Salva modifiche" : "Inserisci articolo"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
