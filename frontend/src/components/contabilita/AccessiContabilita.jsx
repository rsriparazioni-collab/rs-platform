import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";

export const AccessiContabilita = () => {
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get("/contabilita/utenti").then((r) => setD(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const salva = async (u, ids) => {
    try { await api.patch(`/contabilita/utenti/${u.id}`, { contabilita_store_ids: ids }); toast.success(`Accesso contabilità di ${u.name} aggiornato`); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  if (!d) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white lg:col-span-2" data-testid="accessi-contabilita">
      <div className="border-b border-slate-100 px-5 py-3"><h3 className="font-semibold text-slate-900">Chi vede i corrispettivi</h3>
        <p className="text-xs text-slate-500">Vale solo per questa sezione: anche chi "vede tutto" nel resto del gestionale qui vede soltanto i negozi spuntati. Senza spunte l'utente non vede alcun corrispettivo.</p></div>
      <ul className="divide-y divide-slate-100">
        {d.utenti.map((u) => (
          <li key={u.id} className="flex flex-wrap items-center gap-3 px-5 py-2.5" data-testid={`accesso-utente-${u.id}`}>
            <div className="w-44"><p className="text-sm font-medium text-slate-800">{u.name}</p><p className="text-xs text-slate-500">{u.role}{u.override && <span className="ml-1 rounded bg-sky-100 px-1 text-[10px] font-semibold text-sky-700">personalizzato</span>}</p></div>
            <div className="flex flex-1 flex-wrap gap-1.5">
              {d.stores.map((s) => { const on = u.store_ids_effettivi.includes(s.id); return (
                <button key={s.id} onClick={() => salva(u, on ? u.store_ids_effettivi.filter((x) => x !== s.id) : [...u.store_ids_effettivi, s.id])} className={`rounded-full border px-2.5 py-0.5 text-xs transition-colors ${on ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600 hover:border-slate-400"}`} data-testid={`accesso-${u.id}-${s.id}`}>{s.nome}</button>); })}
            </div>
            {u.override && <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => salva(u, null)} data-testid={`accesso-reset-${u.id}`}>Ripristina</Button>}
          </li>
        ))}
      </ul>
    </div>
  );
};
