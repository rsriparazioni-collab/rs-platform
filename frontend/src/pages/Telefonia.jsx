import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Smartphone, CheckCircle2, XCircle, Pencil, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { SERVIZIO_TIPI, servizioTipoLabel, fmtDate } from "../lib/constants";
import ServizioForm from "../components/ServizioForm";
import ServizioDetail from "../components/ServizioDetail";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const TEL_TIPI = SERVIZIO_TIPI.filter((t) => t.section === "telefonia");

export default function Telefonia() {
  const { user } = useAuth();
  const [tab, setTab] = useState("servizi");
  const [servizi, setServizi] = useState([]);
  const [vincoli, setVincoli] = useState([]);
  const [meta, setMeta] = useState({ stores: [], operators: [] });
  const [filters, setFilters] = useState({ q: "", tipo: "all" });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detailRow, setDetailRow] = useState(null);
  const canSeeAll = user.role === "admin" || user.can_view_all;

  const load = useCallback(() => {
    const params = {};
    if (filters.q) params.q = filters.q;
    if (filters.tipo !== "all") params.tipo = filters.tipo;
    api.get("/servizi", { params }).then((r) => {
      setServizi(r.data.filter((s) => TEL_TIPI.some((t) => t.id === s.tipo)));
    }).catch((e) => toast.error(apiError(e, "Impossibile caricare i servizi")));
  }, [filters]);

  const loadVincoli = useCallback(() => {
    api.get("/vincoli", { params: { giorni: 3650 } }).then((r) => setVincoli(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare i vincoli")));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadVincoli(); }, [loadVincoli]);
  useEffect(() => {
    api.get("/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const storeName = (id) => meta.stores.find((s) => s.id === id)?.nome || "-";

  return (
    <div className="space-y-6" data-testid="telefonia-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Telefonia</h1>
          <p className="mt-1 text-sm text-slate-500">SIM, internet, fisso, accessori e vendite</p>
        </div>
        <Button onClick={() => { setEditing(null); setFormOpen(true); }} data-testid="add-servizio-tel-button"
                className="gap-2 bg-slate-900 hover:bg-slate-800">
          <Plus className="h-4 w-4" /> Nuovo servizio
        </Button>
      </div>

      <div className="flex gap-2 border-b border-slate-200" data-testid="telefonia-tabs">
        {[{ id: "servizi", label: "Servizi" }, { id: "vincoli", label: `Vincoli (${vincoli.length})` }].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
                  className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
                    tab === t.id ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "servizi" && (
        <>
          <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="telefonia-filters">
            <div className="relative min-w-[220px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input placeholder="Cerca cliente, numero, operatore..." className="pl-9" value={filters.q}
                     onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} data-testid="telefonia-search" />
            </div>
            <Select value={filters.tipo} onValueChange={(v) => setFilters((f) => ({ ...f, tipo: v }))}>
              <SelectTrigger className="w-[180px]" data-testid="telefonia-tipo-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tutti i tipi</SelectItem>
                {TEL_TIPI.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="telefonia-table">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-3">Cliente</th>
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Operatore / Prodotto</th>
                    <th className="px-4 py-3">Numero</th>
                    <th className="px-4 py-3">Vincolo</th>
                    {canSeeAll && <th className="px-4 py-3">Negozio</th>}
                    <th className="px-4 py-3">Pagato</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {servizi.map((s, i) => (
                    <tr key={s.id} className="cursor-pointer transition-colors hover:bg-slate-50"
                        onClick={() => setDetailRow(s)} data-testid={`telefonia-row-${i}`}>
                      <td className="px-4 py-3 font-medium text-slate-900">{s.client_name || "-"}</td>
                      <td className="px-4 py-3">
                        <span className="status-badge bg-sky-500/15 text-sky-700 border-sky-300">
                          <Smartphone className="h-3 w-3" /> {servizioTipoLabel(s.tipo)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{s.operatore_tel || s.prodotto || "-"}</td>
                      <td className="px-4 py-3 text-slate-600">{s.numero || "-"}</td>
                      <td className="px-4 py-3">
                        {s.scadenza_vincolo ? (
                          <span className={`text-xs font-semibold ${s.giorni_alla_scadenza <= 60 ? "text-amber-700" : "text-slate-500"}`}>
                            {fmtDate(s.scadenza_vincolo)}
                          </span>
                        ) : <span className="text-slate-400">-</span>}
                      </td>
                      {canSeeAll && <td className="px-4 py-3 text-slate-600">{storeName(s.venditore_id)}</td>}
                      <td className="px-4 py-3">
                        {s.pagato
                          ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300"><CheckCircle2 className="h-3 w-3" /> Pagato</span>
                          : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300"><XCircle className="h-3 w-3" /> Non pagato</span>}
                      </td>
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="icon" data-testid={`telefonia-edit-${i}`}
                                onClick={() => { setEditing(s); setFormOpen(true); }}>
                          <Pencil className="h-4 w-4 text-slate-500" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {servizi.length === 0 && (
                    <tr><td colSpan={8} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="telefonia-empty">
                      Nessun servizio di telefonia presente.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === "vincoli" && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="vincoli-table">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Cliente</th>
                  <th className="px-4 py-3">Tipo</th>
                  <th className="px-4 py-3">Operatore</th>
                  <th className="px-4 py-3">Attivazione</th>
                  <th className="px-4 py-3">Scadenza vincolo</th>
                  <th className="px-4 py-3">Stato</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {vincoli.map((s, i) => (
                  <tr key={s.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setDetailRow(s)} data-testid={`vincolo-row-${i}`}>
                    <td className="px-4 py-3 font-medium text-slate-900">{s.client_name || "-"}</td>
                    <td className="px-4 py-3">{servizioTipoLabel(s.tipo)}</td>
                    <td className="px-4 py-3 text-slate-600">{s.operatore_tel || "-"}</td>
                    <td className="px-4 py-3 text-slate-600">{fmtDate(s.data_attivazione)}</td>
                    <td className="px-4 py-3 font-medium">{fmtDate(s.scadenza_vincolo)}</td>
                    <td className="px-4 py-3">
                      {s.giorni_alla_scadenza < 0
                        ? <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300"><AlertTriangle className="h-3 w-3" /> Scaduto da {-s.giorni_alla_scadenza} gg</span>
                        : s.giorni_alla_scadenza <= 60
                          ? <span className="status-badge bg-amber-500/15 text-amber-700 border-amber-300">In scadenza tra {s.giorni_alla_scadenza} gg</span>
                          : <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">Attivo ({s.giorni_alla_scadenza} gg)</span>}
                    </td>
                  </tr>
                ))}
                {vincoli.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="vincoli-empty">
                    Nessun vincolo registrato. I vincoli compaiono quando inserisci data attivazione + durata in mesi (es. WindTre 48 mesi).
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <ServizioDetail servizio={detailRow} onClose={() => setDetailRow(null)} onChanged={() => { load(); loadVincoli(); }}
                      onEdit={(s) => { setEditing(s); setFormOpen(true); }}
                      isAdmin={user.role === "admin"} />
      <ServizioForm open={formOpen} onClose={() => setFormOpen(false)} servizio={editing}
                    defaultTipo={null} meta={meta} onSaved={() => { load(); loadVincoli(); }} />
    </div>
  );
}
