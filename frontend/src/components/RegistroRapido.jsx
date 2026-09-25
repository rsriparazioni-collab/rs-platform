import { useCallback, useEffect, useState } from "react";
import { Zap, Trash2, UserRound, X } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

const AREE = [["energia", "Energia"], ["telefonia", "Telefonia"], ["internet", "Internet"], ["chiamate", "Chiamate"], ["riparazioni", "Riparazioni"]];

export default function RegistroRapido() {
  const [voci, setVoci] = useState([]);
  const [area, setArea] = useState(localStorage.getItem("rr_area") || "telefonia");
  const [oggi, setOggi] = useState([]);
  const [cliQ, setCliQ] = useState("");
  const [cliRes, setCliRes] = useState([]);
  const [cliente, setCliente] = useState(null);

  const load = useCallback(() => api.get("/attivita").then((r) => setOggi(r.data)).catch(() => {}), []);
  useEffect(() => { api.get("/kpi/voci").then((r) => setVoci(r.data.voci)).catch(() => {}); load(); }, [load]);
  useEffect(() => { localStorage.setItem("rr_area", area); }, [area]);
  useEffect(() => {
    if (cliQ.trim().length < 2) { setCliRes([]); return; }
    const t = setTimeout(() => api.get("/clients", { params: { q: cliQ.trim(), limit: 6 } }).then((r) => setCliRes((Array.isArray(r.data) ? r.data : r.data.items || []).slice(0, 6))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [cliQ]);

  const registra = async (voce, dettaglio = "") => {
    try {
      await api.post("/attivita", { voce: voce.id, quantita: 1, client_id: cliente?.id || "", dettaglio });
      toast.success(`+1 ${voce.label}${dettaglio ? ` (${dettaglio})` : ""}${cliente ? ` · ${cliente.cognome} ${cliente.nome}` : ""}`);
      load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const elimina = async (a) => { try { await api.delete(`/attivita/${a.id}`); load(); } catch (e) { toast.error(apiError(e)); } };

  const manuali = voci.filter((v) => v.area === area && v.fonte !== "auto");
  const conteggi = oggi.reduce((m, a) => ({ ...m, [a.voce]: (m[a.voce] || 0) + a.quantita }), {});

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4" data-testid="registro-rapido">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Zap className="h-4 w-4 text-amber-500" /> Registro rapido di oggi</p>
        <span className="text-xs text-slate-500">Solo ciò che non passa dal gestionale (SIM, fissi, riparazioni e vendite si contano da soli): un tap = +1</span>
        <div className="ml-auto flex flex-wrap gap-1">
          {AREE.map(([id, l]) => <button key={id} type="button" onClick={() => setArea(id)} className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${area === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-100"}`} data-testid={`rr-area-${id}`}>{l}</button>)}
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <UserRound className="h-3.5 w-3.5 text-slate-400" />
        {cliente ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-1 font-semibold text-sky-800" data-testid="rr-cliente-selezionato">{cliente.cognome} {cliente.nome}<button type="button" onClick={() => setCliente(null)}><X className="h-3 w-3" /></button></span>
        ) : (
          <div className="relative">
            <input value={cliQ} onChange={(e) => setCliQ(e.target.value)} placeholder="Collega a un cliente (facoltativo)…" className="h-8 w-64 rounded-md border border-slate-300 bg-white px-2 text-xs" data-testid="rr-cliente-search" />
            {cliRes.length > 0 && (
              <div className="absolute z-10 mt-1 w-72 rounded-md border border-slate-200 bg-white shadow-lg">
                {cliRes.map((c) => <button key={c.id} type="button" onClick={() => { setCliente(c); setCliQ(""); setCliRes([]); }} className="block w-full px-3 py-1.5 text-left text-xs hover:bg-slate-50" data-testid={`rr-cliente-opt-${c.id}`}>{c.cognome} {c.nome} <span className="text-slate-400">{c.telefono}</span></button>)}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" data-testid="rr-voci">
        {manuali.map((v) => (
          <div key={v.id} className="relative">
            <button type="button" onClick={() => registra(v)} className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-left text-sm font-medium text-slate-800 shadow-sm transition-transform hover:-translate-y-0.5 hover:border-amber-400 active:scale-95" data-testid={`rr-voce-${v.id}`}>
              <span>{v.label}</span>
              <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-bold ${conteggi[v.id] ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-400"}`} data-testid={`rr-count-${v.id}`}>{conteggi[v.id] || 0}</span>
            </button>
          </div>
        ))}
      </div>
      {oggi.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5" data-testid="rr-oggi">
          {oggi.slice(0, 12).map((a) => (
            <span key={a.id} className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[11px] text-slate-600 shadow-sm" data-testid={`rr-oggi-${a.id}`}>
              {voci.find((v) => v.id === a.voce)?.label || a.voce}{a.dettaglio ? ` · ${a.dettaglio}` : ""}{a.client_nome ? ` · ${a.client_nome}` : ""} <span className="text-slate-400">{new Date(a.at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</span>
              <button type="button" onClick={() => elimina(a)} title="Annulla" data-testid={`rr-del-${a.id}`}><Trash2 className="h-3 w-3 text-rose-500" /></button>
            </span>
          ))}
          {oggi.length > 12 && <span className="text-[11px] text-slate-400">+{oggi.length - 12} altri</span>}
        </div>
      )}
    </div>
  );
}
