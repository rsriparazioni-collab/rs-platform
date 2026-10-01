import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Settings2, Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

export const CentriCostoEditor = ({ centri, onSaved }) => {
  const [open, setOpen] = useState(false);
  const [stores, setStores] = useState([]);
  const [list, setList] = useState(centri);
  useEffect(() => { setList(centri); }, [centri]);
  useEffect(() => { if (open) api.get("/contabilita/meta").then((r) => setStores(r.data.stores)).catch(() => {}); }, [open]);
  const toggle = (ci, sid) => setList(list.map((c, i) => {
    if (i === ci) return { ...c, store_ids: c.store_ids.includes(sid) ? c.store_ids.filter((x) => x !== sid) : [...c.store_ids, sid] };
    return { ...c, store_ids: c.store_ids.filter((x) => x !== sid) };
  }));
  const salva = async () => {
    try { await api.put("/contabilita/pdp/centri", list.map(({ id, nome, store_ids }) => ({ id, nome, store_ids }))); toast.success("Centri di costo salvati"); setOpen(false); onSaved(); }
    catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" variant="ghost" title="Centri di costo" data-testid="centri-btn"><Settings2 className="h-4 w-4" /></Button></DialogTrigger>
      <DialogContent className="max-w-lg" data-testid="centri-dialog">
        <DialogHeader><DialogTitle>Centri di costo (Punto di pareggio)</DialogTitle></DialogHeader>
        <p className="text-xs text-slate-500">Un punto di pareggio per ogni centro: raggruppa i negozi che condividono le stesse spese (es. Morbegno + Gravedona). Ogni negozio può stare in un solo centro.</p>
        <div className="space-y-3">
          {list.map((c, ci) => (
            <div key={c.id || ci} className="rounded-lg border border-slate-200 p-3" data-testid={`centro-row-${ci}`}>
              <div className="flex items-center gap-2"><Input value={c.nome} onChange={(e) => setList(list.map((x, i) => (i === ci ? { ...x, nome: e.target.value } : x)))} className="h-8" data-testid={`centro-nome-${ci}`} />
                <button onClick={() => setList(list.filter((_, i) => i !== ci))} className="text-slate-400 hover:text-rose-600" data-testid={`centro-del-${ci}`}><Trash2 className="h-4 w-4" /></button></div>
              <div className="mt-2 flex flex-wrap gap-2">
                {stores.map((s) => <label key={s.id} className={`cursor-pointer rounded-full border px-2.5 py-0.5 text-xs ${c.store_ids.includes(s.id) ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600"}`}><input type="checkbox" className="hidden" checked={c.store_ids.includes(s.id)} onChange={() => toggle(ci, s.id)} data-testid={`centro-${ci}-store-${s.id}`} />{s.nome}</label>)}
              </div>
            </div>
          ))}
          <Button size="sm" variant="outline" onClick={() => setList([...list, { id: "", nome: "Nuovo centro", store_ids: [] }])} data-testid="centro-add">+ Centro di costo</Button>
        </div>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setOpen(false)}>Annulla</Button><Button onClick={salva} data-testid="centri-salva">Salva</Button></div>
      </DialogContent>
    </Dialog>
  );
};
