import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Switch } from "./ui/switch";
import { LAVORAZIONI } from "../lib/constants";

const EMPTY = {
  nome: "", cognome: "", tipo_cliente: "privato", codice_fiscale: "", p_iva: "",
  indirizzo: "", provincia: "", pod: "", pdr: "", iban: "", email: "", telefono: "",
  kw_potenza: "", tipo_bolletta: "luce", fornitore_provenienza: "",
  costo_kwh_attuale: "", spese_fisse_attuale: "", costo_smc_attuale: "",
  data_contratto: "", data_verifica: "", data_cambio: "", tipo_contratto: "fisso",
  nuovo_fornitore: "", costo_kwh_nuovo: "", spese_fisse_nuovo: "", costo_smc_nuovo: "",
  privacy_firmata: false, note: "", lavorazione: "da_quotare", venditore_id: "", operatore_id: "",
};

const NUM_FIELDS = ["kw_potenza", "costo_kwh_attuale", "spese_fisse_attuale", "costo_smc_attuale",
  "costo_kwh_nuovo", "spese_fisse_nuovo", "costo_smc_nuovo"];
const DATE_FIELDS = ["data_contratto", "data_verifica", "data_cambio"];

function Field({ label, children, testid }) {
  return (
    <div className="space-y-1.5" data-testid={testid ? `field-${testid}` : undefined}>
      <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</Label>
      {children}
    </div>
  );
}

export default function ClientForm({ open, onClose, client, meta, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [baseline, setBaseline] = useState(EMPTY);
  const [venditori, setVenditori] = useState([]);

  useEffect(() => {
    api.get("/venditori").then((r) => setVenditori(r.data.filter((v) => v.attivo !== false))).catch(() => {});
  }, []);
  const isEdit = Boolean(client);
  const dirty = JSON.stringify(form) !== JSON.stringify(baseline);

  useEffect(() => {
    const handler = (e) => {
      if (open && dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [open, dirty]);

  useEffect(() => {
    if (open) {
      if (client) {
        const f = { ...EMPTY, ...client };
        NUM_FIELDS.forEach((k) => { f[k] = f[k] ?? ""; });
        DATE_FIELDS.forEach((k) => { f[k] = f[k] ? f[k].slice(0, 10) : ""; });
        setForm(f);
        setBaseline(f);
      } else {
        const f = { ...EMPTY, venditore_id: meta.stores[0]?.id || "" };
        setForm(f);
        setBaseline(f);
      }
    }
  }, [open, client, meta]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const isLuce = form.tipo_bolletta === "luce";

  const handleClose = () => {
    if (dirty && !isEdit) {
      if (!window.confirm("Ci sono dati non salvati. Vuoi uscire senza salvare?")) return;
    }
    onClose();
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = { ...form };
    NUM_FIELDS.forEach((k) => { payload[k] = payload[k] === "" ? null : parseFloat(payload[k]); });
    DATE_FIELDS.forEach((k) => { payload[k] = payload[k] || null; });
    try {
      if (isEdit) {
        await api.patch(`/clients/${client.id}`, payload);
        toast.success("Cliente aggiornato");
      } else {
        await api.post("/clients", payload);
        toast.success("Cliente inserito");
      }
      setForm(EMPTY);
      setBaseline(EMPTY);
      onSaved();
      onClose();
    } catch (err) {
      toast.error(apiError(err, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" data-testid="client-form-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">
            {isEdit ? `Modifica ${client.cognome} ${client.nome}` : "Nuovo cliente"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-6" data-testid="client-form">
          <section>
            <h3 className="mb-3 font-heading text-sm font-semibold text-slate-800">Anagrafica</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Nome *" testid="nome">
                <Input required value={form.nome} onChange={(e) => set("nome", e.target.value)} data-testid="input-nome" />
              </Field>
              <Field label="Cognome / Rag. Sociale *" testid="cognome">
                <Input required value={form.cognome} onChange={(e) => set("cognome", e.target.value)} data-testid="input-cognome" />
              </Field>
              <Field label="Tipo cliente" testid="tipo-cliente">
                <Select value={form.tipo_cliente} onValueChange={(v) => set("tipo_cliente", v)}>
                  <SelectTrigger data-testid="select-tipo-cliente"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="privato">Privato</SelectItem>
                    <SelectItem value="business">Business (P.IVA)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Codice Fiscale" testid="cf">
                <Input value={form.codice_fiscale} onChange={(e) => set("codice_fiscale", e.target.value.toUpperCase())} data-testid="input-codice-fiscale" />
              </Field>
              {form.tipo_cliente === "business" && (
                <Field label="Partita IVA" testid="piva">
                  <Input value={form.p_iva} onChange={(e) => set("p_iva", e.target.value)} data-testid="input-p-iva" />
                </Field>
              )}
              <Field label="Indirizzo" testid="indirizzo">
                <Input value={form.indirizzo} onChange={(e) => set("indirizzo", e.target.value)} data-testid="input-indirizzo" />
              </Field>
              <Field label="Provincia" testid="provincia">
                <Input placeholder="es. SO" maxLength={2} value={form.provincia || ""} onChange={(e) => set("provincia", e.target.value.toUpperCase())} data-testid="input-provincia" />
              </Field>
              <Field label="Email" testid="email">
                <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} data-testid="input-email" />
              </Field>
              <Field label="Telefono" testid="telefono">
                <Input value={form.telefono} onChange={(e) => set("telefono", e.target.value)} data-testid="input-telefono" />
              </Field>
              <Field label="IBAN" testid="iban">
                <Input value={form.iban} onChange={(e) => set("iban", e.target.value.toUpperCase())} data-testid="input-iban" />
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 font-heading text-sm font-semibold text-slate-800">Utenza attuale</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Tipo bolletta" testid="tipo-bolletta">
                <Select value={form.tipo_bolletta} onValueChange={(v) => set("tipo_bolletta", v)}>
                  <SelectTrigger data-testid="select-tipo-bolletta"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="luce">Luce</SelectItem>
                    <SelectItem value="gas">Gas</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              {isLuce ? (
                <>
                  <Field label="POD" testid="pod">
                    <Input value={form.pod} onChange={(e) => set("pod", e.target.value.toUpperCase())} data-testid="input-pod" />
                  </Field>
                  <Field label="Potenza (kW)" testid="kw">
                    <Input type="number" step="0.5" value={form.kw_potenza} onChange={(e) => set("kw_potenza", e.target.value)} data-testid="input-kw" />
                  </Field>
                  <Field label="Costo attuale €/kWh" testid="costo-kwh">
                    <Input type="number" step="0.001" value={form.costo_kwh_attuale} onChange={(e) => set("costo_kwh_attuale", e.target.value)} data-testid="input-costo-kwh" />
                  </Field>
                </>
              ) : (
                <>
                  <Field label="PDR" testid="pdr">
                    <Input value={form.pdr} onChange={(e) => set("pdr", e.target.value)} data-testid="input-pdr" />
                  </Field>
                  <Field label="Costo attuale €/Smc" testid="costo-smc">
                    <Input type="number" step="0.001" value={form.costo_smc_attuale} onChange={(e) => set("costo_smc_attuale", e.target.value)} data-testid="input-costo-smc" />
                  </Field>
                </>
              )}
              <Field label="Spese fisse attuali €/mese" testid="spese-fisse">
                <Input type="number" step="0.5" value={form.spese_fisse_attuale} onChange={(e) => set("spese_fisse_attuale", e.target.value)} data-testid="input-spese-fisse" />
              </Field>
              <Field label="Fornitore di provenienza" testid="fornitore">
                <Select value={form.fornitore_provenienza} onValueChange={(v) => set("fornitore_provenienza", v)}>
                  <SelectTrigger data-testid="select-fornitore"><SelectValue placeholder="Seleziona fornitore" /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    {meta.suppliers.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 font-heading text-sm font-semibold text-slate-800">Date & nuovo contratto</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Data di contratto" testid="data-contratto">
                <Input type="date" value={form.data_contratto} onChange={(e) => set("data_contratto", e.target.value)} data-testid="input-data-contratto" />
              </Field>
              <Field label="Data di verifica" testid="data-verifica">
                <Input type="date" value={form.data_verifica} onChange={(e) => set("data_verifica", e.target.value)} data-testid="input-data-verifica" />
              </Field>
              <Field label="Data di cambio" testid="data-cambio">
                <Input type="date" value={form.data_cambio} onChange={(e) => set("data_cambio", e.target.value)} data-testid="input-data-cambio" />
              </Field>
              <Field label="Tipo contratto proposto" testid="tipo-contratto">
                <Select value={form.tipo_contratto} onValueChange={(v) => set("tipo_contratto", v)}>
                  <SelectTrigger data-testid="select-tipo-contratto"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fisso">Fisso</SelectItem>
                    <SelectItem value="variabile">Variabile</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Nuovo fornitore" testid="nuovo-fornitore">
                <Select value={form.nuovo_fornitore} onValueChange={(v) => set("nuovo_fornitore", v)}>
                  <SelectTrigger data-testid="select-nuovo-fornitore"><SelectValue placeholder="Seleziona fornitore" /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    {meta.suppliers.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </Field>
              {isLuce ? (
                <Field label="Nuovo costo €/kWh" testid="costo-kwh-nuovo">
                  <Input type="number" step="0.001" value={form.costo_kwh_nuovo} onChange={(e) => set("costo_kwh_nuovo", e.target.value)} data-testid="input-costo-kwh-nuovo" />
                </Field>
              ) : (
                <Field label="Nuovo costo €/Smc" testid="costo-smc-nuovo">
                  <Input type="number" step="0.001" value={form.costo_smc_nuovo} onChange={(e) => set("costo_smc_nuovo", e.target.value)} data-testid="input-costo-smc-nuovo" />
                </Field>
              )}
              <Field label="Nuove spese fisse €/mese" testid="spese-fisse-nuovo">
                <Input type="number" step="0.5" value={form.spese_fisse_nuovo} onChange={(e) => set("spese_fisse_nuovo", e.target.value)} data-testid="input-spese-fisse-nuovo" />
              </Field>
            </div>
          </section>

          <section>
            <h3 className="mb-3 font-heading text-sm font-semibold text-slate-800">Gestione</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Lavorazione" testid="lavorazione">
                <Select value={form.lavorazione} onValueChange={(v) => set("lavorazione", v)}>
                  <SelectTrigger data-testid="select-lavorazione"><SelectValue /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    {LAVORAZIONI.map((l) => <SelectItem key={l.id} value={l.id}>{l.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Negozio / Venditore" testid="venditore">
                <Select value={form.venditore_id} onValueChange={(v) => set("venditore_id", v)}>
                  <SelectTrigger data-testid="select-venditore"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                  <SelectContent>
                    {meta.stores.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.nome}{s.referente ? ` (${s.referente})` : ""}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Venduto da" testid="operatore">
                <Select value={form.operatore_id} onValueChange={(v) => set("operatore_id", v)}>
                  <SelectTrigger data-testid="select-operatore"><SelectValue placeholder="Seleziona venditore" /></SelectTrigger>
                  <SelectContent>
                    {venditori.map((o) => <SelectItem key={o.id} value={o.id}>{o.nome}{o.store_name ? ` · ${o.store_name}` : ""}</SelectItem>)}
                  </SelectContent>
                </Select>
              </Field>
              <div className="flex items-center gap-3 pt-6">
                <Switch checked={form.privacy_firmata} onCheckedChange={(v) => set("privacy_firmata", v)} data-testid="switch-privacy" />
                <Label className="text-sm">Privacy firmata</Label>
              </div>
            </div>
            <div className="mt-4">
              <Field label="Note" testid="note">
                <Textarea rows={3} value={form.note} onChange={(e) => set("note", e.target.value)} data-testid="input-note" />
              </Field>
            </div>
          </section>

          <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
            <Button type="button" variant="outline" onClick={handleClose} data-testid="client-form-cancel">Annulla</Button>
            <Button type="submit" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="client-form-submit">
              {saving ? "Salvataggio..." : isEdit ? "Salva modifiche" : "Inserisci cliente"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
