import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

export default function RitiroDaRiparazione({ open, onClose, servizio, onCreated }) {
  const [form, setForm] = useState({ imei: "", prezzo_ritiro: "", numero_documento: "", n_allegati: 2 });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setForm({ imei: "", prezzo_ritiro: "", numero_documento: "", n_allegati: 2 });
  }, [open]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const c = servizio?.client_contacts || {};

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api.post("/ritiri", {
        store_id: servizio.venditore_id || "",
        client_id: servizio.client_id,
        servizio_id: servizio.id,
        nome: c.nome || "",
        cognome: c.cognome || "",
        codice_fiscale: c.codice_fiscale || "",
        articolo: servizio.dispositivo || "",
        imei: form.imei,
        prezzo_ritiro: form.prezzo_ritiro === "" ? null : parseFloat(form.prezzo_ritiro),
        numero_documento: form.numero_documento,
        n_allegati: parseInt(form.n_allegati) || 2,
      });
      toast.success(`Bolla di ritiro ${res.data.numero} generata e collegata alla riparazione`);
      onCreated();
      onClose();
    } catch (err) {
      toast.error(apiError(err, "Creazione ritiro fallita"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md" data-testid="ritiro-rip-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">Ritiro telefono da riparazione</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" data-testid="ritiro-rip-form">
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <p className="font-medium text-slate-900" data-testid="ritiro-rip-cliente">{c.cognome} {c.nome}</p>
            <p className="text-slate-600">{servizio?.dispositivo} · Rip. N° {servizio?.numero_riparazione}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">IMEI</Label>
              <Input value={form.imei} onChange={(e) => set("imei", e.target.value)} data-testid="ritiro-rip-imei" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prezzo ritiro €</Label>
              <Input type="number" step="0.01" value={form.prezzo_ritiro} onChange={(e) => set("prezzo_ritiro", e.target.value)} data-testid="ritiro-rip-prezzo" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">N° documento</Label>
              <Input value={form.numero_documento} onChange={(e) => set("numero_documento", e.target.value)} data-testid="ritiro-rip-documento" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Allegati (n.)</Label>
              <Input type="number" min="0" value={form.n_allegati} onChange={(e) => set("n_allegati", e.target.value)} data-testid="ritiro-rip-allegati" />
            </div>
          </div>
          <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
            <Button type="button" variant="outline" onClick={onClose} data-testid="ritiro-rip-cancel">Annulla</Button>
            <Button type="submit" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="ritiro-rip-submit">
              {saving ? "Generazione bolla..." : "Genera bolla ritiro"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
