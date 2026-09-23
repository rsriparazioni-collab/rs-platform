import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Zap, Flame, CheckCircle2, XCircle, Pencil, Upload, Download, Crown, Ban, Wrench, Smartphone, Wifi, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import SyncFogliDialog from "../components/SyncFogliDialog";
import { useAuth } from "../context/AuthContext";
import { LAVORAZIONI, lavorazioneLabel, lavorazioneBadge, fmtDate, PREMIUM_STEPS, tipoClienteInfo, isBusinessCliente } from "../lib/constants";

const TIPI_SERVIZI = {
  luce: { label: "Luce", badge: "bg-sky-50 text-sky-700", icon: <Zap className="h-3 w-3" /> },
  gas: { label: "Gas", badge: "bg-orange-50 text-orange-700", icon: <Flame className="h-3 w-3" /> },
  rip: { label: "Rip", badge: "bg-violet-50 text-violet-700", icon: <Wrench className="h-3 w-3" /> },
  mob: { label: "Mob", badge: "bg-emerald-50 text-emerald-700", icon: <Smartphone className="h-3 w-3" /> },
  fis: { label: "Fis", badge: "bg-indigo-50 text-indigo-700", icon: <Wifi className="h-3 w-3" /> },
};
import ClientForm from "../components/ClientForm";
import ClientDetail from "../components/ClientDetail";
import ServizioForm from "../components/ServizioForm";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Label } from "../components/ui/label";

export default function Clienti() {
  const { user } = useAuth();
  const [clients, setClients] = useState([]);
  const [meta, setMeta] = useState({ suppliers: [], lavorazioni: [], stores: [], operators: [] });
  const [filters, setFilters] = useState({ q: "", lavorazione: "all", tipo_bolletta: "all", venditore_id: "all", no_recensioni: false, tipo_cliente: "all",
    gestione: localStorage.getItem("clienti_gestione") || "all" });
  const [conteggi, setConteggi] = useState(null);
  const setGestione = (g) => { localStorage.setItem("clienti_gestione", g); setFilters((f) => ({ ...f, gestione: g })); };
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [prefill, setPrefill] = useState(null);
  const [servizioForm, setServizioForm] = useState(null);
  const navigate = useNavigate();
  const [detailRow, setDetailRow] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importStore, setImportStore] = useState("");
  const [importMode, setImportMode] = useState("single");
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const canSeeAll = user.role === "admin" || user.can_view_all;

  const load = useCallback(() => {
    const params = {};
    if (filters.q) params.q = filters.q;
    if (filters.lavorazione !== "all") params.lavorazione = filters.lavorazione;
    if (filters.tipo_bolletta !== "all") params.tipo_servizio = filters.tipo_bolletta;
    if (filters.venditore_id !== "all") params.venditore_id = filters.venditore_id;
    if (filters.no_recensioni) params.no_recensioni = "1";
    if (filters.tipo_cliente !== "all") params.tipo_cliente = filters.tipo_cliente;
    if (filters.gestione !== "all") params.gestione = filters.gestione;
    api.get("/clients/conteggio-gestione").then((r) => setConteggi(r.data)).catch(() => {});
    api.get("/clients", { params }).then((r) => setClients(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare i clienti")));
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const storeName = (id) => meta.stores.find((s) => s.id === id)?.nome || "-";

  const exportExcel = async () => {
    try {
      const res = await api.get("/export/clients.xlsx", { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(res.data);
      a.download = `report_clienti_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      toast.error(apiError(e, "Export fallito"));
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

  return (
    <div className="space-y-6" data-testid="clienti-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Clienti</h1>
          <p className="mt-1 text-sm text-slate-500">{clients.length} utenze {canSeeAll ? "in totale" : "del tuo negozio"}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportExcel} data-testid="export-excel-button" className="gap-2">
            <Download className="h-4 w-4" /> Esporta Excel
          </Button>
          {user.role === "admin" && (
            <Button variant="outline" onClick={() => setSyncOpen(true)} data-testid="sync-fogli-button" className="gap-2">
              <RefreshCw className="h-4 w-4" /> Sincronizza fogli Google
            </Button>
          )}
          {user.role === "admin" && (
            <Button variant="outline" onClick={() => { setImportStore(meta.stores[0]?.id || ""); setImportOpen(true); }}
                    data-testid="import-sheet-button" className="gap-2">
              <Upload className="h-4 w-4" /> Importa da Google Sheet
            </Button>
          )}
          <Button onClick={() => { setEditing(null); setPrefill(null); setFormOpen(true); }} data-testid="add-client-button"
                  className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Plus className="h-4 w-4" /> Nuovo cliente
          </Button>
        </div>
      </div>

      <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm" data-testid="gestione-switch" role="tablist">
        {[
          { id: "all", label: "Tutti", cls: "bg-slate-900 text-white" },
          { id: "cambiaora", label: "CambiaOra", cls: "bg-fuchsia-600 text-white" },
          { id: "enel", label: "ENEL", cls: "bg-amber-500 text-white" },
        ].map((g) => (
          <button key={g.id} type="button" role="tab" aria-selected={filters.gestione === g.id} onClick={() => setGestione(g.id)}
                  data-testid={`gestione-tab-${g.id}`}
                  className={`flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold transition-colors ${filters.gestione === g.id ? g.cls : "text-slate-600 hover:bg-slate-100"}`}>
            {g.label}
            {conteggi && <span className={`rounded-full px-2 py-0.5 text-xs ${filters.gestione === g.id ? "bg-white/25" : "bg-slate-100 text-slate-600"}`}>{conteggi[g.id === "all" ? "tutti" : g.id]}</span>}
          </button>
        ))}
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
          <SelectTrigger className="w-[160px]" data-testid="filter-tipo-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti i tipi</SelectItem>
            <SelectItem value="luce">Luce</SelectItem>
            <SelectItem value="gas">Gas</SelectItem>
            <SelectItem value="rip">Rip (riparazioni)</SelectItem>
            <SelectItem value="mob">Mob (mobile)</SelectItem>
            <SelectItem value="fis">Fis (fisso/internet)</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.tipo_cliente} onValueChange={(v) => setFilters((f) => ({ ...f, tipo_cliente: v }))}>
          <SelectTrigger className="w-[190px]" data-testid="filter-tipo-cliente-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Privati e Business</SelectItem>
            <SelectItem value="privato">Solo privati</SelectItem>
            <SelectItem value="business">Solo business</SelectItem>
            <SelectItem value="ditta_individuale">Ditte individuali</SelectItem>
            <SelectItem value="societa">Società</SelectItem>
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
        <Button type="button" variant={filters.no_recensioni ? "default" : "outline"} size="sm" className="h-10 gap-1.5"
                onClick={() => setFilters((f) => ({ ...f, no_recensioni: !f.no_recensioni }))} data-testid="filter-blacklist-toggle">
          <Ban className="h-4 w-4" /> Solo blacklist recensioni
        </Button>
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
                    onClick={() => setDetailRow(c)} data-testid={`client-row-${i}`}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">
                      {c.cognome} {c.nome}
                      {c.gestione === "enel" && filters.gestione === "all" && (
                        <span className="ml-2 status-badge bg-amber-500/15 text-amber-700 border-amber-300" data-testid={`client-enel-${i}`}>ENEL</span>
                      )}
                      {isBusinessCliente(c.tipo_cliente) && (
                        <span className={`ml-2 status-badge ${tipoClienteInfo(c.tipo_cliente).badge}`} data-testid={`client-business-${i}`}>
                          {tipoClienteInfo(c.tipo_cliente).label}
                        </span>
                      )}
                      {c.premium_step > 0 && (
                        <span className={`ml-2 status-badge ${PREMIUM_STEPS[c.premium_step]?.badge}`} data-testid={`client-premium-${i}`}>
                          {c.premium_step === 3 && <Crown className="h-3 w-3" />}
                          {PREMIUM_STEPS[c.premium_step]?.label}
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500">{isBusinessCliente(c.tipo_cliente) ? `P.IVA ${c.p_iva || "-"} · ${c.telefono || ""}` : c.telefono}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex flex-wrap items-center gap-1" data-testid={`client-tipi-${i}`}>
                      {(c.tipi_servizi || []).map((t) => <span key={t} className={`status-badge ${TIPI_SERVIZI[t].badge}`}>{TIPI_SERVIZI[t].icon}{TIPI_SERVIZI[t].label}</span>)}
                      {!(c.tipi_servizi || []).length && <span className="text-xs text-slate-400">-</span>}
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
                            onClick={() => { setEditing(c); setPrefill(null); setFormOpen(true); }}>
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

      <ClientDetail client={detailRow} onClose={() => setDetailRow(null)} onChanged={load}
                    onEdit={(c) => { setEditing(c); setPrefill(null); setFormOpen(true); }}
                    isAdmin={user.role === "admin"}
                    onNuovaUtenza={(d, tipo) => {
                      const { id, created_at, updated_at, pod, pdr, kw_potenza, costo_kwh_attuale, costo_smc_attuale, costo_kwh_nuovo, costo_smc_nuovo,
                        spese_fisse_attuale, spese_fisse_nuovo, data_contratto, data_verifica, data_cambio, note, history, premium_step, tipi_servizi, ...anag } = d;
                      setEditing(null);
                      setPrefill({ ...anag, tipo_bolletta: tipo, lavorazione: "da_quotare", pagato: undefined, privacy_firmata: !!d.privacy_firmata });
                      setFormOpen(true);
                    }}
                    onNuovoServizio={(tipo, d) => {
                      if (tipo === "apri_utenza") { setDetailRow(d); return; }
                      if (tipo === "ritiro") { navigate(`/ritiri?cliente=${d.id}`); return; }
                      setServizioForm({ tipo, client: { id: d.id, label: `${d.cognome} ${d.nome}` } });
                    }} />
      <ServizioForm open={Boolean(servizioForm)} onClose={() => setServizioForm(null)} servizio={null}
                    defaultTipo={servizioForm?.tipo} presetClient={servizioForm?.client} meta={meta}
                    onSaved={() => { setServizioForm(null); load(); setDetailRow((r) => (r ? { ...r } : r)); }} />

      <SyncFogliDialog open={syncOpen} onClose={() => setSyncOpen(false)} onDone={load} />
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

      <ClientForm open={formOpen} onClose={() => { setFormOpen(false); setPrefill(null); }} client={editing} meta={meta} onSaved={load} prefill={prefill} />
    </div>
  );
}
