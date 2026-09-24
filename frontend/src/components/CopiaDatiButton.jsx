import { Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";

export function datiClienteTesto(c) {
  const indirizzo = [[c.indirizzo, c.civico].filter(Boolean).join(" "), [c.cap, c.comune].filter(Boolean).join(" "), c.provincia].filter(Boolean).join(", ");
  const righe = [
    ["Nome", c.nome], ["Cognome", c.cognome], ["Codice fiscale", c.codice_fiscale], ["P.IVA", c.p_iva],
    ["Telefono", c.telefono], ["Email", c.email], ["Indirizzo", indirizzo], ["POD", c.pod], ["PDR", c.pdr], ["IBAN", c.iban],
  ].filter(([, v]) => v);
  return righe.map(([k, v]) => `${k}: ${v}`).join("\n");
}

export default function CopiaDatiButton({ cliente, size = "sm", className = "" }) {
  if (!cliente) return null;
  const copia = () => navigator.clipboard.writeText(datiClienteTesto(cliente))
    .then(() => toast.success("Dati cliente copiati: incollali nel portale"))
    .catch(() => toast.error("Copia non riuscita"));
  return (
    <Button size={size} variant="outline" className={`gap-1 ${className}`} onClick={copia} title="Copia nome, CF, telefono, indirizzo…" data-testid="copia-dati-cliente-button">
      <Copy className="h-3.5 w-3.5" /> Copia dati cliente
    </Button>
  );
}
