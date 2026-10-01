import { Label } from "./ui/label";
import { Input } from "./ui/input";

const FORNITORI = ["Miwo", "Phoneclik", "Sifar", "Kolme", "Euroelettronica", "Altro"];

export default function VenditaOrdineBox({ form, set }) {
  const art = form.ordine_articolo || {};
  const setArt = (k, v) => set("ordine_articolo", { ...art, [k]: v });
  return (
    <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50/60 p-3" data-testid="servizio-ordine-box">
      <label className="flex items-center gap-2 text-sm font-medium text-amber-900">
        <input type="checkbox" checked={!!form.da_ordinare} onChange={(e) => { set("da_ordinare", e.target.checked); if (e.target.checked) set("magazzino_item_id", ""); }} data-testid="servizio-da-ordinare" />
        Prodotto da ordinare (non ancora in magazzino)
      </label>
      {form.da_ordinare && (
        <>
          <p className="text-xs text-amber-800">Il telefono viene creato in magazzino e messo "in ordine"; all'arrivo premi "Arrivato" e il cliente riceve il WhatsApp. Alla consegna la vendita si chiude con il saldo.</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1"><Label className="text-xs text-slate-500">Fornitore</Label>
              <Input list="fornitori-ordine" value={form.ordine_fornitore || ""} onChange={(e) => set("ordine_fornitore", e.target.value)} placeholder="Miwo, Phoneclik…" data-testid="servizio-ordine-fornitore" />
              <datalist id="fornitori-ordine">{FORNITORI.map((f) => <option key={f} value={f} />)}</datalist></div>
            <div className="space-y-1"><Label className="text-xs text-slate-500">Marca</Label><Input value={art.marca || ""} onChange={(e) => setArt("marca", e.target.value)} placeholder="Samsung" data-testid="servizio-ordine-marca" /></div>
            <div className="space-y-1"><Label className="text-xs text-slate-500">Modello</Label><Input value={art.modello || ""} onChange={(e) => setArt("modello", e.target.value)} placeholder="Galaxy A55 128GB" data-testid="servizio-ordine-modello" /></div>
            <div className="space-y-1"><Label className="text-xs text-slate-500">Costo acquisto €</Label><Input type="number" step="0.01" value={art.costo ?? ""} onChange={(e) => setArt("costo", e.target.value === "" ? null : parseFloat(e.target.value))} data-testid="servizio-ordine-costo" /></div>
            <div className="space-y-1"><Label className="text-xs text-slate-500">Acconto incassato €</Label><Input type="number" step="0.01" value={form.acconto ?? ""} onChange={(e) => set("acconto", e.target.value)} data-testid="servizio-ordine-acconto" /></div>
            <div className="space-y-1"><Label className="text-xs text-slate-500">Codice / IMEI</Label><Input value={art.codice || ""} onChange={(e) => setArt("codice", e.target.value)} data-testid="servizio-ordine-codice" /></div>
          </div>
          {form.importo && form.acconto ? <p className="text-xs text-slate-600">Saldo alla consegna: <b>€ {(parseFloat(form.importo) - parseFloat(form.acconto)).toFixed(2)}</b></p> : null}
        </>
      )}
    </div>
  );
}
