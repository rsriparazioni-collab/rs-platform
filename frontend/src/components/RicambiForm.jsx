import { useState } from "react";
import { Barcode, PackagePlus, Plus, Trash2 } from "lucide-react";
import { RICAMBIO_TIPOLOGIE } from "../lib/constants";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const inp = "h-8 rounded-md border border-slate-300 bg-white px-2 text-xs";
const vuoto = () => ({ tipologia: "altro", marca: "", modello: "", barcode: "", fornitore: "", prezzo_acquisto: "", prezzo_vendita: "", quantita: 1 });

/* Riga "articolo non in magazzino": al salvataggio della riparazione viene creato in magazzino a giacenza negativa (in ordine). */
export const RicambioNuovoRow = ({ onAdd }) => {
  const [open, setOpen] = useState(false);
  const [r, setR] = useState(vuoto());
  const set = (k) => (e) => setR((x) => ({ ...x, [k]: e.target.value }));
  const ok = r.modello.trim() || r.barcode.trim();
  if (!open) return <button type="button" onClick={() => setOpen(true)} className="flex items-center gap-1 text-xs font-medium text-rose-700 hover:underline" data-testid="servizio-ricambio-nuovo-apri"><PackagePlus className="h-3.5 w-3.5" /> Ricambio non in magazzino: crealo e mettilo in ordine</button>;
  return (
    <div className="space-y-2 rounded-lg border border-rose-200 bg-rose-50/60 p-2.5" data-testid="servizio-ricambio-nuovo-box">
      <p className="text-[11px] text-rose-700">Verrà creato nel magazzino del negozio a giacenza −{r.quantita || 1} (in ordine); all'arrivo torna a 0.</p>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative"><Barcode className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-slate-400" /><input placeholder="Codice a barre" value={r.barcode} onChange={set("barcode")} className={`${inp} w-44 pl-7`} data-testid="servizio-ricambio-nuovo-barcode" /></div>
        <Select value={r.tipologia} onValueChange={(v) => setR({ ...r, tipologia: v })}>
          <SelectTrigger className="h-8 w-[160px] bg-white text-xs" data-testid="servizio-ricambio-nuovo-tipologia"><SelectValue /></SelectTrigger>
          <SelectContent>{RICAMBIO_TIPOLOGIE.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
        </Select>
        <input placeholder="Marca" value={r.marca} onChange={set("marca")} className={`${inp} w-28`} data-testid="servizio-ricambio-nuovo-marca" />
        <input placeholder="Descrizione / modello" value={r.modello} onChange={set("modello")} className={`${inp} w-48`} data-testid="servizio-ricambio-nuovo-modello" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input placeholder="Fornitore" value={r.fornitore} onChange={set("fornitore")} className={`${inp} w-32`} data-testid="servizio-ricambio-nuovo-fornitore" />
        <input type="number" step="0.01" min="0" placeholder="€ acquisto" value={r.prezzo_acquisto} onChange={set("prezzo_acquisto")} className={`${inp} w-24`} data-testid="servizio-ricambio-nuovo-acquisto" />
        <input type="number" step="0.01" min="0" placeholder="€ vendita" value={r.prezzo_vendita} onChange={set("prezzo_vendita")} className={`${inp} w-24`} data-testid="servizio-ricambio-nuovo-vendita" />
        <input type="number" min="1" value={r.quantita} onChange={set("quantita")} className={`${inp} w-14`} title="Quantità" data-testid="servizio-ricambio-nuovo-qta" />
        <Button type="button" size="sm" disabled={!ok} onClick={() => { onAdd({ ...r, quantita: Math.max(parseInt(r.quantita) || 1, 1) }); setR(vuoto()); setOpen(false); }} className="h-8 gap-1 bg-rose-700 text-xs hover:bg-rose-800" data-testid="servizio-ricambio-nuovo-aggiungi"><Plus className="h-3.5 w-3.5" /> Aggiungi</Button>
        <button type="button" className="text-xs text-slate-500 hover:underline" onClick={() => setOpen(false)}>annulla</button>
      </div>
    </div>
  );
};

export const RicambiScelti = ({ righe, onChange }) => (
  <ul className="space-y-1" data-testid="servizio-ricambi-lista">
    {righe.map((r, i) => (
      <li key={i} className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm ${r.nuovo ? "border-rose-300 bg-rose-50" : r.disponibile ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`} data-testid={`servizio-ricambio-riga-${i}`}>
        <span className="flex-1">
          {r.nuovo ? <>{[r.marca, r.modello].filter(Boolean).join(" ")}{r.barcode && <span className="ml-1 rounded bg-white px-1 font-mono text-[10px] text-slate-500">{r.barcode}</span>} <span className="text-xs text-rose-700">· nuovo articolo, va in ordine</span>{r.prezzo_acquisto !== "" && <span className="text-xs text-slate-500"> · {r.prezzo_acquisto} €</span>}</> : <>{r.nome} · {r.store_name}{!r.disponibile && <span className="text-xs text-amber-800"> · esaurito: verrà messo in ordine</span>}</>}
        </span>
        <input type="number" min="1" value={r.quantita} onChange={(e) => onChange(righe.map((x, j) => (j === i ? { ...x, quantita: Math.max(parseInt(e.target.value) || 1, 1) } : x)))} className="w-14 rounded border border-slate-300 px-1.5 py-0.5 text-xs" data-testid={`servizio-ricambio-qta-${i}`} />
        <button type="button" className="text-rose-700" onClick={() => onChange(righe.filter((_, j) => j !== i))} title="Rimuovi" data-testid={`servizio-ricambio-rimuovi-${i}`}><Trash2 className="h-3.5 w-3.5" /></button>
      </li>
    ))}
  </ul>
);

/* Collega tutti i ricambi alla riparazione appena creata; ritorna il numero di errori. */
export async function collegaRicambi(api, servizioId, righe, venditoreId) {
  let errori = 0;
  for (const r of righe) {
    try {
      if (r.nuovo) {
        await api.post(`/servizi/${servizioId}/ricambi/ordina`, { tipologia: r.tipologia, marca: r.marca, modello: r.modello, barcode: r.barcode, fornitore: r.fornitore, quantita: r.quantita,
          prezzo_acquisto: r.prezzo_acquisto === "" ? null : parseFloat(r.prezzo_acquisto), prezzo_vendita: r.prezzo_vendita === "" ? null : parseFloat(r.prezzo_vendita) });
      } else if (r.disponibile) {
        await api.post(`/servizi/${servizioId}/ricambi`, { magazzino_id: r.item_id, quantita: r.quantita });
      } else {
        await api.post(`/servizi/${servizioId}/ricambi/ordina`, { magazzino_id: r.item_id, quantita: r.quantita, tipologia: r.tipologia, da_store_id: r.store_id !== venditoreId ? r.store_id : "" });
      }
    } catch { errori += 1; }
  }
  return errori;
}
