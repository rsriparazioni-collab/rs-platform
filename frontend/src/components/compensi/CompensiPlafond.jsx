import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { fmtDate } from "../../lib/constants";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { eur } from "./CompensiCalcolo";

export const CompensiPlafond = ({ meta }) => {
  const [data, setData] = useState(null);
  const [f, setF] = useState({ store_id: "", importo: "", causale: "" });
  const load = useCallback(() => api.get("/compensi/plafond").then((r) => setData(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const carica = async (e) => {
    e.preventDefault();
    try { await api.post("/compensi/plafond", { ...f, importo: parseFloat(f.importo) }); toast.success("Movimento registrato"); setF({ store_id: "", importo: "", causale: "" }); load(); }
    catch (err) { toast.error(apiError(err)); }
  };
  const elimina = async (m) => { try { await api.delete(`/compensi/plafond/${m.id}`); load(); } catch (err) { toast.error(apiError(err)); } };

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">Le prime ricariche delle SIM (inserite nel servizio SIM) vengono scalate dal plafond del negozio; se il negozio non ha un plafond proprio, dal plafond globale. Carica qui i plafond (es. generati dalle SIM Lyca) con importo positivo, o correggi con importo negativo.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {data?.saldi.map((s) => (
          <div key={s.store_id} className="rounded-xl border border-slate-200 bg-white p-4" data-testid={`plafond-saldo-${s.store_id || "globale"}`}>
            <p className="text-xs uppercase tracking-wide text-slate-500">{s.store_name}</p>
            <p className={`font-heading text-2xl font-bold ${s.saldo < 0 ? "text-rose-600" : "text-slate-900"}`}>{eur(s.saldo)}</p>
            <p className="text-xs text-slate-500">Caricato {eur(s.carichi)} · Ricariche {eur(s.ricariche)}</p>
          </div>
        ))}
      </div>
      <form onSubmit={carica} className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="space-y-1.5"><label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Plafond</label>
          <Select value={f.store_id || "globale"} onValueChange={(v) => setF({ ...f, store_id: v === "globale" ? "" : v })}><SelectTrigger className="w-44" data-testid="plafond-store"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="globale">Plafond globale</SelectItem>{meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1.5"><label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Importo € (+/−)</label><Input type="number" step="0.01" className="w-32" value={f.importo} onChange={(e) => setF({ ...f, importo: e.target.value })} required data-testid="plafond-importo" /></div>
        <div className="flex-1 space-y-1.5"><label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Causale</label><Input value={f.causale} onChange={(e) => setF({ ...f, causale: e.target.value })} placeholder="es. Plafond Lyca settembre" data-testid="plafond-causale" /></div>
        <Button type="submit" data-testid="plafond-salva">Registra</Button>
      </form>
      {data?.movimenti.length > 0 && (
        <table className="w-full rounded-xl border border-slate-200 bg-white text-sm" data-testid="plafond-movimenti">
          <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-2">Data</th><th className="px-3 py-2">Plafond</th><th className="px-3 py-2">Importo</th><th className="px-3 py-2">Causale</th><th></th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {data.movimenti.map((m) => (
              <tr key={m.id}><td className="px-4 py-2 text-slate-600">{fmtDate(m.at)}</td><td className="px-3 py-2">{m.store_name}</td><td className={`px-3 py-2 font-semibold ${m.importo < 0 ? "text-rose-600" : "text-emerald-700"}`}>{eur(m.importo)}</td><td className="px-3 py-2 text-slate-600">{m.causale}</td>
                <td className="px-3 py-2"><Button variant="ghost" size="icon" onClick={() => elimina(m)} data-testid={`plafond-del-${m.id}`}><Trash2 className="h-4 w-4 text-rose-600" /></Button></td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
