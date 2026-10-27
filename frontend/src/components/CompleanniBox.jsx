import { useEffect, useState } from "react";
import { Cake, Send } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { ClienteLink } from "./ClienteLink";
import { Button } from "./ui/button";

const fmt = (iso) => iso.split("-").reverse().slice(0, 2).join("/");

export default function CompleanniBox() {
  const { user } = useAuth();
  const [items, setItems] = useState(null);
  const [stato, setStato] = useState(null);
  const load = () => {
    api.get("/ricordi/compleanni", { params: { giorni: 7 } }).then((r) => setItems(r.data)).catch(() => setItems([]));
    if (user.role === "admin") api.get("/ricordi/compleanni/stato").then((r) => setStato(r.data)).catch(() => {});
  };
  useEffect(load, [user.role]);
  if (!items) return null;
  const oggi = items.filter((i) => i.oggi);
  const inviaOra = async () => {
    try { const r = await api.post("/ricordi/compleanni/invia-ora"); toast.success(`Auguri inviati: ${r.data.inviati} (errori ${r.data.errori})`); load(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <section className="rounded-xl border border-pink-200 bg-pink-50/60 p-4" data-testid="compleanni-box">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-slate-800"><Cake className="h-4 w-4 text-pink-600" /> Compleanni oggi e nei prossimi 7 giorni
          <span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-600" data-testid="compleanni-count">{items.length}</span></h2>
        {user.role === "admin" && oggi.some((i) => !i.auguri_inviati) && (
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={inviaOra} data-testid="compleanni-invia-ora"><Send className="mr-1 h-3 w-3" /> Invia auguri di oggi ora</Button>
        )}
      </div>
      {stato && (
        <p className="mt-1 text-xs text-slate-500" data-testid="compleanni-stato">
          Data di nascita nota per {stato.con_data_nascita + stato.da_codice_fiscale} clienti su {stato.clienti} ({stato.da_codice_fiscale} dal codice fiscale); {stato.senza} senza data: compilala nella scheda.
          Auguri automatici alle 9:00 dal numero del negozio{stato.ultimo_invio ? ` · ultimo giro: ${stato.ultimo_invio.inviati} inviati` : ""}.
        </p>
      )}
      {items.length === 0 ? <p className="mt-2 text-sm text-slate-500">Nessun compleanno in vista.</p> : (
        <ul className="mt-2 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((i) => (
            <li key={i.id} className={`flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm ${i.oggi ? "border-2 border-pink-400" : "border border-slate-200"}`} data-testid={`compleanno-${i.id}`}>
              <span className={`font-mono text-xs ${i.oggi ? "font-bold text-pink-600" : "text-slate-500"}`}>{i.oggi ? "OGGI" : fmt(i.data)}</span>
              <span className="min-w-0 flex-1 truncate"><ClienteLink clientId={i.id}>{i.client_name}</ClienteLink> <span className="text-xs text-slate-500">· {i.eta} anni · {i.negozio}</span></span>
              {i.oggi && <span className={`text-[10px] ${i.auguri_inviati ? "text-emerald-600" : "text-amber-600"}`}>{i.auguri_inviati ? "auguri inviati" : i.telefono ? "in attesa" : "senza telefono"}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
