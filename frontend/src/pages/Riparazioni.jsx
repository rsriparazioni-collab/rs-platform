import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Wrench, CheckCircle2, XCircle, Pencil } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { RIP_STATI, ripStatoLabel, ripStatoBadge } from "../lib/constants";
import ServizioForm from "../components/ServizioForm";
import ServizioDetail from "../components/ServizioDetail";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export default function Riparazioni() {
  const { user } = useAuth();
  const [servizi, setServizi] = useState([]);
  const [meta, setMeta] = useState({ stores: [], operators: [] });
  const [filters, setFilters] = useState({ q: "", stato: "all", venditore_id: "all" });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detailRow, setDetailRow] = useState(null);
  const canSeeAll = user.role === "admin" || user.role === "tecnico" || user.can_view_all;

  const load = useCallback(() => {
    const params = { tipo: "riparazione" };
    if (filters.q) params.q = filters.q;
    if (filters.stato !== "all") params.stato = filters.stato;
    if (filters.venditore_id !== "all") params.venditore_id = filters.venditore_id;
    api.get("/servizi", { params }).then((r) => setServizi(r.data))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare le riparazioni")));
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const storeName = (id) => meta.stores.find((s) => s.id === id)?.nome || "-";

  return (
    <div className="space-y-6" data-testid="riparazioni-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Riparazioni</h1>
          <p className="mt-1 text-sm text-slate-500">
            {servizi.length} riparazioni {canSeeAll ? "in totale" : "del tuo negozio"}
          </p>
        </div>
        <Button onClick={() => { setEditing(null); setFormOpen(true); }} data-testid="add-riparazione-button"
                className="gap-2 bg-slate-900 hover:bg-slate-800">
          <Plus className="h-4 w-4" /> Nuova riparazione
        </Button>
      </div>

      <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="riparazioni-filters">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Cerca cliente o dispositivo..." className="pl-9" value={filters.q}
                 onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} data-testid="riparazioni-search" />
        </div>
        <Select value={filters.stato} onValueChange={(v) => setFilters((f) => ({ ...f, stato: v }))}>
          <SelectTrigger className="w-[240px]" data-testid="riparazioni-stato-filter"><SelectValue /></SelectTrigger>
          <SelectContent className="max-h-72">
            <SelectItem value="all">Tutti gli stati</SelectItem>
            {RIP_STATI.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
          </SelectContent>
        </Select>
        {(user.role === "admin" || user.can_view_all) && (
          <Select value={filters.venditore_id} onValueChange={(v) => setFilters((f) => ({ ...f, venditore_id: v }))}>
            <SelectTrigger className="w-[200px]" data-testid="riparazioni-negozio-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti i negozi</SelectItem>
              {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="riparazioni-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Dispositivo</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">Prezzo cons.</th>
                {canSeeAll && <th className="px-4 py-3">Negozio</th>}
                <th className="px-4 py-3">Pagato</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {servizi.map((s, i) => (
                <tr key={s.id} className="cursor-pointer transition-colors hover:bg-slate-50"
                    onClick={() => setDetailRow(s)} data-testid={`riparazione-row-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{s.client_name || "-"}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5">
                      <Wrench className="h-3.5 w-3.5 text-slate-400" /> {s.dispositivo || "-"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`status-badge ${ripStatoBadge(s.stato)}`}>{ripStatoLabel(s.stato)}</span>
                  </td>
                  <td className="px-4 py-3 font-semibold text-emerald-700">
                    {s.prezzo_consigliato != null ? `€ ${s.prezzo_consigliato.toFixed(2)}` : "-"}
                  </td>
                  {canSeeAll && <td className="px-4 py-3 text-slate-600">{storeName(s.venditore_id)}</td>}
                  <td className="px-4 py-3">
                    {s.pagato
                      ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300"><CheckCircle2 className="h-3 w-3" /> Pagato</span>
                      : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300"><XCircle className="h-3 w-3" /> Non pagato</span>}
                  </td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="icon" data-testid={`riparazione-edit-${i}`}
                            onClick={() => { setEditing(s); setFormOpen(true); }}>
                      <Pencil className="h-4 w-4 text-slate-500" />
                    </Button>
                  </td>
                </tr>
              ))}
              {servizi.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="riparazioni-empty">
                  Nessuna riparazione trovata.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ServizioDetail servizio={detailRow} onClose={() => setDetailRow(null)} onChanged={load}
                      onEdit={(s) => { setEditing(s); setFormOpen(true); }}
                      isAdmin={user.role === "admin"} />
      <ServizioForm open={formOpen} onClose={() => setFormOpen(false)} servizio={editing}
                    defaultTipo="riparazione" meta={meta} onSaved={load} />
    </div>
  );
}
