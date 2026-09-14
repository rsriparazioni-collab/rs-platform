import { useEffect, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Checkbox } from "./ui/checkbox";

export const uploadRitiroDocumenti = async (ritiroId, files) => {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return api.post(`/ritiri/${ritiroId}/documenti`, fd, { headers: { "Content-Type": "multipart/form-data" } });
};

const costoRicambiDaRiparazione = (s) => {
  if (!s) return 0;
  const usati = (s.ricambi_usati || []).reduce((t, u) => t + (Number(u.prezzo_vendita) || 0) * (u.quantita || 1), 0);
  if (usati > 0) return usati;
  return s.con_ricambio ? Number(s.costo_componente) || 0 : 0;
};

export default function RitiroDaRiparazione({ open, onClose, servizio, onCreated }) {
  const [form, setForm] = useState({ imei: "", prezzo_ritiro: "0", numero_documento: "", n_allegati: 2, costo_ricambi: "0", crea_rigenerato: true, marca: "", modello: "" });
  const [files, setFiles] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      const dev = (servizio?.dispositivo || "").trim();
      const [marca, ...rest] = dev.split(" ");
      setForm({ imei: "", prezzo_ritiro: "0", numero_documento: "", n_allegati: 2,
                costo_ricambi: String(costoRicambiDaRiparazione(servizio).toFixed(2)), crea_rigenerato: true,
                marca: rest.length ? marca : "", modello: rest.length ? rest.join(" ") : dev });
      setFiles([]);
    }
  }, [open, servizio]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const c = servizio?.client_contacts || {};
  const costoTot = (parseFloat(form.prezzo_ritiro) || 0) + (parseFloat(form.costo_ricambi) || 0);

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
        articolo: `${form.marca} ${form.modello}`.trim() || servizio.dispositivo || "",
        marca: form.marca,
        modello: form.modello,
        imei: form.imei,
        prezzo_ritiro: form.prezzo_ritiro === "" ? 0 : parseFloat(form.prezzo_ritiro),
        numero_documento: form.numero_documento,
        n_allegati: files.length || parseInt(form.n_allegati) || 0,
        costo_ricambi: parseFloat(form.costo_ricambi) || 0,
        crea_rigenerato: form.crea_rigenerato,
      });
      if (files.length) {
        try { await uploadRitiroDocumenti(res.data.id, files); }
        catch (err) { toast.error(apiError(err, "Bolla creata ma documenti non allegati")); }
      }
      toast.success(`Bolla ${res.data.numero} generata${files.length ? ` con ${files.length} documenti` : ""}${form.crea_rigenerato ? " · dispositivo caricato in Magazzino (rigenerati)" : ""}`);
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
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto" data-testid="ritiro-rip-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">Telefono ritirato</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" data-testid="ritiro-rip-form">
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <p className="font-medium text-slate-900" data-testid="ritiro-rip-cliente">{c.cognome} {c.nome}</p>
            <p className="text-slate-600">{servizio?.dispositivo} · Rip. N° {servizio?.numero_riparazione}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Marca</Label>
              <Input value={form.marca} onChange={(e) => set("marca", e.target.value)} placeholder="es. Samsung" data-testid="ritiro-rip-marca" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Modello</Label>
              <Input value={form.modello} onChange={(e) => set("modello", e.target.value)} placeholder="es. Galaxy Z Flip 6" data-testid="ritiro-rip-modello" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">IMEI</Label>
              <Input value={form.imei} onChange={(e) => set("imei", e.target.value)} data-testid="ritiro-rip-imei" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prezzo ritiro € (in bolla)</Label>
              <Input type="number" step="0.01" min="0" value={form.prezzo_ritiro} onChange={(e) => set("prezzo_ritiro", e.target.value)} data-testid="ritiro-rip-prezzo" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">N° documento</Label>
              <Input value={form.numero_documento} onChange={(e) => set("numero_documento", e.target.value)} data-testid="ritiro-rip-documento" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Costo ricambi a nostro carico €</Label>
              <Input type="number" step="0.01" min="0" value={form.costo_ricambi} onChange={(e) => set("costo_ricambi", e.target.value)} data-testid="ritiro-rip-costo-ricambi" />
              <p className="text-[11px] text-slate-400">Non compare in bolla: serve per il costo del dispositivo.</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Documenti cliente (PDF/foto) — uniti alla bolla</Label>
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
              <Paperclip className="h-4 w-4" /> Scegli file
              <input type="file" multiple accept="application/pdf,image/jpeg,image/png,image/webp" className="hidden"
                     onChange={(e) => setFiles((f) => [...f, ...Array.from(e.target.files || [])])} data-testid="ritiro-rip-files" />
            </label>
            {files.length > 0 && (
              <ul className="space-y-1 text-xs" data-testid="ritiro-rip-files-list">
                {files.map((f, i) => (
                  <li key={`${f.name}-${f.size}-${f.lastModified}`} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1">
                    <span className="truncate">{f.name}</span>
                    <button type="button" onClick={() => setFiles((l) => l.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-600"><X className="h-3.5 w-3.5" /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <label className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50/50 px-3 py-2 text-sm">
            <Checkbox checked={form.crea_rigenerato} onCheckedChange={(v) => set("crea_rigenerato", !!v)} data-testid="ritiro-rip-rigenerato" />
            <span>
              <span className="font-medium text-slate-900">Carica in Magazzino come rigenerato</span>
              <span className="block text-xs text-slate-500">Costo dispositivo: € {costoTot.toFixed(2)} (ritiro + ricambi). Il margine si calcola alla vendita.</span>
            </span>
          </label>

          <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
            <Button type="button" variant="outline" onClick={onClose} data-testid="ritiro-rip-cancel">Annulla</Button>
            <Button type="submit" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="ritiro-rip-submit">
              {saving ? "Generazione bolla..." : "Conferma ritiro e genera bolla"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
