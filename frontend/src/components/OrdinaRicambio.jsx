import { useState } from "react";
import { PackagePlus } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { RICAMBIO_TIPOLOGIE } from "../lib/constants";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

function splitDispositivo(d) {
  const parts = (d || "").trim().split(/\s+/);
  return { marca: parts[0] || "", modello: parts.slice(1).join(" ") };
}

export default function OrdinaRicambio({ servizio, onDone, preset }) {
  const init = splitDispositivo(servizio.dispositivo);
  const [form, setForm] = useState({ marca: preset?.marca || init.marca, modello: preset?.modello || init.modello, tipologia: preset?.tipologia || servizio.tipo_ricambio || "altro", quantita: 1, magazzino_id: preset?.item_id || "" });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/servizi/${servizio.id}/ricambi/ordina`, { ...form, quantita: parseInt(form.quantita) || 1 });
      toast.success(`${r.data.nome} messo in ordine (giacenza ${r.data.giacenza}). Riparazione in attesa ricambio.`);
      onDone?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50/70 p-3" data-testid="ordina-ricambio-box">
      <p className="text-xs font-semibold uppercase tracking-wide text-rose-800">Ricambio non disponibile: mettilo in ordine</p>
      <p className="mb-2 text-[11px] text-rose-700">L'articolo viene creato (se manca) nel magazzino del negozio e va a giacenza negativa finché non arriva.</p>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={form.tipologia} onValueChange={(v) => setForm({ ...form, tipologia: v })}>
          <SelectTrigger className="h-8 w-[170px] bg-white text-xs" data-testid="ordina-tipologia"><SelectValue /></SelectTrigger>
          <SelectContent>{RICAMBIO_TIPOLOGIE.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
        </Select>
        <input placeholder="Marca" value={form.marca} onChange={(e) => setForm({ ...form, marca: e.target.value })} className="h-8 w-28 rounded-md border border-slate-300 px-2 text-xs" data-testid="ordina-marca" />
        <input placeholder="Modello" value={form.modello} onChange={(e) => setForm({ ...form, modello: e.target.value })} className="h-8 w-40 rounded-md border border-slate-300 px-2 text-xs" data-testid="ordina-modello" />
        <input type="number" min="1" value={form.quantita} onChange={(e) => setForm({ ...form, quantita: e.target.value })} className="h-8 w-14 rounded-md border border-slate-300 px-2 text-xs" data-testid="ordina-quantita" />
        <Button type="button" size="sm" disabled={busy || (!form.magazzino_id && !form.modello.trim())} onClick={submit} className="h-8 gap-1 bg-rose-700 text-xs hover:bg-rose-800" data-testid="ordina-submit">
          <PackagePlus className="h-3.5 w-3.5" /> Usa e metti in ordine
        </Button>
      </div>
    </div>
  );
}
