import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Zap, Flame, CheckCircle2, XCircle, Trash2, Pencil, ShieldCheck, Wallet, Upload, Download, Paperclip, MessageCircle, FileText } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { LAVORAZIONI, lavorazioneLabel, lavorazioneBadge, fmtDate } from "../lib/constants";
import ClientForm from "../components/ClientForm";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Label } from "../components/ui/label";

export default function Clienti() {
  const { user } = useAuth();
  const [clients, setClients] = useState([]);
  const [meta, setMeta] = useState({ suppliers: [], lavorazioni: [], stores: [], operators: [] });
  const [filters, setFilters] = useState({ q: "", lavorazione: "all", tipo_bolletta: "all", venditore_id: "all" });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importStore, setImportStore] = useState("");
  const [importMode, setImportMode] = useState("single");
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [waLoading, setWaLoading] = useState("");
  const canSeeAll = user.role === "admin" || user.can_view_all;

  const downloadBlob = async (url, filename) => {
    try {
      const res = await api.get(url, { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(res.data);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      toast.error(apiError(e, "Download fallito"));
    }
  };

  const loadAttachments = async (clientId) => {
    try {
      const res = await api.get(`/clients/${clientId}/attachments`);
      setAttachments(res.data);
    } catch {
      setAttachments([]);
    }
  };

  const uploadAttachment = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !detail) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/clients/${detail.id}/attachments`, fd);
      toast.success("Allegato caricato");
      loadAttachments(detail.id);
    } catch (err) {
      toast.error(apiError(err, "Upload fallito"));
    }
  };

  const deleteAttachment = async (att) => {
    try {
      await api.delete(`/attachments/${att.id}`);
      toast.success("Allegato eliminato");
      loadAttachments(detail.id);
    } catch (e) {
      toast.error(apiError(e, "Eliminazione fallita"));
    }
  };

  const sendWhatsApp = async (tipo) => {
    setWaLoading(tipo);
    try {
      const res = await api.post(`/clients/${detail.id}/whatsapp/${tipo}`);
      if (tipo === "privacy") {
        if (res.data.privacy_registered) {
          toast.success("Modulo privacy compilato e inviato in automatico sul sito");
        } else if (res.data.registration_error) {
          toast.warning(`Registrazione sito non riuscita: ${res.data.registration_error}`);
        }
        if (res.data.wa_error) {
          toast.warning(`WhatsApp non inviato: ${res.data.wa_error}`);
        } else {
          toast.success("Messaggio privacy inviato. La richiesta recensione partirà automaticamente tra 5 minuti.");
        }
      } else {
        toast.success("Richiesta recensione inviata");
      }
      openDetail(detail);
    } catch (e) {
      toast.error(apiError(e, "Invio WhatsApp fallito"));
    } finally {
      setWaLoading("");
    }
  };

  const runImport = async (e) => {
    e.preventDefault();
    setImporting(true);
    setImportResult(null);
    try {
      const res = await api.post("/import/google-sheet", {
        sheet_url: importUrl,
        store_id: importMode === "single" ? importStore : "",
        all_tabs: importMode === "all",
      });
      if (res.data.mode === "all_tabs") {
        setImportResult(res.data);
        const ok = res.data.report.filter((r) => r.status === "ok").length;
        toast.success(`Importazione completata: ${res.data.total_imported} clienti da ${ok} negozi`);
      } else {
        toast.success(`Importazione completata: ${res.data.imported} clienti importati, ${res.data.skipped} righe saltate`);
        setImportOpen(false);
        setImportUrl("");
      }
      load();
    } catch (err) {
      toast.error(apiError(err, "Importazione fallita"));
    } finally {
      setImporting(false);
    }
  };

  const load = useCallback(() => {
    const params = {};
    if (filters.q) params.q = filters.q;
    if (filters.lavorazione !== "all") params.lavorazione = filters.lavorazione;
    if (filters.tipo_bolletta !== "all") params.tipo_bolletta = filters.tipo_bolletta;
    if (filters.venditore_id !== "all") params.venditore_id = filters.venditore_id;
    api.get("/clients", { params }).then((r) => setClients(r.data)).catch(() => {});
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const storeName = (id) => meta.stores.find((s) => s.id === id)?.nome || "-";

  const openDetail = async (c) => {
    try {
      const res = await api.get(`/clients/${c.id}`);
      setDetail(res.data);
      loadAttachments(c.id);
    } catch {
      toast.error("Impossibile caricare il cliente");
    }
  };

  const markPaid = async (c) => {
    try {
      await api.post(`/clients/${c.id}/mark-paid`);
      toast.success("Pagamento registrato. Tornerà 'non pagato' tra 6 mesi.");
      load();
      if (detail?.id === c.id) openDetail(c);
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const remove = async (c) => {
    if (!window.confirm(`Eliminare ${c.cognome} ${c.nome}?`)) return;
    try {
      await api.delete(`/clients/${c.id}`);
      toast.success("Cliente eliminato");
      setDetail(null);
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <div className="space-y-6" data-testid="clienti-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Clienti</h1>
          <p className="mt-1 text-sm text-slate-500">{clients.length} utenze {canSeeAll ? "in totale" : "del tuo negozio"}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadBlob("/export/clients.xlsx", `report_clienti_${new Date().toISOString().slice(0, 10)}.xlsx`)}
                  data-testid="export-excel-button" className="gap-2">
            <Download className="h-4 w-4" /> Esporta Excel
          </Button>
          {user.role === "admin" && (
            <Button variant="outline" onClick={() => { setImportStore(meta.stores[0]?.id || ""); setImportOpen(true); }}
                    data-testid="import-sheet-button" className="gap-2">
              <Upload className="h-4 w-4" /> Importa da Google Sheet
            </Button>
          )}
          <Button onClick={() => { setEditing(null); setFormOpen(true); }} data-testid="add-client-button"
                  className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Plus className="h-4 w-4" /> Nuovo cliente
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="filters-bar">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Cerca nome, CF, POD, telefono..." className="pl-9" value={filters.q}
                 onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} data-testid="filter-search-input" />
        </div>
        <Select value={filters.lavorazione} onValueChange={(v) => setFilters((f) => ({ ...f, lavorazione: v }))}>
          <SelectTrigger className="w-[200px]" data-testid="filter-status-select"><SelectValue /></SelectTrigger>
          <SelectContent className="max-h-72">
            <SelectItem value="all">Tutte le lavorazioni</SelectItem>
            {LAVORAZIONI.map((l) => <SelectItem key={l.id} value={l.id}>{l.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.tipo_bolletta} onValueChange={(v) => setFilters((f) => ({ ...f, tipo_bolletta: v }))}>
          <SelectTrigger className="w-[140px]" data-testid="filter-tipo-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Luce + Gas</SelectItem>
            <SelectItem value="luce">Luce</SelectItem>
            <SelectItem value="gas">Gas</SelectItem>
          </SelectContent>
        </Select>
        {canSeeAll && (
          <Select value={filters.venditore_id} onValueChange={(v) => setFilters((f) => ({ ...f, venditore_id: v }))}>
            <SelectTrigger className="w-[200px]" data-testid="filter-negozio-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti i negozi</SelectItem>
              {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="clients-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Fornitore</th>
                <th className="px-4 py-3">Lavorazione</th>
                <th className="px-4 py-3">Rinnovo (10 mesi)</th>
                {canSeeAll && <th className="px-4 py-3">Negozio</th>}
                <th className="px-4 py-3">Pagato</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {clients.map((c, i) => (
                <tr key={c.id} className="cursor-pointer transition-colors hover:bg-slate-50"
                    onClick={() => openDetail(c)} data-testid={`client-row-${i}`}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{c.cognome} {c.nome}</p>
                    <p className="text-xs text-slate-500">{c.tipo_cliente === "business" ? `P.IVA ${c.p_iva || "-"}` : c.telefono}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 text-xs font-semibold">
                      {c.tipo_bolletta === "gas"
                        ? <><Flame className="h-3.5 w-3.5 text-orange-500" /> Gas</>
                        : <><Zap className="h-3.5 w-3.5 text-sky-500" /> Luce</>}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{c.fornitore_provenienza || "-"}</td>
                  <td className="px-4 py-3">
                    <span className={`status-badge ${lavorazioneBadge(c.lavorazione)}`}>{lavorazioneLabel(c.lavorazione)}</span>
                  </td>
                  <td className="px-4 py-3">
                    {c.data_rinnovo ? (
                      <div>
                        <p className="text-xs font-medium text-slate-900">{fmtDate(c.data_rinnovo)}</p>
                        <p className={`text-xs font-semibold ${c.giorni_al_rinnovo < 0 ? "text-rose-600" : c.giorni_al_rinnovo <= 30 ? "text-amber-600" : "text-slate-400"}`}>
                          {c.giorni_al_rinnovo < 0 ? `scaduto da ${-c.giorni_al_rinnovo} gg` : `tra ${c.giorni_al_rinnovo} gg`}
                        </p>
                      </div>
                    ) : <span className="text-slate-400">-</span>}
                  </td>
                  {canSeeAll && <td className="px-4 py-3 text-slate-600">{storeName(c.venditore_id)}</td>}
                  <td className="px-4 py-3">
                    {c.pagato_effettivo
                      ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300"><CheckCircle2 className="h-3 w-3" /> Pagato</span>
                      : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300"><XCircle className="h-3 w-3" /> Non pagato</span>}
                  </td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="icon" data-testid={`edit-client-${i}`}
                            onClick={() => { setEditing(c); setFormOpen(true); }}>
                      <Pencil className="h-4 w-4 text-slate-500" />
                    </Button>
                  </td>
                </tr>
              ))}
              {clients.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="clients-empty">
                  Nessun cliente trovato con questi filtri.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Sheet open={Boolean(detail)} onOpenChange={(o) => !o && setDetail(null)}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl" data-testid="client-detail-sheet">
          {detail && (
            <>
              <SheetHeader>
                <SheetTitle className="font-heading text-xl">{detail.cognome} {detail.nome}</SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-6">
                <div className="flex flex-wrap gap-2">
                  <span className={`status-badge ${lavorazioneBadge(detail.lavorazione)}`}>{lavorazioneLabel(detail.lavorazione)}</span>
                  <span className={`status-badge ${detail.tipo_contratto === "fisso" ? "bg-sky-500/15 text-sky-700 border-sky-300" : "bg-violet-500/15 text-violet-700 border-violet-300"}`}>
                    Contratto {detail.tipo_contratto}
                  </span>
                  {detail.privacy_firmata && (
                    <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">
                      <ShieldCheck className="h-3 w-3" /> Privacy firmata
                    </span>
                  )}
                  {detail.pagato_effettivo
                    ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">Pagato</span>
                    : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300">Non pagato</span>}
                </div>

                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Timeline contratto</p>
                  <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                    <div><p className="text-xs text-slate-500">Contratto</p><p className="font-semibold" data-testid="detail-data-contratto">{fmtDate(detail.data_contratto)}</p></div>
                    <div><p className="text-xs text-slate-500">Attivazione (+2m)</p><p className="font-semibold" data-testid="detail-data-attivazione">{fmtDate(detail.data_attivazione)}</p></div>
                    <div><p className="text-xs text-slate-500">Rinnovo (+10m)</p><p className="font-semibold text-amber-700" data-testid="detail-data-rinnovo">{fmtDate(detail.data_rinnovo)}</p></div>
                    <div><p className="text-xs text-slate-500">Scadenza</p><p className="font-semibold" data-testid="detail-data-scadenza">{fmtDate(detail.data_scadenza)}</p></div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <div><p className="text-xs text-slate-500">Telefono</p><p className="font-medium">{detail.telefono || "-"}</p></div>
                  <div><p className="text-xs text-slate-500">Email</p><p className="font-medium">{detail.email || "-"}</p></div>
                  <div><p className="text-xs text-slate-500">Codice Fiscale</p><p className="font-medium">{detail.codice_fiscale || "-"}</p></div>
                  <div><p className="text-xs text-slate-500">P.IVA</p><p className="font-medium">{detail.p_iva || "-"}</p></div>
                  <div className="col-span-2"><p className="text-xs text-slate-500">Indirizzo</p><p className="font-medium">{detail.indirizzo || "-"}</p></div>
                  <div><p className="text-xs text-slate-500">POD</p><p className="font-medium">{detail.pod || "-"}</p></div>
                  <div><p className="text-xs text-slate-500">PDR</p><p className="font-medium">{detail.pdr || "-"}</p></div>
                  <div className="col-span-2"><p className="text-xs text-slate-500">IBAN</p><p className="font-medium">{detail.iban || "-"}</p></div>
                  {detail.tipo_bolletta === "luce" && <div><p className="text-xs text-slate-500">Potenza</p><p className="font-medium">{detail.kw_potenza ?? "-"} kW</p></div>}
                </div>

                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Confronto tariffe</p>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-500">Attuale — {detail.fornitore_provenienza || "-"}</p>
                      {detail.tipo_bolletta === "luce"
                        ? <p className="mt-1 font-medium">{detail.costo_kwh_attuale ?? "-"} €/kWh</p>
                        : <p className="mt-1 font-medium">{detail.costo_smc_attuale ?? "-"} €/Smc</p>}
                      <p className="text-xs text-slate-500">Fisse: {detail.spese_fisse_attuale ?? "-"} €/mese</p>
                    </div>
                    <div className="rounded-lg bg-sky-50 p-3">
                      <p className="text-xs font-semibold text-sky-700">Nuovo — {detail.nuovo_fornitore || "-"}</p>
                      {detail.tipo_bolletta === "luce"
                        ? <p className="mt-1 font-medium">{detail.costo_kwh_nuovo ?? "-"} €/kWh</p>
                        : <p className="mt-1 font-medium">{detail.costo_smc_nuovo ?? "-"} €/Smc</p>}
                      <p className="text-xs text-slate-500">Fisse: {detail.spese_fisse_nuovo ?? "-"} €/mese</p>
                    </div>
                  </div>
                </div>

                {detail.note && (
                  <div><p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Note</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700" data-testid="detail-note">{detail.note}</p></div>
                )}

                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Storico lavorazioni</p>
                  <div className="max-h-48 space-y-2 overflow-y-auto" data-testid="detail-history">
                    {(detail.history || []).map((h) => (
                      <div key={h.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
                        <span><strong>{h.operatore_name}</strong> · {lavorazioneLabel(h.status)}</span>
                        <span className="text-slate-500">{fmtDate(h.created_at)}</span>
                      </div>
                    ))}
                    {(detail.history || []).length === 0 && <p className="text-xs text-slate-400">Nessuno storico</p>}
                  </div>
                </div>

                <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4" data-testid="whatsapp-card">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">WhatsApp automatico</p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => sendWhatsApp("privacy")} disabled={waLoading !== ""}
                            data-testid="wa-privacy-button" className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                      <MessageCircle className="h-4 w-4" />
                      {waLoading === "privacy" ? "Invio..." : "Invia link privacy"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => sendWhatsApp("review")} disabled={waLoading !== ""}
                            data-testid="wa-review-button" className="gap-2">
                      <MessageCircle className="h-4 w-4" />
                      {waLoading === "review" ? "Invio..." : "Invia richiesta recensione"}
                    </Button>
                  </div>
                  <div className="mt-2 space-y-0.5 text-xs text-slate-500">
                    {detail.privacy_msg_sent_at && <p data-testid="wa-privacy-sent">Privacy inviata il {fmtDate(detail.privacy_msg_sent_at)} — recensione automatica dopo 5 min</p>}
                    {detail.review_msg_sent_at && <p data-testid="wa-review-sent">Recensione richiesta il {fmtDate(detail.review_msg_sent_at)}</p>}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 p-4" data-testid="attachments-card">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Allegati (bollette, documenti)</p>
                    {attachments.length > 0 && (
                      <Button size="sm" variant="outline" data-testid="merged-pdf-button"
                              onClick={() => downloadBlob(`/clients/${detail.id}/attachments/merged`, `documenti_${detail.cognome}.pdf`)}>
                        <FileText className="mr-2 h-4 w-4" /> PDF unico
                      </Button>
                    )}
                  </div>
                  <div className="space-y-1.5" data-testid="attachments-list">
                    {attachments.map((a) => (
                      <div key={a.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                        <button className="flex items-center gap-2 text-sky-700 hover:underline"
                                onClick={() => downloadBlob(`/attachments/${a.id}/download`, a.original_filename)}
                                data-testid={`attachment-download-${a.id}`}>
                          <Paperclip className="h-3.5 w-3.5" /> {a.original_filename}
                        </button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" data-testid={`attachment-delete-${a.id}`}
                                onClick={() => deleteAttachment(a)}>
                          <Trash2 className="h-3.5 w-3.5 text-rose-500" />
                        </Button>
                      </div>
                    ))}
                    {attachments.length === 0 && <p className="text-xs text-slate-400">Nessun allegato</p>}
                  </div>
                  <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 transition-colors hover:border-sky-400 hover:text-sky-700"
                         data-testid="attachment-upload-label">
                    <Upload className="h-4 w-4" /> Carica PDF o immagine
                    <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={uploadAttachment}
                           data-testid="attachment-upload-input" />
                  </label>
                </div>

                <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
                  {!detail.pagato_effettivo && (
                    <Button size="sm" onClick={() => markPaid(detail)} data-testid="detail-mark-paid-button"
                            className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                      <Wallet className="h-4 w-4" /> Segna pagato
                    </Button>
                  )}
                  <Button size="sm" variant="outline" data-testid="detail-edit-button"
                          onClick={() => { setEditing(detail); setFormOpen(true); }}>
                    <Pencil className="mr-2 h-4 w-4" /> Modifica
                  </Button>
                  {user.role === "admin" && (
                    <Button size="sm" variant="outline" data-testid="detail-delete-button"
                            className="text-rose-600 hover:text-rose-700" onClick={() => remove(detail)}>
                      <Trash2 className="mr-2 h-4 w-4" /> Elimina
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={importOpen} onOpenChange={(o) => { setImportOpen(o); if (!o) setImportResult(null); }}>
        <DialogContent data-testid="import-sheet-dialog">
          <DialogHeader><DialogTitle className="font-heading text-xl">Importa da Google Sheet</DialogTitle></DialogHeader>
          <form onSubmit={runImport} className="space-y-4" data-testid="import-sheet-form">
            <div className="space-y-1.5">
              <Label>Cosa importare</Label>
              <Select value={importMode} onValueChange={(v) => { setImportMode(v); setImportResult(null); }}>
                <SelectTrigger data-testid="import-mode-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="single">Una pagina (usa il link con gid della pagina)</SelectItem>
                  <SelectItem value="all">Tutte le pagine — una per negozio</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Link del foglio Google *</Label>
              <Input required value={importUrl} onChange={(e) => setImportUrl(e.target.value)}
                     placeholder="https://docs.google.com/spreadsheets/d/..." data-testid="import-sheet-url-input" />
              <p className="text-xs text-slate-500">
                Il foglio deve essere condiviso con "Chiunque abbia il link può visualizzare".
                {importMode === "all"
                  ? " Ogni pagina deve avere lo stesso nome del negozio (es. Tirano, Sondalo, Gravedona...)."
                  : " Per importare una pagina specifica, aprila nel foglio e copia il link (contiene gid=...)."}
              </p>
            </div>
            {importMode === "single" && (
              <div className="space-y-1.5">
                <Label>Assegna al negozio</Label>
                <Select value={importStore} onValueChange={setImportStore}>
                  <SelectTrigger data-testid="import-sheet-store-select"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                  <SelectContent>
                    {meta.stores.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.nome}{s.referente ? ` (${s.referente})` : ""}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {importResult && (
              <div className="max-h-48 space-y-1.5 overflow-y-auto rounded-lg border border-slate-200 p-3" data-testid="import-report">
                {importResult.report.map((r) => (
                  <div key={r.store} className="flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-800">{r.store}</span>
                    {r.status === "ok"
                      ? <span className="text-xs font-semibold text-emerald-700">{r.imported} importati{r.skipped ? `, ${r.skipped} saltati` : ""}</span>
                      : <span className="text-xs font-semibold text-rose-600" title={r.detail || ""}>Pagina non trovata</span>}
                  </div>
                ))}
                <p className="pt-1 text-xs text-slate-500">{importResult.hint}</p>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setImportOpen(false)} data-testid="import-sheet-cancel">Chiudi</Button>
              <Button type="submit" disabled={importing} className="bg-slate-900 hover:bg-slate-800" data-testid="import-sheet-submit">
                {importing ? "Importazione..." : "Importa clienti"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <ClientForm open={formOpen} onClose={() => setFormOpen(false)} client={editing} meta={meta} onSaved={load} />
    </div>
  );
}
