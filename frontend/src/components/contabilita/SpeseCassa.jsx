import { useState } from "react";
import { toast } from "sonner";
import { Trash2, Pencil, Check, X } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Num, eur } from "./shared";

const dmy = (d) => d.split("-").reverse().join("/");

export const SpeseCassa = ({ storeId, anno, mese, spese, reload }) => {
  const [f, setF] = useState({ data: new Date().toISOString().slice(0, 10), motivo: "", importo: "", riferimento: "" });
  const [edit, setEdit] = useState(null);
  const add = async () => {
    if (!f.motivo || !f.importo) return toast.error("Scrivi il motivo e l'importo della spesa");
    try { await api.post("/contabilita/spese", { ...f, store_id: storeId, importo: parseFloat(f.importo) }); setF({ ...f, motivo: "", importo: "", riferimento: "" }); toast.success("Spesa registrata"); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const del = async (s) => {
    if (!window.confirm(`Eliminare la spesa "${s.motivo}" di ${eur(s.importo)} del ${dmy(s.data)}?`)) return;
    try { await api.delete(`/contabilita/spese/${s.id}`); toast.success("Spesa eliminata"); reload(); } catch (e) { toast.error(apiError(e)); }
  };
  const salva = async () => {
    if (!edit.motivo || edit.importo === "") return toast.error("Scrivi il motivo e l'importo della spesa");
    try { await api.put(`/contabilita/spese/${edit.id}`, { data: edit.data, motivo: edit.motivo, importo: parseFloat(edit.importo), riferimento: edit.riferimento || "" }); toast.success("Spesa modificata"); setEdit(null); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
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
          {spese.map((s) => edit?.id === s.id ? (
            <tr key={s.id} className="bg-amber-50/60" data-testid={`spesa-edit-row-${s.id}`}>
              <td className="px-3 py-1.5"><Input type="date" value={edit.data} onChange={(e) => setEdit({ ...edit, data: e.target.value })} className="h-8" data-testid="spesa-edit-data" /></td>
              <td className="px-3 py-1.5"><Input value={edit.motivo} onChange={(e) => setEdit({ ...edit, motivo: e.target.value })} className="h-8" data-testid="spesa-edit-motivo" /></td>
              <td className="px-3 py-1.5"><Num value={edit.importo} onChange={(v) => setEdit({ ...edit, importo: v })} testid="spesa-edit-importo" /></td>
              <td className="px-3 py-1.5"><Input value={edit.riferimento || ""} onChange={(e) => setEdit({ ...edit, riferimento: e.target.value })} className="h-8" placeholder="N° fattura / ritiro" data-testid="spesa-edit-riferimento" /></td>
              <td className="whitespace-nowrap px-3 py-1.5 text-right">
                <button onClick={salva} className="mr-2 text-emerald-600 hover:text-emerald-800" title="Salva" data-testid="spesa-edit-save"><Check className="h-4 w-4" /></button>
                <button onClick={() => setEdit(null)} className="text-slate-400 hover:text-slate-700" title="Annulla" data-testid="spesa-edit-cancel"><X className="h-4 w-4" /></button>
              </td>
            </tr>
          ) : (
            <tr key={s.id} data-testid={`spesa-row-${s.id}`}>
              <td className="px-5 py-1.5 text-slate-500">{dmy(s.data)}</td>
              <td className="px-3 py-1.5">{s.motivo}{s.updated_by && <span className="ml-2 text-[10px] text-amber-700" title={`Modificata il ${s.updated_at?.slice(0, 10).split("-").reverse().join("/")}`} data-testid={`spesa-modificata-${s.id}`}>modificata da {s.updated_by}</span>}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{eur(s.importo)}</td><td className="px-3 py-1.5 text-slate-500">{s.riferimento}</td>
              <td className="whitespace-nowrap px-3 py-1.5 text-right">
                <button onClick={() => setEdit({ ...s, importo: String(s.importo) })} className="mr-2 text-slate-400 hover:text-sky-700" title="Modifica" data-testid={`spesa-edit-${s.id}`}><Pencil className="h-4 w-4" /></button>
                <button onClick={() => del(s)} className="text-slate-400 hover:text-rose-600" title="Elimina" data-testid={`spesa-del-${s.id}`}><Trash2 className="h-4 w-4" /></button>
              </td>
            </tr>
          ))}
          {!spese.length && <tr><td className="px-5 py-3 text-sm text-slate-400">Nessuna spesa nel mese</td></tr>}
        </tbody>
      </table>
    </div>
  );
};
