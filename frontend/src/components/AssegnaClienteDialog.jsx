import { useEffect, useState } from "react";
import { UserPlus } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

const splitNome = (s) => {
  const parts = (s || "").trim().split(/\s+/);
  return parts.length > 1 ? { cognome: parts[0], nome: parts.slice(1).join(" ") } : { cognome: parts[0] || "", nome: "" };
};

export default function AssegnaClienteDialog({ vendita, open, onOpenChange, onAssigned }) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [nuovo, setNuovo] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSearch(vendita.cliente_nome || ""); setNuovo(null);
  }, [open, vendita]);

  useEffect(() => {
    if (search.trim().length < 2) { setResults([]); return undefined; }
    const t = setTimeout(() => api.get("/clients", { params: { q: search.trim() } }).then((r) => setResults(r.data.slice(0, 8))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [search]);

  const assegna = async (clientId) => {
    setSaving(true);
    try {
      const r = await api.post(`/vendite/${vendita.id}/cliente`, { client_id: clientId });
      toast.success("Cliente collegato alla vendita");
      onAssigned(r.data);
      onOpenChange(false);
    } catch (e) { toast.error(apiError(e, "Collegamento fallito")); }
    finally { setSaving(false); }
  };

  const creaEAssegna = async () => {
    if (!(nuovo.telefono || "").replace(/\D/g, "").length) { toast.error("Inserisci il telefono del cliente"); return; }
    setSaving(true);
    try {
      const c = await api.post("/clients", { nome: nuovo.nome, cognome: nuovo.cognome, telefono: nuovo.telefono, codice_fiscale: nuovo.codice_fiscale || "",
        venditore_id: vendita.store_id, tipo_bolletta: "luce", origine: "riparazione", lavorazione: "" });
      await assegna(c.data.id);
    } catch (e) { toast.error(apiError(e, "Creazione cliente fallita")); setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="assegna-cliente-dialog">
        <DialogHeader><DialogTitle>Collega un cliente alla vendita</DialogTitle></DialogHeader>
        {vendita.cliente_nome && <p className="text-sm text-slate-600">Nome registrato: <b>{vendita.cliente_nome}</b></p>}
        {nuovo ? (
          <div className="space-y-2" data-testid="assegna-cliente-nuovo">
            <div className="grid grid-cols-2 gap-2">
              <Input required placeholder="Cognome *" value={nuovo.cognome} onChange={(e) => setNuovo({ ...nuovo, cognome: e.target.value })} data-testid="assegna-nuovo-cognome" />
              <Input required placeholder="Nome *" value={nuovo.nome} onChange={(e) => setNuovo({ ...nuovo, nome: e.target.value })} data-testid="assegna-nuovo-nome" />
              <Input required placeholder="Telefono *" value={nuovo.telefono} onChange={(e) => setNuovo({ ...nuovo, telefono: e.target.value })} data-testid="assegna-nuovo-telefono" />
              <Input placeholder="Cod. fiscale" value={nuovo.codice_fiscale} onChange={(e) => setNuovo({ ...nuovo, codice_fiscale: e.target.value.toUpperCase() })} />
            </div>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="outline" onClick={() => setNuovo(null)}>Indietro</Button>
              <Button size="sm" onClick={creaEAssegna} disabled={saving || !nuovo.cognome || !nuovo.nome} data-testid="assegna-nuovo-salva" className="gap-2">
                <UserPlus className="h-4 w-4" /> {saving ? "Salvo..." : "Crea e collega"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <Input placeholder="Cerca cliente (cognome, telefono, CF)..." value={search} onChange={(e) => setSearch(e.target.value)} data-testid="assegna-cliente-search" />
            {results.length > 0 && (
              <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-200">
                {results.map((c) => (
                  <button type="button" key={c.id} disabled={saving} onClick={() => assegna(c.id)} data-testid={`assegna-cliente-option-${c.id}`}
                          className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-50">
                    <span>{c.cognome} {c.nome}</span><span className="text-xs text-slate-500">{c.telefono}</span>
                  </button>
                ))}
              </div>
            )}
            {search.trim().length >= 2 && results.length === 0 && <p className="text-xs text-slate-500">Nessun cliente trovato.</p>}
            <Button size="sm" variant="outline" className="gap-2" data-testid="assegna-cliente-crea-button"
                    onClick={() => setNuovo({ ...splitNome(vendita.cliente_nome), telefono: "", codice_fiscale: "" })}>
              <UserPlus className="h-4 w-4" /> Crea nuovo cliente
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
