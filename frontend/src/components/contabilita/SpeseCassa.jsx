import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Num, eur } from "./shared";

export const SpeseCassa = ({ storeId, anno, mese, spese, reload }) => {
  const [f, setF] = useState({ data: new Date().toISOString().slice(0, 10), motivo: "", importo: "", riferimento: "" });
  const add = async () => {
    if (!f.motivo || !f.importo) return toast.error("Motivo e importo obbligatori");
    try { await api.post("/contabilita/spese", { ...f, store_id: storeId, importo: parseFloat(f.importo) }); setF({ ...f, motivo: "", importo: "", riferimento: "" }); toast.success("Spesa registrata"); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const del = async (id) => { try { await api.delete(`/contabilita/spese/${id}`); reload(); } catch (e) { toast.error(apiError(e)); } };
  const tot = spese.reduce((a, s) => a + s.importo, 0);
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="spese-cassa">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3"><h3 className="font-semibold text-slate-900">Spese per contanti / cassa <span className="text-xs font-normal text-slate-500">[prima nota]</span></h3><span className="text-sm font-semibold text-rose-700" data-testid="spese-totale">{eur(tot)}</span></div>
      <div className="grid gap-2 border-b border-slate-100 p-4 sm:grid-cols-[150px_1fr_120px_140px_auto]">
        <Input type="date" value={f.data} min={`${anno}-${String(mese).padStart(2, "0")}-01`} onChange={(e) => setF({ ...f, data: e.target.value })} className="h-8" data-testid="spesa-data" />
        <Input placeholder="Motivo (es. MIWO, ritiro zflip 4)" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} className="h-8" data-testid="spesa-motivo" />
        <Num value={f.importo} onChange={(v) => setF({ ...f, importo: v })} testid="spesa-importo" />
        <Input placeholder="N° fattura / ritiro" value={f.riferimento} onChange={(e) => setF({ ...f, riferimento: e.target.value })} className="h-8" data-testid="spesa-riferimento" />
        <Button size="sm" onClick={add} data-testid="spesa-add">Aggiungi</Button>
      </div>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-slate-100">
          {spese.map((s) => (
            <tr key={s.id} data-testid={`spesa-row-${s.id}`}>
              <td className="px-5 py-1.5 text-slate-500">{s.data.split("-").reverse().join("/")}</td><td className="px-3 py-1.5">{s.motivo}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{eur(s.importo)}</td><td className="px-3 py-1.5 text-slate-500">{s.riferimento}</td>
              <td className="px-3 py-1.5 text-right"><button onClick={() => del(s.id)} className="text-slate-400 hover:text-rose-600" data-testid={`spesa-del-${s.id}`}><Trash2 className="h-4 w-4" /></button></td>
            </tr>
          ))}
          {!spese.length && <tr><td className="px-5 py-3 text-sm text-slate-400">Nessuna spesa nel mese</td></tr>}
        </tbody>
      </table>
    </div>
  );
};
