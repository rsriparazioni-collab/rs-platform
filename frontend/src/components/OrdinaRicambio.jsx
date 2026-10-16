import { useEffect, useState } from "react";
import { Barcode, PackagePlus, Store } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { RICAMBIO_TIPOLOGIE } from "../lib/constants";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

function splitDispositivo(d) {
  const parts = (d || "").trim().split(/\s+/);
  return { marca: parts[0] || "", modello: parts.slice(1).join(" ") };
}

const inp = "h-8 rounded-md border border-slate-300 bg-white px-2 text-xs";

export default function OrdinaRicambio({ servizio, onDone, preset }) {
  const init = splitDispositivo(servizio.dispositivo);
  const [form, setForm] = useState({ marca: preset?.marca || init.marca, modello: preset?.modello || init.modello, tipologia: preset?.tipologia || servizio.tipo_ricambio || "altro", quantita: 1, magazzino_id: preset?.item_id || "", barcode: "", fornitore: "", prezzo_acquisto: "", prezzo_vendita: "", soglia_minima: "" });
  const [busy, setBusy] = useState(false);
  const [trovato, setTrovato] = useState(null);
  const [suggerimento, setSuggerimento] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  useEffect(() => {
    const code = form.barcode.trim();
    if (code.length < 4) { setTrovato(null); return; }
    const t = setTimeout(() => api.get("/magazzino/disponibilita", { params: { q: code } }).then((r) => {
      const g = r.data.find((x) => x.stores.some((s) => (s.barcode || "") === code)) || r.data[0] || null;
      setTrovato(g);
      if (g) {
        const own = g.stores.find((s) => s.store_id === servizio.venditore_id);
        setForm((f) => ({ ...f, marca: g.marca || f.marca, modello: g.modello || f.modello, tipologia: g.tipologia || f.tipologia, magazzino_id: own?.item_id || "" }));
      }
    }).catch(() => setTrovato(null)), 350);
    return () => clearTimeout(t);
  }, [form.barcode, servizio.venditore_id]);

  const payload = () => ({ ...form, quantita: parseInt(form.quantita) || 1, prezzo_acquisto: form.prezzo_acquisto === "" ? null : parseFloat(form.prezzo_acquisto), prezzo_vendita: form.prezzo_vendita === "" ? null : parseFloat(form.prezzo_vendita), soglia_minima: form.soglia_minima === "" ? null : parseInt(form.soglia_minima) });

  const ordina = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/servizi/${servizio.id}/ricambi/ordina`, payload());
      toast.success(`${r.data.nome} messo in ordine (giacenza ${r.data.giacenza}). Riparazione in attesa ricambio.`);
      onDone?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const prendiDa = async (s) => {
    setBusy(true);
    try {
      await api.post(`/servizi/${servizio.id}/ricambi`, { magazzino_id: s.item_id, quantita: parseInt(form.quantita) || 1 });
      toast.success(`Ricambio preso da ${s.store_name}: avviso inviato al negozio`);
      onDone?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const submit = async () => {
    setBusy(true);
    try {
      const q = form.barcode.trim() || `${form.marca} ${form.modello}`.trim();
      const r = q.length >= 2 ? await api.get("/magazzino/disponibilita", { params: { q, ...(form.barcode.trim() ? {} : { tipologia: form.tipologia }) } }) : { data: [] };
      const altri = r.data.flatMap((g) => g.stores).filter((s) => s.store_id !== servizio.venditore_id && s.quantita > 0);
      if (altri.length) { setSuggerimento(altri); setBusy(false); return; }
    } catch { /* se la ricerca fallisce si ordina comunque */ }
    await ordina();
  };

  return (
    <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50/70 p-3" data-testid="ordina-ricambio-box">
      <p className="text-xs font-semibold uppercase tracking-wide text-rose-800">Ricambio non disponibile: mettilo in ordine</p>
      <p className="mb-2 text-[11px] text-rose-700">Compila l'articolo completo (codice a barre, fornitore, prezzi): viene creato nel magazzino del negozio e va a giacenza negativa finché non arriva.</p>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <div className="relative"><Barcode className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-slate-400" /><input placeholder="Scansiona / codice a barre" value={form.barcode} onChange={set("barcode")} className={`${inp} w-56 pl-7`} data-testid="ordina-barcode" /></div>
        {trovato && <span className="text-[11px] text-emerald-700" data-testid="ordina-barcode-trovato">Trovato: <b>{trovato.nome}</b> · {trovato.stores.map((s) => `${s.store_name} ${s.quantita}`).join(", ")}</span>}
        {form.barcode.trim().length >= 4 && !trovato && <span className="text-[11px] text-slate-500" data-testid="ordina-barcode-nuovo">Codice nuovo: verrà associato all'articolo</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={form.tipologia} onValueChange={(v) => setForm({ ...form, tipologia: v })}>
          <SelectTrigger className="h-8 w-[170px] bg-white text-xs" data-testid="ordina-tipologia"><SelectValue /></SelectTrigger>
          <SelectContent>{RICAMBIO_TIPOLOGIE.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
        </Select>
        <input placeholder="Marca" value={form.marca} onChange={set("marca")} className={`${inp} w-28`} data-testid="ordina-marca" />
        <input placeholder="Modello" value={form.modello} onChange={set("modello")} className={`${inp} w-40`} data-testid="ordina-modello" />
        <input type="number" min="1" value={form.quantita} onChange={set("quantita")} className={`${inp} w-14`} title="Quantità" data-testid="ordina-quantita" />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input placeholder="Fornitore" value={form.fornitore} onChange={set("fornitore")} className={`${inp} w-36`} data-testid="ordina-fornitore" />
        <input type="number" step="0.01" min="0" placeholder="€ acquisto" value={form.prezzo_acquisto} onChange={set("prezzo_acquisto")} className={`${inp} w-24`} data-testid="ordina-prezzo-acquisto" />
        <input type="number" step="0.01" min="0" placeholder="€ vendita" value={form.prezzo_vendita} onChange={set("prezzo_vendita")} className={`${inp} w-24`} data-testid="ordina-prezzo-vendita" />
        <input type="number" min="0" placeholder="Soglia min." value={form.soglia_minima} onChange={set("soglia_minima")} className={`${inp} w-24`} data-testid="ordina-soglia" />
        {!suggerimento && (
          <Button type="button" size="sm" disabled={busy || (!form.magazzino_id && !form.modello.trim())} onClick={submit} className="h-8 gap-1 bg-rose-700 text-xs hover:bg-rose-800" data-testid="ordina-submit">
            <PackagePlus className="h-3.5 w-3.5" /> Usa e metti in ordine
          </Button>
        )}
      </div>
      {suggerimento && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-2.5" data-testid="ordina-suggerimento">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-900"><Store className="h-3.5 w-3.5" /> Un altro negozio ce l'ha già: conviene prenderlo da lì invece di ordinarlo</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {suggerimento.map((s) => (
              <Button key={s.item_id} type="button" size="sm" disabled={busy} onClick={() => prendiDa(s)} className="h-7 bg-amber-600 text-xs hover:bg-amber-700" data-testid={`ordina-prendi-da-${s.store_id}`}>Sì, prendi da {s.store_name} ({s.quantita} pz)</Button>
            ))}
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={ordina} className="h-7 border-rose-300 text-xs text-rose-700" data-testid="ordina-rifiuta-suggerimento">No, ordina comunque dal fornitore</Button>
          </div>
        </div>
      )}
    </div>
  );
}
