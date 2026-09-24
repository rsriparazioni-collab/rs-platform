import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, ShoppingBag, Trash2, Wrench, Smartphone, Wifi, PackageOpen, Zap, FileDown } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtDate, VENDITE_CATEGORIE, venditaCategoriaLabel, REGIMI_IVA, regimeIvaLabel, regimeIvaBadge } from "../lib/constants";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import VenditaForm from "../components/VenditaForm";
import ServizioForm from "../components/ServizioForm";

const eur = (v) => (v == null ? "-" : `€ ${Number(v).toFixed(2)}`);

export default function Vendite() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [meta, setMeta] = useState({ stores: [] });
  const [filters, setFilters] = useState({ q: "", categoria: "all", regime_iva: "all", store_id: "all" });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);
  const [servizioForm, setServizioForm] = useState(null);
  const [importing, setImporting] = useState(false);
  const presetClientId = useMemo(() => new URLSearchParams(window.location.search).get("cliente"), []);
  const canSeeAll = user.role === "admin" || user.can_view_all || user.role === "tecnico";

  const load = useCallback(() => {
    const params = {};
    if (filters.q) params.q = filters.q;
    if (filters.categoria !== "all") params.categoria = filters.categoria;
    if (filters.regime_iva !== "all") params.regime_iva = filters.regime_iva;
    if (filters.store_id !== "all") params.store_id = filters.store_id;
    api.get("/vendite", { params }).then((r) => setRows(r.data)).catch(() => toast.error("Errore caricamento vendite"));
    api.get("/vendite/stats", { params: filters.store_id !== "all" ? { store_id: filters.store_id } : {} }).then((r) => setStats(r.data)).catch(() => {});
  }, [filters]);

  useEffect(() => { api.get("/meta").then((r) => setMeta(r.data)).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (presetClientId) { setEditing(null); setFormOpen(true); } }, [presetClientId]);

  const remove = async (v) => {
    if (!window.confirm("Eliminare questa vendita? Se collegata al magazzino la giacenza viene ripristinata.")) return;
    try { await api.delete(`/vendite/${v.id}`); toast.success("Vendita eliminata"); setDetail(null); load(); }
    catch (e) { toast.error(apiError(e, "Eliminazione fallita")); }
  };

  const importaFoglio = async () => {
    setImporting(true);
    try {
      const r = await api.post("/vendite/import-sheet", {
        sheet_url: "https://docs.google.com/spreadsheets/d/1_j80xlW3jfMPwoULx50u0EfDMBlJiOVj0G3pjD_EMBw/edit",
        gids: { "1195285320": "Morbegno", "1042530783": "Sondrio", "1560914735": "Gravedona" },
      });
      toast.success(`Import: ${r.data.vendite} vendite, ${r.data.in_vendita_magazzino} in vendita → magazzino, ${r.data.saltate} saltate`);
      load();
    } catch (e) { toast.error(apiError(e, "Import fallito")); }
    finally { setImporting(false); }
  };

  const storeName = (id) => meta.stores.find((s) => s.id === id)?.nome || "-";

  return (
    <div className="space-y-6" data-testid="vendite-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Vendite</h1>
          <p className="mt-1 text-sm text-slate-500">Telefoni nuovi, rigenerati, usati, PC, router, accessori, stampanti — con regime IVA</p>
        </div>
        <div className="flex gap-2">
          {(user.role === "admin" || user.can_view_all) && (
            <Button variant="outline" onClick={importaFoglio} disabled={importing} className="gap-2" data-testid="vendite-import-button">
              <FileDown className="h-4 w-4" /> {importing ? "Importo..." : "Importa registro 2026"}
            </Button>
          )}
          <Button onClick={() => { setEditing(null); setFormOpen(true); }} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="vendite-add-button">
            <Plus className="h-4 w-4" /> Nuova vendita
          </Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5" data-testid="vendite-kpi">
          <Kpi label="Vendite" value={stats.totale.n} />
          <Kpi label="Incasso" value={eur(stats.totale.incasso)} />
          <Kpi label="Margine" value={eur(stats.totale.margine)} accent />
          {REGIMI_IVA.map((r) => <Kpi key={r.id} label={r.label} value={`${stats.per_iva[r.id]?.n || 0} · ${eur(stats.per_iva[r.id]?.incasso || 0)}`} small />).slice(0, 2)}
        </div>
      )}

      <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Cerca articolo, cliente, IMEI, fattura..." className="pl-9" value={filters.q}
                 onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} data-testid="vendite-search" />
        </div>
        <Select value={filters.categoria} onValueChange={(v) => setFilters((f) => ({ ...f, categoria: v }))}>
          <SelectTrigger className="w-[200px]" data-testid="vendite-filter-categoria"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutte le categorie</SelectItem>
            {VENDITE_CATEGORIE.map((c) => <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.regime_iva} onValueChange={(v) => setFilters((f) => ({ ...f, regime_iva: v }))}>
          <SelectTrigger className="w-[190px]" data-testid="vendite-filter-iva"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti i regimi IVA</SelectItem>
            {REGIMI_IVA.map((r) => <SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>
        {canSeeAll && (
          <Select value={filters.store_id} onValueChange={(v) => setFilters((f) => ({ ...f, store_id: v }))}>
            <SelectTrigger className="w-[170px]" data-testid="vendite-filter-store"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti i negozi</SelectItem>
              {meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Data</th><th className="px-4 py-3">Articolo</th><th className="px-4 py-3">Categoria</th>
              <th className="px-4 py-3">IVA</th><th className="px-4 py-3">Cliente</th><th className="px-4 py-3">Negozio</th>
              <th className="px-4 py-3 text-right">Prezzo</th><th className="px-4 py-3 text-right">Margine</th><th className="px-4 py-3">Fattura</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-slate-500" data-testid="vendite-empty">Nessuna vendita registrata</td></tr>
            )}
            {rows.map((v, i) => (
              <tr key={v.id} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => setDetail(v)} data-testid={`vendita-row-${i}`}>
                <td className="px-4 py-3 text-slate-600">{fmtDate(v.data_vendita)}</td>
                <td className="px-4 py-3 font-medium text-slate-900"><span className="flex items-center gap-2"><ShoppingBag className="h-3.5 w-3.5 text-slate-400" />{v.articolo}{v.imei ? <span className="font-mono text-[10px] text-slate-500">{v.imei}</span> : null}</span></td>
                <td className="px-4 py-3 text-slate-600">{venditaCategoriaLabel(v.categoria)}</td>
                <td className="px-4 py-3"><span className={`status-badge ${regimeIvaBadge(v.regime_iva)}`}>{regimeIvaLabel(v.regime_iva)}</span></td>
                <td className="px-4 py-3 text-slate-700">{v.client_name || v.cliente_nome || "-"}</td>
                <td className="px-4 py-3 text-slate-600">{storeName(v.store_id)}</td>
                <td className="px-4 py-3 text-right font-semibold">{eur(v.prezzo * (v.quantita || 1))}</td>
                <td className="px-4 py-3 text-right text-emerald-700">{v.costo != null ? eur((v.prezzo - v.costo) * (v.quantita || 1)) : "-"}</td>
                <td className="px-4 py-3 text-slate-600">{v.numero_fattura || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <VenditaForm open={formOpen} onClose={() => { setFormOpen(false); if (presetClientId) navigate("/vendite", { replace: true }); }}
                   vendita={editing} meta={meta} presetClientId={presetClientId} onSaved={() => { setFormOpen(false); load(); }} />

      <Dialog open={Boolean(detail)} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl" data-testid="vendita-detail">
          {detail && (
            <>
              <DialogHeader><DialogTitle className="font-heading text-xl">{detail.articolo}</DialogTitle></DialogHeader>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <Info l="Categoria" v={venditaCategoriaLabel(detail.categoria)} />
                <Info l="Regime IVA" v={regimeIvaLabel(detail.regime_iva)} />
                <Info l="Negozio" v={storeName(detail.store_id)} />
                <Info l="Cliente" v={detail.client_name || detail.cliente_nome || "-"} />
                <Info l="Telefono" v={detail.client_telefono || "-"} />
                <Info l="Data" v={fmtDate(detail.data_vendita)} />
                <Info l="Prezzo" v={eur(detail.prezzo)} />
                <Info l="Costo" v={eur(detail.costo)} />
                <Info l="Quantità" v={detail.quantita || 1} />
                <Info l="IMEI / Serial" v={detail.imei || "-"} />
                <Info l="Pagamento" v={detail.pagamento || "-"} />
                <Info l="N° fattura" v={detail.numero_fattura || "-"} />
                {detail.note && <div className="col-span-full"><p className="text-xs text-slate-500">Note</p><p>{detail.note}</p></div>}
              </div>
              {detail.client_id && (
                <div className="rounded-xl border border-sky-200 bg-sky-50/50 p-4" data-testid="vendita-aggiungi-al-cliente">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Aggiungi al cliente</p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setServizioForm({ tipo: "riparazione", client: { id: detail.client_id, label: detail.client_name } })} data-testid="vendita-add-riparazione"><Wrench className="h-4 w-4" /> Riparazione</Button>
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setServizioForm({ tipo: "sim", client: { id: detail.client_id, label: detail.client_name } })} data-testid="vendita-add-sim"><Smartphone className="h-4 w-4" /> SIM</Button>
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setServizioForm({ tipo: "internet", client: { id: detail.client_id, label: detail.client_name } })} data-testid="vendita-add-internet"><Wifi className="h-4 w-4" /> Internet / Fisso</Button>
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => navigate(`/ritiri?cliente=${detail.client_id}`)} data-testid="vendita-add-ritiro"><PackageOpen className="h-4 w-4" /> Ritiro telefono</Button>
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => navigate(`/clienti?apri=${detail.client_id}`)} data-testid="vendita-add-utenza"><Zap className="h-4 w-4" /> Scheda cliente / Utenze</Button>
                  </div>
                </div>
              )}
              <div className="flex justify-between">
                <Button variant="outline" size="sm" onClick={() => { setEditing(detail); setDetail(null); setFormOpen(true); }} data-testid="vendita-edit-button">Modifica</Button>
                <Button variant="outline" size="sm" className="text-rose-600" onClick={() => remove(detail)} data-testid="vendita-delete-button"><Trash2 className="mr-2 h-4 w-4" /> Elimina</Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
      <ServizioForm open={Boolean(servizioForm)} onClose={() => setServizioForm(null)} servizio={null} defaultTipo={servizioForm?.tipo}
                    presetClient={servizioForm?.client} meta={meta} onSaved={() => { setServizioForm(null); toast.success("Servizio aggiunto al cliente"); }} />
    </div>
  );
}

function Kpi({ label, value, accent, small }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`${small ? "text-base" : "text-2xl"} font-bold ${accent ? "text-emerald-700" : "text-slate-900"}`}>{value}</p>
    </div>
  );
}

function Info({ l, v }) {
  return <div><p className="text-xs text-slate-500">{l}</p><p className="font-medium">{v}</p></div>;
}
