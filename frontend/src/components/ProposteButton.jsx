import { useState } from "react";
import { Lightbulb } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

const PROPOSTE = [["eolo_proposto", "Eolo proposto"], ["telefono_proposto", "Telefono proposto"], ["chiamata_eolo", "Chiamata Eolo fatta"], ["chiamata_enel_eco", "Chiamata ENEL eco fatta"], ["passato_a_deborah", "Passato a Deborah (utenze)"], ["passato_a_silvio", "Passato a Silvio (telefonia)"]];

export default function ProposteButton({ clientId }) {
  const [open, setOpen] = useState(false);
  const segna = async (voce, label) => {
    try { await api.post("/attivita", { voce, client_id: clientId }); toast.success(`${label} registrato nei KPI`); setOpen(false); }
    catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="relative inline-block">
      <Button size="sm" variant="outline" className="gap-1 border-amber-300 text-amber-800" onClick={() => setOpen(!open)} data-testid="proposta-button"><Lightbulb className="h-3.5 w-3.5" /> Proposta fatta</Button>
      {open && (
        <div className="absolute z-20 mt-1 w-56 rounded-md border border-slate-200 bg-white p-1 shadow-lg" data-testid="proposta-menu">
          {PROPOSTE.map(([id, l]) => <button key={id} type="button" onClick={() => segna(id, l)} className="block w-full rounded px-2.5 py-1.5 text-left text-xs hover:bg-amber-50" data-testid={`proposta-${id}`}>{l}</button>)}
        </div>
      )}
    </div>
  );
}
