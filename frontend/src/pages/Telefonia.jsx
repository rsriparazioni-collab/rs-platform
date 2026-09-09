import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Smartphone, Phone, CheckCircle2, XCircle, Pencil, AlertTriangle, Lightbulb } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { servizioTipoLabel, fmtDate } from "../lib/constants";
import ServizioForm from "../components/ServizioForm";
import ServizioDetail from "../components/ServizioDetail";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

const SEZIONI = {
  mobile: { label: "Mobile", tipi: ["sim"], defaultTipo: "sim", icon: Smartphone },
  fisso: { label: "Fisso", tipi: ["internet", "fisso"], defaultTipo: "internet", icon: Phone },
};

function VincoloBadge({ s }) {
  if (s.giorni_alla_scadenza == null) return <span className="text-slate-400">-</span>;
  if (s.giorni_alla_scadenza < 0) return <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300"><AlertTriangle className="h-3 w-3" /> Scaduto da {-s.giorni_alla_scadenza} gg</span>;
  if (s.giorni_alla_scadenza <= 60) return <span className="status-badge bg-amber-500/15 text-amber-700 border-amber-300">Scade tra {s.giorni_alla_scadenza} gg</span>;
  return <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">Attivo ({s.giorni_alla_scadenza} gg)</span>;
}

export default function Telefonia() {
  const { user } = useAuth();
  const [tab, setTab] = useState("mobile");
  const [servizi, setServizi] = useState([]);
  const [vincoli, setVincoli] = useState([]);
  const [proposte, setProposte] = useState([]);
  const [meta, setMeta] = useState({ stores: [], operators: [] });
  const [q, setQ] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [formTipo, setFormTipo] = useState("sim");
  const [editing, setEditing] = useState(null);
  const [detailRow, setDetailRow] = useState(null);
  const canSeeAll = user.role === "admin" || user.can_view_all;

  const load = useCallback(() => {
    api.get("/servizi", { params: q ? { q } : {} })
      .then((r) => setServizi(r.data.filter((s) => ["sim", "internet", "fisso"].includes(s.tipo))))
      .catch((e) => toast.error(apiError(e, "Impossibile caricare i servizi")));
    api.get("/vincoli", { params: { giorni: 3650 } }).then((r) => setVincoli(r.data)).catch(() => {});
    api.get("/telefonia/proposte").then((r) => setProposte(r.data)).catch(() => {});
  }, [q]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/meta").then((r) => setMeta(r.data)).catch(() => {}); }, []);

  const storeName = (id) => meta.stores.find((s) => s.id === id)?.nome || "-";
  const openNew = (tipo) => { setEditing(null); setFormTipo(tipo); setFormOpen(true); };
  const sez = SEZIONI[tab];
  const rows = sez ? servizi.filter((s) => sez.tipi.includes(s.tipo)) : [];
  const inScadenza = vincoli.filter((v) => v.giorni_alla_scadenza <= 60).length;

  const tabs = [
    { id: "mobile", label: `Mobile (${servizi.filter((s) => s.tipo === "sim").length})` },
    { id: "fisso", label: `Fisso (${servizi.filter((s) => s.tipo !== "sim").length})` },
    { id: "vincoli", label: `Vincoli in scadenza (${inScadenza})` },
    { id: "proposte", label: `Da proporre (${proposte.length})` },
  ];

  return (
    <div className="space-y-6" data-testid="telefonia-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Telefonia</h1>
          <p className="mt-1 text-sm text-slate-500">Mobile e Fisso con vincoli, scadenze e clienti da proporre</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => openNew("sim")} data-testid="add-mobile-button" className="gap-2 bg-slate-900 hover:bg-slate-800">
            <Smartphone className="h-4 w-4" /> Nuovo Mobile
          </Button>
          <Button onClick={() => openNew("internet")} data-testid="add-fisso-button" variant="outline" className="gap-2">
            <Phone className="h-4 w-4" /> Nuovo Fisso
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200" data-testid="telefonia-tabs">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
                  className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
                    tab === t.id ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {sez && (
        <>
          <div className="relative rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="telefonia-filters">
            <Search className="absolute left-7 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input placeholder="Cerca cliente, numero, operatore..." className="pl-9" value={q}
                   onChange={(e) => setQ(e.target.value)} data-testid="telefonia-search" />
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="telefonia-table">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-3">Cliente</th>
                    <th className="px-4 py-3">Operatore</th>
                    <th className="px-4 py-3">Numero</th>
                    <th className="px-4 py-3">Attivazione</th>
                    <th className="px-4 py-3">Vincolo</th>
                    <th className="px-4 py-3">Scadenza</th>
                    {canSeeAll && <th className="px-4 py-3">Negozio</th>}
                    <th className="px-4 py-3">Pagato</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((s, i) => (
                    <tr key={s.id} className="cursor-pointer transition-colors hover:bg-slate-50"
                        onClick={() => setDetailRow(s)} data-testid={`telefonia-row-${i}`}>
                      <td className="px-4 py-3 font-medium text-slate-900">{s.client_name || "-"}
                        {tab === "fisso" && <span className="ml-2 text-xs text-slate-400">{servizioTipoLabel(s.tipo)}</span>}</td>
                      <td className="px-4 py-3"><span className="status-badge bg-sky-500/15 text-sky-700 border-sky-300"><sez.icon className="h-3 w-3" /> {s.operatore_tel || "-"}</span></td>
                      <td className="px-4 py-3 text-slate-600">{s.numero || "-"}</td>
                      <td className="px-4 py-3 text-slate-600">{fmtDate(s.data_attivazione)}</td>
                      <td className="px-4 py-3 text-slate-600">{s.vincolo_mesi != null ? `${s.vincolo_mesi} mesi` : "-"}</td>
                      <td className="px-4 py-3"><VincoloBadge s={s} /></td>
                      {canSeeAll && <td className="px-4 py-3 text-slate-600">{storeName(s.venditore_id)}</td>}
                      <td className="px-4 py-3">
                        {s.pagato
                          ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300"><CheckCircle2 className="h-3 w-3" /> Pagato</span>
                          : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300"><XCircle className="h-3 w-3" /> Non pagato</span>}
                      </td>
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="icon" data-testid={`telefonia-edit-${i}`} onClick={() => { setEditing(s); setFormTipo(s.tipo); setFormOpen(true); }}>
                          <Pencil className="h-4 w-4 text-slate-500" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr><td colSpan={9} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="telefonia-empty">
                      Nessun servizio {sez.label.toLowerCase()} presente.
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
          <p className="border-b border-slate-200 px-4 py-3 text-xs text-slate-500">Alla scadenza del vincolo avvisa il cliente: ci sono nuove offerte. In evidenza quelli entro 60 giorni o già scaduti.</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Cliente</th><th className="px-4 py-3">Tipo</th><th className="px-4 py-3">Operatore</th>
                <th className="px-4 py-3">Attivazione</th><th className="px-4 py-3">Vincolo</th><th className="px-4 py-3">Scadenza</th><th className="px-4 py-3">Stato</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {vincoli.map((s, i) => (
                <tr key={s.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setDetailRow(s)} data-testid={`vincolo-row-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{s.client_name || "-"}</td>
                  <td className="px-4 py-3">{s.tipo === "sim" ? "Mobile" : "Fisso"}</td>
                  <td className="px-4 py-3 text-slate-600">{s.operatore_tel || "-"}</td>
                  <td className="px-4 py-3 text-slate-600">{fmtDate(s.data_attivazione)}</td>
                  <td className="px-4 py-3 text-slate-600">{s.vincolo_mesi} mesi</td>
                  <td className="px-4 py-3 font-medium">{fmtDate(s.scadenza_vincolo)}</td>
                  <td className="px-4 py-3"><VincoloBadge s={s} /></td>
                </tr>
              ))}
              {vincoli.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="vincoli-empty">
                  Nessun vincolo registrato: inserisci data attivazione e mesi di vincolo nei servizi.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "proposte" && (
        <div className="overflow-hidden rounded-xl border border-amber-200 bg-white shadow-sm" data-testid="proposte-table">
          <p className="flex items-center gap-2 border-b border-amber-100 px-4 py-3 text-xs text-slate-600">
            <Lightbulb className="h-4 w-4 text-amber-600" /> Clienti con Mobile ma senza Fisso e/o senza contratto energia: da contattare per una proposta.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Cliente</th><th className="px-4 py-3">Telefono</th><th className="px-4 py-3">Mobile con</th>
                <th className="px-4 py-3">Da proporre</th>{canSeeAll && <th className="px-4 py-3">Negozio</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {proposte.map((p, i) => (
                <tr key={p.client_id} data-testid={`proposta-row-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{p.client_name}</td>
                  <td className="px-4 py-3 text-slate-600">{p.telefono || "-"}</td>
                  <td className="px-4 py-3 text-slate-600">{p.operatore_mobile || "-"}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {p.manca_fisso && <span className="status-badge bg-sky-500/15 text-sky-700 border-sky-300">Fisso</span>}
                      {p.manca_energia && <span className="status-badge bg-amber-500/15 text-amber-700 border-amber-300">Energia</span>}
                    </div>
                  </td>
                  {canSeeAll && <td className="px-4 py-3 text-slate-600">{storeName(p.venditore_id)}</td>}
                </tr>
              ))}
              {proposte.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="proposte-empty">Nessun cliente da proporre.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <ServizioDetail servizio={detailRow} onClose={() => setDetailRow(null)} onChanged={load}
                      onEdit={(s) => { setEditing(s); setFormTipo(s.tipo); setFormOpen(true); }} isAdmin={user.role === "admin"} />
      <ServizioForm open={formOpen} onClose={() => setFormOpen(false)} servizio={editing}
                    defaultTipo={formTipo} meta={meta} onSaved={load} />
    </div>
  );
}
