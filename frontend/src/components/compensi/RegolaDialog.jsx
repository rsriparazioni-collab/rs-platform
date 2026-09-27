import { useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Switch } from "../ui/switch";
import { Checkbox } from "../ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";

const VUOTA = { nome: "", destinatario_tipo: "store", destinatario_id: "", voce: "sim", modalita: "per_unita", importo: 0, operatore_tel: "", tipo_attivazione: "",
  provenienza_in: [], provenienza_not_in: [], enel_voci: [], soglia: 0, conteggio_globale: false, solo_incassato: false, mesi_pagamento: 0, e_gara: false, valido_da: "", valido_a: "", attiva: true, note: "" };

const F = ({ label, children }) => <div className="space-y-1.5"><Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</Label>{children}</div>;

export const RegolaDialog = ({ meta, regola, onClose, onSaved }) => {
  const [f, setF] = useState({ ...VUOTA, ...regola });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const toggleIn = (k, v) => set(k, f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v]);
  const isTel = ["sim", "internet", "fisso"].includes(f.voce);
  const dest = f.destinatario_tipo === "store" ? meta.stores.map((s) => ({ id: s.id, label: s.nome })) : meta.users.map((u) => ({ id: u.id, label: u.name }));

  const salva = async (e) => {
    e.preventDefault();
    setBusy(true);
    const payload = { ...f, importo: parseFloat(f.importo) || 0, soglia: parseInt(f.soglia) || 0, mesi_pagamento: parseInt(f.mesi_pagamento) || 0 };
    delete payload.id; delete payload.created_at; delete payload.updated_at;
    try {
      if (regola.id) await api.put(`/compensi/regole/${regola.id}`, payload); else await api.post("/compensi/regole", payload);
      toast.success("Regola salvata"); onSaved();
    } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="regola-dialog">
        <DialogHeader><DialogTitle className="font-heading">{regola.id ? "Modifica regola" : "Nuova regola compenso"}</DialogTitle></DialogHeader>
        <form onSubmit={salva} className="space-y-4">
          <F label="Nome regola *"><Input value={f.nome} onChange={(e) => set("nome", e.target.value)} required data-testid="regola-nome" /></F>
          <div className="grid gap-3 sm:grid-cols-2">
            <F label="Destinatario"><Select value={f.destinatario_tipo} onValueChange={(v) => { set("destinatario_tipo", v); set("destinatario_id", ""); }}><SelectTrigger data-testid="regola-dest-tipo"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="store">Negozio</SelectItem><SelectItem value="user">Operatore / venditore</SelectItem></SelectContent></Select></F>
            <F label="Chi"><Select value={f.destinatario_id || "all"} onValueChange={(v) => set("destinatario_id", v === "all" ? "" : v)}><SelectTrigger data-testid="regola-dest-id"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">Tutti</SelectItem>{dest.map((d) => <SelectItem key={d.id} value={d.id}>{d.label}</SelectItem>)}</SelectContent></Select></F>
            <F label="Voce"><Select value={f.voce} onValueChange={(v) => set("voce", v)}><SelectTrigger data-testid="regola-voce"><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(meta.voci).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></F>
            <F label="Modalità"><Select value={f.modalita} onValueChange={(v) => set("modalita", v)}><SelectTrigger data-testid="regola-modalita"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="per_unita">€ per ogni contratto/attivazione</SelectItem><SelectItem value="forfait">Forfait (bonus fisso al raggiungimento)</SelectItem></SelectContent></Select></F>
            <F label="Importo €"><Input type="number" step="0.01" value={f.importo} onChange={(e) => set("importo", e.target.value)} data-testid="regola-importo" /></F>
            <F label="Pagato dopo (mesi) – es. CambiaOra 2, gare 3"><Input type="number" min="0" value={f.mesi_pagamento} onChange={(e) => set("mesi_pagamento", e.target.value)} data-testid="regola-mesi" /></F>
          </div>
          {isTel && (
            <div className="grid gap-3 sm:grid-cols-2">
              <F label="Operatore telefonico (vuoto = tutti; più operatori separati da virgola)"><Input value={f.operatore_tel} onChange={(e) => set("operatore_tel", e.target.value)} placeholder="es. WINDTRE,VERY" data-testid="regola-operatore" /></F>
              {f.voce === "sim" && <F label="Tipo attivazione"><Select value={f.tipo_attivazione || "all"} onValueChange={(v) => set("tipo_attivazione", v === "all" ? "" : v)}><SelectTrigger data-testid="regola-attivazione"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="all">Qualsiasi</SelectItem><SelectItem value="nuovo">Numero nuovo</SelectItem><SelectItem value="mnp">MNP</SelectItem><SelectItem value="cambio_offerta">Cambio offerta</SelectItem></SelectContent></Select></F>}
            </div>
          )}
          {f.voce === "sim" && f.tipo_attivazione === "mnp" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <F label="Solo se MNP proviene da">
                <div className="flex flex-wrap gap-2">{meta.provenienze.map((p) => <label key={p} className="flex items-center gap-1 text-xs"><Checkbox checked={f.provenienza_in.includes(p)} onCheckedChange={() => toggleIn("provenienza_in", p)} />{p}</label>)}</div></F>
              <F label="Escludi se proviene da">
                <div className="flex flex-wrap gap-2">{meta.provenienze.map((p) => <label key={p} className="flex items-center gap-1 text-xs"><Checkbox checked={f.provenienza_not_in.includes(p)} onCheckedChange={() => toggleIn("provenienza_not_in", p)} />{p}</label>)}</div></F>
            </div>
          )}
          {f.voce === "enel" && (
            <F label="Operazioni ENEL conteggiate (vuoto = tutte)">
              <div className="flex flex-wrap gap-2">{meta.enel_voci.map((p) => <label key={p} className="flex items-center gap-1 text-xs"><Checkbox checked={f.enel_voci.includes(p)} onCheckedChange={() => toggleIn("enel_voci", p)} />{p}</label>)}</div></F>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <F label="Soglia minima (0 = nessuna)"><Input type="number" min="0" value={f.soglia} onChange={(e) => set("soglia", e.target.value)} data-testid="regola-soglia" /></F>
            <F label="Valido da (AAAA-MM)"><Input placeholder="2026-01" value={f.valido_da} onChange={(e) => set("valido_da", e.target.value)} data-testid="regola-da" /></F>
            <F label="Valido fino a (AAAA-MM)"><Input placeholder="vuoto = sempre" value={f.valido_a} onChange={(e) => set("valido_a", e.target.value)} data-testid="regola-a" /></F>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-sm"><Switch checked={f.conteggio_globale} onCheckedChange={(v) => set("conteggio_globale", v)} data-testid="regola-globale" /> Soglia contata su tutti i negozi (globale)</label>
            <label className="flex items-center gap-2 text-sm"><Switch checked={f.solo_incassato} onCheckedChange={(v) => set("solo_incassato", v)} data-testid="regola-incassato" /> Solo contratti incassati/pagati</label>
            <label className="flex items-center gap-2 text-sm"><Switch checked={f.e_gara} onCheckedChange={(v) => set("e_gara", v)} data-testid="regola-gara" /> È una gara (si paga solo a incasso avvenuto)</label>
            <label className="flex items-center gap-2 text-sm"><Switch checked={f.attiva} onCheckedChange={(v) => set("attiva", v)} data-testid="regola-attiva" /> Regola attiva</label>
          </div>
          <F label="Note"><Textarea rows={2} value={f.note} onChange={(e) => set("note", e.target.value)} data-testid="regola-note" /></F>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Annulla</Button>
            <Button type="submit" disabled={busy || !f.nome} data-testid="regola-salva">Salva regola</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
