import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Search, Recycle, FileDown, Trash2, Wrench, Paperclip, Package } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { uploadRitiroDocumenti } from "../components/RitiroDaRiparazione";
import { useAuth } from "../context/AuthContext";
import { fmtDate } from "../lib/constants";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

const EMPTY = { store_id: "", client_id: "", nome: "", cognome: "", codice_fiscale: "",
                articolo: "", imei: "", prezzo_ritiro: "", numero_documento: "", n_allegati: 2, data_ritiro: "" };

export default function Ritiri() {
  const { user } = useAuth();
  const [ritiri, setRitiri] = useState([]);
  const [meta, setMeta] = useState({ stores: [] });
  const [filters, setFilters] = useState({ q: "", venditore_id: "all" });
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const canSeeAll = user.role === "admin" || user.can_view_all;

  const load = useCallback(() => {
    const params = {};
    if (filters.q) params.q = filters.q;
    if (filters.venditore_id !== "all") params.venditore_id = filters.venditore_id;
    api.get("/ritiri", { params }).then((r) => setRitiri(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare i ritiri")));
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/meta").then((r) => setMeta(r.data)).catch(() => {}); }, []);

  useEffect(() => {
    if (search.trim().length < 2 || form.client_id) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      api.get("/clients", { params: { q: search.trim() } })
        .then((r) => setResults(r.data.slice(0, 6)))
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [search, form.client_id]);

  const pickClient = (c) => {
    setForm((f) => ({ ...f, client_id: c.id, nome: c.nome || "", cognome: c.cognome || "",
                      codice_fiscale: c.codice_fiscale || "" }));
    setResults([]);
  };

  const openNew = () => {
    setForm({ ...EMPTY, store_id: meta.stores[0]?.id || "" });
    setSearch("");
    setResults([]);
    setFormOpen(true);
  };

  const clienteParam = new URLSearchParams(window.location.search).get("cliente");
  useEffect(() => {
    if (!clienteParam || !meta.stores.length) return;
    api.get(`/clients/${clienteParam}`).then((r) => {
      const c = r.data;
      setForm({ ...EMPTY, store_id: c.venditore_id || meta.stores[0]?.id || "", client_id: c.id, nome: c.nome || "", cognome: c.cognome || "", codice_fiscale: c.codice_fiscale || "" });
      setFormOpen(true);
    }).catch(() => {});
  }, [clienteParam, meta.stores]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        prezzo_ritiro: form.prezzo_ritiro === "" ? null : parseFloat(form.prezzo_ritiro),
        n_allegati: parseInt(form.n_allegati) || 2,
        data_ritiro: form.data_ritiro || null,
      };
      const res = await api.post("/ritiri", payload);
      toast.success(`Bolla di ritiro ${res.data.numero} generata`);
      setFormOpen(false);
      load();
    } catch (err) {
      toast.error(apiError(err, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  const downloadPdf = async (r) => {
    try {
      const res = await api.get(`/ritiri/${r.id}/pdf`, { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(res.data);
      a.download = `${r.numero}.pdf`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      toast.error(apiError(e, "Download fallito"));
    }
  };

  const remove = async (r) => {
    if (!window.confirm(`Eliminare la bolla ${r.numero}?`)) return;
    try {
      await api.delete(`/ritiri/${r.id}`);
      toast.success("Ritiro eliminato");
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const allegaDocumenti = (r) => {
    const input = document.createElement("input");
    input.type = "file"; input.multiple = true; input.accept = "application/pdf,image/jpeg,image/png,image/webp";
    input.onchange = async () => {
      const files = Array.from(input.files || []);
      if (!files.length) return;
      try {
        await uploadRitiroDocumenti(r.id, files);
        toast.success(`${files.length} documenti uniti alla bolla ${r.numero}`);
        load();
      } catch (e) { toast.error(apiError(e, "Caricamento documenti fallito")); }
    };
    input.click();
  };

  return (
    <div className="space-y-6" data-testid="ritiri-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Ritiri usato</h1>
          <p className="mt-1 text-sm text-slate-500">{ritiri.length} bolle di ritiro generate</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadBlob("/ritiri/export", `ritiri_usato_${new Date().toISOString().slice(0, 10)}.xlsx`)} data-testid="ritiri-export-button" className="gap-2">
            <FileDown className="h-4 w-4" /> Excel
          </Button>
          <Button onClick={openNew} data-testid="add-ritiro-button" className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Plus className="h-4 w-4" /> Nuovo ritiro
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="ritiri-filters">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Cerca cliente, articolo o N° ritiro..." className="pl-9" value={filters.q}
                 onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} data-testid="ritiri-search" />
        </div>
        {canSeeAll && (
          <Select value={filters.venditore_id} onValueChange={(v) => setFilters((f) => ({ ...f, venditore_id: v }))}>
            <SelectTrigger className="w-[200px]" data-testid="ritiri-negozio-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti i negozi</SelectItem>
              {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="ritiri-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">N° ritiro</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Articolo</th>
                <th className="px-4 py-3">Riparazione</th>
                <th className="px-4 py-3">Prezzo ritiro</th>
                {canSeeAll && <th className="px-4 py-3">Negozio</th>}
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ritiri.map((r, i) => (
                <tr key={r.id} className="transition-colors hover:bg-slate-50" data-testid={`ritiro-row-${i}`}>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 font-mono text-xs font-bold text-slate-800">
                      <Recycle className="h-3.5 w-3.5 text-emerald-600" /> {r.numero}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{fmtDate(r.data_ritiro)}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{r.cognome} {r.nome}</td>
                  <td className="px-4 py-3 text-slate-600">{r.articolo}{r.imei ? ` · IMEI ${r.imei}` : ""}
                    <span className="mt-0.5 flex flex-wrap gap-1">
                      {(r.documenti || []).length > 0 && <span className="rounded bg-sky-50 px-1.5 text-[10px] font-semibold text-sky-700" data-testid={`ritiro-docs-badge-${i}`}><Paperclip className="inline h-3 w-3" /> {r.documenti.length} doc.</span>}
                      {r.magazzino_id && <span className="rounded bg-violet-50 px-1.5 text-[10px] font-semibold text-violet-700" data-testid={`ritiro-rigenerato-badge-${i}`}><Package className="inline h-3 w-3" /> rigenerato</span>}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {r.servizio_id
                      ? <Link to={`/riparazioni?apri=${r.servizio_id}`} className="inline-flex items-center gap-1 rounded-full border border-sky-300 bg-sky-500/15 px-2 py-0.5 text-xs font-semibold text-sky-700 hover:bg-sky-500/25"
                              data-testid={`ritiro-riparazione-link-${i}`}>
                          <Wrench className="h-3 w-3" /> {r.riparazione_numero || "Scheda"}
                        </Link>
                      : <span className="text-xs text-slate-400">-</span>}
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-800">
                    {r.prezzo_ritiro != null ? `€ ${Number(r.prezzo_ritiro).toFixed(2)}` : "-"}
                  </td>
                  {canSeeAll && <td className="px-4 py-3 text-slate-600">{r.store_name || "-"}</td>}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" title="Scarica bolla PDF" onClick={() => downloadPdf(r)} data-testid={`ritiro-pdf-${i}`}>
                        <FileDown className="h-4 w-4 text-sky-600" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Allega documenti alla bolla" onClick={() => allegaDocumenti(r)} data-testid={`ritiro-docs-${i}`}>
                        <Paperclip className="h-4 w-4 text-slate-500" />
                      </Button>
                      {user.role === "admin" && (
                        <Button variant="ghost" size="icon" onClick={() => remove(r)} data-testid={`ritiro-del-${i}`}>
                          <Trash2 className="h-4 w-4 text-rose-500" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {ritiri.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="ritiri-empty">
                  Nessun ritiro registrato. Crea la prima bolla con "Nuovo ritiro".
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={formOpen} onOpenChange={(o) => !o && setFormOpen(false)}>
        <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto" data-testid="ritiro-form-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl">Nuova bolla di ritiro usato</DialogTitle>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-4" data-testid="ritiro-form">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Negozio *</Label>
              <Select value={form.store_id} onValueChange={(v) => setForm({ ...form, store_id: v })} disabled={user.role === "negozio"}>
                <SelectTrigger data-testid="ritiro-form-store"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                <SelectContent>
                  {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 rounded-xl border border-slate-200 p-4" data-testid="ritiro-client-picker">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cliente</Label>
              {form.client_id ? (
                <div className="flex items-center justify-between rounded-lg bg-sky-50 px-3 py-2">
                  <span className="text-sm font-medium text-sky-800" data-testid="ritiro-client-selected">{form.cognome} {form.nome}</span>
                  <Button type="button" variant="ghost" size="sm" onClick={() => setForm((f) => ({ ...f, client_id: "" }))} data-testid="ritiro-client-clear">Cambia</Button>
                </div>
              ) : (
                <>
                  <Input placeholder="Cerca anagrafica per nome, telefono, CF..." value={search}
                         onChange={(e) => setSearch(e.target.value)} data-testid="ritiro-client-search" />
                  {results.length > 0 && (
                    <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                      {results.map((c) => (
                        <button type="button" key={c.id}
                                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                                onClick={() => pickClient(c)} data-testid={`ritiro-client-option-${c.id}`}>
                          <span className="font-medium">{c.cognome} {c.nome}</span>
                          <span className="text-xs text-slate-500">{c.telefono}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
              <div className="grid grid-cols-2 gap-3">
                <Input placeholder="Nome *" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} data-testid="ritiro-form-nome" />
                <Input placeholder="Cognome *" value={form.cognome} onChange={(e) => setForm({ ...form, cognome: e.target.value })} data-testid="ritiro-form-cognome" />
              </div>
              <Input placeholder="Codice fiscale" value={form.codice_fiscale} onChange={(e) => setForm({ ...form, codice_fiscale: e.target.value.toUpperCase() })} data-testid="ritiro-form-cf" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Articolo ritirato *</Label>
                <Input required placeholder="es. iPhone 12 Pro Max 128GB" value={form.articolo}
                       onChange={(e) => setForm({ ...form, articolo: e.target.value })} data-testid="ritiro-form-articolo" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">IMEI</Label>
                <Input value={form.imei} onChange={(e) => setForm({ ...form, imei: e.target.value })} data-testid="ritiro-form-imei" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prezzo ritiro €</Label>
                <Input type="number" step="0.01" value={form.prezzo_ritiro}
                       onChange={(e) => setForm({ ...form, prezzo_ritiro: e.target.value })} data-testid="ritiro-form-prezzo" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">N° documento (carta identità)</Label>
                <Input value={form.numero_documento} onChange={(e) => setForm({ ...form, numero_documento: e.target.value })} data-testid="ritiro-form-documento" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Documenti allegati (n.)</Label>
                <Input type="number" min="0" value={form.n_allegati}
                       onChange={(e) => setForm({ ...form, n_allegati: e.target.value })} data-testid="ritiro-form-allegati" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data ritiro</Label>
                <Input type="date" value={form.data_ritiro} onChange={(e) => setForm({ ...form, data_ritiro: e.target.value })} data-testid="ritiro-form-data" />
              </div>
            </div>
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)} data-testid="ritiro-form-cancel">Annulla</Button>
              <Button type="submit" disabled={saving || !form.nome.trim() || !form.cognome.trim() || !form.articolo.trim() || !form.store_id}
                      className="bg-slate-900 hover:bg-slate-800" data-testid="ritiro-form-submit">
                {saving ? "Generazione bolla..." : "Genera bolla PDF"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
