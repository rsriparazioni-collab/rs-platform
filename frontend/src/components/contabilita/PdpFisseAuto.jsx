import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Landmark, Plus, Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { eur } from "./shared";

export const PdpFisseAuto = ({ centri, onSaved }) => {
  const [items, setItems] = useState(null);
  const [aperto, setAperto] = useState(false);
  const load = useCallback(() => api.get("/contabilita/pdp-fisse-auto").then((r) => setItems(r.data)).catch(() => setItems([])), []);
  useEffect(() => { load(); }, [load]);
  if (!items) return null;
  const set = (i, k, v) => setItems(items.map((it, j) => (j === i ? { ...it, [k]: v } : it)));
  const salva = async () => {
    try {
      const r = await api.put("/contabilita/pdp-fisse-auto", items.map((i) => ({ centro_id: i.centro_id, voce: i.voce, importo: Number(i.importo) || 0, note: i.note || "" })));
      setItems(r.data.items); toast.success(`Spese fisse salvate${r.data.fisse_pdp_inserite ? ` · ${r.data.fisse_pdp_inserite} voci compilate nel mese corrente` : ""}`); onSaved?.();
    } catch (e) { toast.error(apiError(e)); }
  };
  const tot = items.reduce((a, i) => a + (Number(i.importo) || 0), 0);
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="pdp-fisse-auto">
      <button type="button" onClick={() => setAperto((a) => !a)} className="flex w-full items-center justify-between px-4 py-3 text-left" data-testid="pdp-fisse-auto-toggle">
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Landmark className="h-4 w-4 text-sky-600" /> Spese fisse pagate dal conto corrente <span className="text-xs font-normal text-slate-500">(affitti, utenze, condominio, commercialista: compilate da sole ogni mese)</span></span>
        <span className="text-xs text-slate-500">{items.length} voci · {eur(tot)}/mese {aperto ? "▲" : "▼"}</span>
      </button>
      {aperto && (
        <div className="space-y-2 border-t border-slate-100 p-4">
          {items.map((it, i) => (
            <div key={it.id || i} className="grid gap-2 sm:grid-cols-[1fr_1fr_120px_1fr_auto]" data-testid={`pdp-fissa-${i}`}>
              <select value={it.centro_id} onChange={(e) => set(i, "centro_id", e.target.value)} className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid={`pdp-fissa-centro-${i}`}>{centri.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select>
              <Input value={it.voce} onChange={(e) => set(i, "voce", e.target.value)} placeholder="Voce (es. Utenze)" className="h-8" data-testid={`pdp-fissa-voce-${i}`} />
              <Input type="number" step="0.01" value={it.importo} onChange={(e) => set(i, "importo", e.target.value)} placeholder="€/mese" className="h-8 text-right" data-testid={`pdp-fissa-importo-${i}`} />
              <Input value={it.note || ""} onChange={(e) => set(i, "note", e.target.value)} placeholder="Nota (es. Morbegno 700 + Gravedona 600)" className="h-8" data-testid={`pdp-fissa-note-${i}`} />
              <button type="button" onClick={() => setItems(items.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-600" data-testid={`pdp-fissa-del-${i}`}><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
          <div className="flex items-center justify-between pt-1">
            <Button type="button" size="sm" variant="outline" onClick={() => setItems([...items, { centro_id: centri[0]?.id || "", voce: "", importo: "", note: "" }])} data-testid="pdp-fissa-add"><Plus className="mr-1 h-3.5 w-3.5" /> Aggiungi voce</Button>
            <Button type="button" size="sm" onClick={salva} data-testid="pdp-fisse-salva">Salva spese fisse</Button>
          </div>
          <p className="text-xs text-slate-500">Le voci si scrivono nel Punto di pareggio il 1° di ogni mese (e subito al salvataggio) solo se la casella è vuota: i valori che inserisci a mano non vengono toccati. Il pagamento reale si segue nello Scadenzario.</p>
        </div>
      )}
    </div>
  );
};
