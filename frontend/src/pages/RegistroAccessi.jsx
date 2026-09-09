import { useCallback, useEffect, useState } from "react";
import { ScrollText, Search, Eye, Pencil, Trash2, Download, Plus, LogIn, LogOut, Upload, Shield } from "lucide-react";
import api from "../lib/api";
import { fmtDateTime } from "../lib/constants";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const ACTIONS = {
  view: { label: "Apertura", icon: Eye, cls: "bg-slate-500/10 text-slate-700 border-slate-300" },
  create: { label: "Creazione", icon: Plus, cls: "bg-emerald-500/15 text-emerald-700 border-emerald-300" },
  update: { label: "Modifica", icon: Pencil, cls: "bg-sky-500/15 text-sky-700 border-sky-300" },
  delete: { label: "Eliminazione", icon: Trash2, cls: "bg-rose-500/15 text-rose-700 border-rose-300" },
  export: { label: "Esportazione", icon: Download, cls: "bg-amber-500/15 text-amber-700 border-amber-300" },
  import: { label: "Importazione", icon: Upload, cls: "bg-amber-500/15 text-amber-700 border-amber-300" },
  login: { label: "Accesso", icon: LogIn, cls: "bg-violet-500/15 text-violet-700 border-violet-300" },
  logout: { label: "Uscita", icon: LogOut, cls: "bg-slate-500/10 text-slate-700 border-slate-300" },
};
const ENTITIES = { cliente: "Cliente", servizio: "Servizio", ritiro: "Ritiro", clienti: "Anagrafica", export: "Export", utente: "Utente", accesso: "Accesso", sicurezza: "Sicurezza" };

export default function RegistroAccessi() {
  const [rows, setRows] = useState([]);
  const [users, setUsers] = useState([]);
  const [f, setF] = useState({ q: "", user_id: "all", action: "all", entity: "all", dal: "", al: "" });

  const load = useCallback(() => {
    const params = {};
    if (f.q) params.q = f.q;
    if (f.user_id !== "all") params.user_id = f.user_id;
    if (f.action !== "all") params.action = f.action;
    if (f.entity !== "all") params.entity = f.entity;
    if (f.dal) params.dal = f.dal;
    if (f.al) params.al = f.al;
    api.get("/audit-log", { params }).then((r) => setRows(r.data)).catch(() => setRows([]));
  }, [f]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/users").then((r) => setUsers(r.data)).catch(() => {}); }, []);

  const exportCsv = () => {
    const head = ["Data", "Utente", "Ruolo", "Azione", "Tipo", "Elemento", "IP", "Percorso"];
    const lines = rows.map((r) => [fmtDateTime(r.at), r.user_name, r.user_role, ACTIONS[r.action]?.label || r.action, ENTITIES[r.entity] || r.entity, r.label, r.ip, r.path]
      .map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(";"));
    const blob = new Blob(["\uFEFF" + [head.join(";"), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "registro-accessi.csv"; a.click();
  };

  return (
    <div className="space-y-6" data-testid="registro-accessi-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Registro Accessi</h1>
          <p className="mt-1 text-sm text-slate-500">Chi ha aperto, modificato, esportato o eliminato dati (registro trattamenti GDPR)</p>
        </div>
        <Button variant="outline" onClick={exportCsv} className="gap-2" data-testid="audit-export-button"><Download className="h-4 w-4" /> Esporta CSV</Button>
      </div>

      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-6" data-testid="audit-filters">
        <div className="relative md:col-span-2">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Cerca cliente, utente..." className="pl-9" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} data-testid="audit-search" />
        </div>
        <Select value={f.user_id} onValueChange={(v) => setF({ ...f, user_id: v })}>
          <SelectTrigger data-testid="audit-user-filter"><SelectValue placeholder="Utente" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Tutti gli utenti</SelectItem>{users.map((u) => <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={f.action} onValueChange={(v) => setF({ ...f, action: v })}>
          <SelectTrigger data-testid="audit-action-filter"><SelectValue placeholder="Azione" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Tutte le azioni</SelectItem>{Object.entries(ACTIONS).map(([k, a]) => <SelectItem key={k} value={k}>{a.label}</SelectItem>)}</SelectContent>
        </Select>
        <Input type="date" value={f.dal} onChange={(e) => setF({ ...f, dal: e.target.value })} data-testid="audit-dal" />
        <Input type="date" value={f.al} onChange={(e) => setF({ ...f, al: e.target.value })} data-testid="audit-al" />
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="audit-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3">Data e ora</th><th className="px-4 py-3">Utente</th><th className="px-4 py-3">Azione</th>
              <th className="px-4 py-3">Elemento</th><th className="px-4 py-3">IP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r, i) => {
              const a = ACTIONS[r.action] || ACTIONS.view; const Icon = a.icon;
              return (
                <tr key={r.id} data-testid={`audit-row-${i}`}>
                  <td className="px-4 py-2.5 text-slate-600">{fmtDateTime(r.at)}</td>
                  <td className="px-4 py-2.5 font-medium text-slate-900">{r.user_name} <span className="text-xs text-slate-400">{r.user_role}</span></td>
                  <td className="px-4 py-2.5"><span className={`status-badge ${a.cls}`}><Icon className="h-3 w-3" /> {a.label}</span></td>
                  <td className="px-4 py-2.5 text-slate-700"><span className="text-xs text-slate-400">{ENTITIES[r.entity] || r.entity}</span> {r.label || <span className="text-slate-400">{r.path}</span>}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{r.ip}</td>
                </tr>
              );
            })}
            {rows.length === 0 && <tr><td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-500" data-testid="audit-empty"><ScrollText className="mx-auto mb-2 h-6 w-6 text-slate-300" />Nessuna attività registrata</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="flex items-center gap-1 text-xs text-slate-400"><Shield className="h-3 w-3" /> Vengono tracciati: apertura schede, creazioni, modifiche, eliminazioni, esportazioni/importazioni, accessi e modifiche sicurezza. Ultime {rows.length} voci.</p>
    </div>
  );
}
