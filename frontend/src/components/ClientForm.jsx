import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { apriPortaleDopoSalvataggio } from "./PortaleBox";
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
  indirizzo: "", civico: "", cap: "", comune: "", provincia: "", pod: "", pdr: "", iban: "", email: "", telefono: "",
  kw_potenza: "", tipo_bolletta: "luce", fornitore_provenienza: "", gestione: "cambiaora",
  costo_kwh_attuale: "", spese_fisse_attuale: "", costo_smc_attuale: "",
  data_contratto: "", data_verifica: "", data_cambio: "", tipo_contratto: "fisso",
  nuovo_fornitore: "", costo_kwh_nuovo: "", spese_fisse_nuovo: "", costo_smc_nuovo: "",
  privacy_firmata: false, note: "", lavorazione: "da_quotare", venditore_id: "", operatore_id: "",
};

const NUM_FIELDS = ["kw_potenza", "costo_kwh_attuale", "spese_fisse_attuale", "costo_smc_attuale",
  "costo_kwh_nuovo", "spese_fisse_nuovo", "costo_smc_nuovo"];
const DATE_FIELDS = ["data_contratto", "data_verifica", "data_cambio"];

function FornitoreSelect({ campo, value, set, suppliers, nuovo, setNuovo, onAdd, testid }) {
  if (nuovo?.campo === campo) {
    return (
      <div className="flex gap-2">
        <Input autoFocus placeholder="Nome nuovo fornitore" value={nuovo.value}
               onChange={(e) => setNuovo({ campo, value: e.target.value })}
               onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onAdd(); } }} data-testid={`${testid}-nuovo-input`} />
        <Button type="button" size="sm" onClick={onAdd} data-testid={`${testid}-nuovo-salva`}>Aggiungi</Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setNuovo(null)} data-testid={`${testid}-nuovo-annulla`}>✕</Button>
      </div>
    );
  }
  return (
    <div className="flex gap-2">
      <Select value={value} onValueChange={(v) => set(campo, v)}>
        <SelectTrigger data-testid={testid}><SelectValue placeholder="Seleziona fornitore" /></SelectTrigger>
        <SelectContent className="max-h-64">
          {suppliers.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
        </SelectContent>
      </Select>
      <Button type="button" size="sm" variant="outline" title="Aggiungi un fornitore non in elenco"
              onClick={() => setNuovo({ campo, value: "" })} data-testid={`${testid}-nuovo-btn`}>+ Nuovo</Button>
    </div>
  );
}

function Field({ label, children, testid }) {
  return (
    <div className="space-y-1.5" data-testid={testid ? `field-${testid}` : undefined}>
      <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</Label>
      {children}
    </div>
  );
}

export default function ClientForm({ open, onClose, client, meta, onSaved, prefill }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [baseline, setBaseline] = useState(EMPTY);
  const [venditori, setVenditori] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [nuovoFornitore, setNuovoFornitore] = useState(null);

  useEffect(() => {
    api.get("/venditori").then((r) => setVenditori(r.data.filter((v) => v.attivo !== false))).catch(() => {});
  }, []);
  useEffect(() => { setSuppliers(meta.suppliers || []); }, [meta.suppliers]);

  const aggiungiFornitore = async () => {
    const nome = (nuovoFornitore?.value || "").trim();
    if (nome.length < 2) return;
    try {
      const r = await api.post("/fornitori", { nome });
      setSuppliers((s) => (s.includes(r.data.nome) ? s : [...s, r.data.nome]));
      set(nuovoFornitore.campo, r.data.nome);
      setNuovoFornitore(null);
      toast.success(`Fornitore "${r.data.nome}" aggiunto`);
    } catch (e) {
      toast.error(apiError(e, "Impossibile aggiungere il fornitore"));
    }
  };
  const isEdit = Boolean(client);
  const dirty = JSON.stringify(form) !== JSON.stringify(baseline);
  const draftKey = `client_form_draft:${client?.id || "nuovo"}`;
  const [draft, setDraft] = useState(null);

  // Bozza automatica: salva in locale ogni modifica (solo se ci sono dati diversi dalla base)
  useEffect(() => {
    if (!open || draft || !dirty) return;
    localStorage.setItem(draftKey, JSON.stringify({ form, at: new Date().toISOString() }));
  }, [form, dirty, open, draftKey, draft]);

  const ripristinaBozza = () => {
    if (draft?.form) setForm({ ...EMPTY, ...draft.form });
    setDraft(null);
    toast.success("Bozza ripristinata");
  };
  const scartaBozza = () => {
    localStorage.removeItem(draftKey);
    setDraft(null);
  };

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
    if (!open) return;
    try {
      const raw = localStorage.getItem(`client_form_draft:${client?.id || "nuovo"}`);
      setDraft(raw ? JSON.parse(raw) : null);
    } catch {
      setDraft(null);
    }
    const applica = (src) => {
      const f = { ...EMPTY, ...src };
      NUM_FIELDS.forEach((k) => { f[k] = f[k] ?? ""; });
      DATE_FIELDS.forEach((k) => { f[k] = f[k] ? f[k].slice(0, 10) : ""; });
      setForm(f);
      setBaseline(f);
    };
    if (client) {
      applica(client);
      // La riga della lista ha solo alcuni campi: carico SEMPRE la scheda completa per non sovrascrivere dati
      api.get(`/clients/${client.id}`).then((r) => applica(r.data)).catch(() => toast.error("Impossibile caricare la scheda completa"));
    } else {
      const f = { ...EMPTY, venditore_id: meta.stores[0]?.id || "", ...(prefill || {}) };
      setForm(f);
      setBaseline(prefill ? { ...EMPTY, venditore_id: meta.stores[0]?.id || "" } : f);
    }
  }, [open, client, meta, prefill]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const isLuce = form.tipo_bolletta === "luce";
  const tipoCliente = form.tipo_cliente === "business" ? "societa" : (form.tipo_cliente || "privato");
  const isBusiness = tipoCliente !== "privato";
  const isSocieta = tipoCliente === "societa";

  const handleClose = () => {
    if (dirty && !isEdit) {
      if (!window.confirm("Ci sono dati non salvati. Vuoi uscire senza salvare? (La bozza resta salvata in locale)")) return;
    }
    onClose();
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = { ...form, tipo_cliente: tipoCliente };
    NUM_FIELDS.forEach((k) => { payload[k] = payload[k] === "" ? null : parseFloat(payload[k]); });
    DATE_FIELDS.forEach((k) => { payload[k] = payload[k] || null; });
    try {
      if (isEdit) {
        await api.patch(`/clients/${client.id}`, payload);
        toast.success("Cliente aggiornato");
      } else {
        await api.post("/clients", payload);
        toast.success("Cliente inserito");
        if (payload.nuovo_fornitore) api.get("/portali").then((r) => apriPortaleDopoSalvataggio(r.data, "energia", payload.nuovo_fornitore)).catch(() => {});
      }
      setForm(EMPTY);
      setBaseline(EMPTY);
      localStorage.removeItem(draftKey);
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
          {draft && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="client-draft-banner">
              <span>
                Bozza non salvata trovata ({new Date(draft.at).toLocaleString("it-IT")})
                {draft.form?.cognome || draft.form?.nome ? ` — ${draft.form.cognome || ""} ${draft.form.nome || ""}`.trimEnd() : ""}
              </span>
              <div className="flex gap-2">
                <Button type="button" size="sm" onClick={ripristinaBozza} data-testid="client-draft-restore" className="bg-amber-600 hover:bg-amber-700">Ripristina bozza</Button>
                <Button type="button" size="sm" variant="outline" onClick={scartaBozza} data-testid="client-draft-discard">Scarta</Button>
              </div>
            </div>
          )}
          <section>
            <h3 className="mb-3 font-heading text-sm font-semibold text-slate-800">Anagrafica</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Nome *" testid="nome">
                <Input required value={form.nome} onChange={(e) => set("nome", e.target.value)} data-testid="input-nome" />
              </Field>
              <Field label={isSocieta ? "Ragione sociale *" : "Cognome *"} testid="cognome">
                <Input required value={form.cognome} onChange={(e) => set("cognome", e.target.value)} data-testid="input-cognome" />
              </Field>
              <Field label="Tipo cliente" testid="tipo-cliente">
                <Select value={tipoCliente} onValueChange={(v) => set("tipo_cliente", v)}>
                  <SelectTrigger data-testid="select-tipo-cliente"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="privato">Privato (solo CF)</SelectItem>
                    <SelectItem value="ditta_individuale">Ditta individuale (CF + P.IVA)</SelectItem>
                    <SelectItem value="societa">Società (P.IVA)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label={tipoCliente === "ditta_individuale" ? "Codice Fiscale *" : "Codice Fiscale"} testid="cf">
                <Input required={tipoCliente === "ditta_individuale"} value={form.codice_fiscale}
                       onChange={(e) => set("codice_fiscale", e.target.value.toUpperCase())} data-testid="input-codice-fiscale" />
              </Field>
              {isBusiness && (
                <Field label="Partita IVA *" testid="piva">
                  <Input required value={form.p_iva} onChange={(e) => set("p_iva", e.target.value.replace(/\D/g, "").slice(0, 11))}
                         placeholder="11 cifre" data-testid="input-p-iva" />
                </Field>
              )}
              <Field label="Via / Indirizzo" testid="indirizzo">
                <Input value={form.indirizzo} onChange={(e) => set("indirizzo", e.target.value)} data-testid="input-indirizzo" />
              </Field>
              <Field label="N. civico" testid="civico">
                <Input value={form.civico || ""} onChange={(e) => set("civico", e.target.value)} data-testid="input-civico" />
              </Field>
              <Field label="CAP" testid="cap">
                <Input inputMode="numeric" maxLength={5} value={form.cap || ""} onChange={(e) => set("cap", e.target.value.replace(/\D/g, ""))} data-testid="input-cap" />
              </Field>
              <Field label="Comune" testid="comune">
                <Input value={form.comune || ""} onChange={(e) => set("comune", e.target.value)} data-testid="input-comune" />
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
              <Field label="Gestione (canale WhatsApp)" testid="gestione">
                <Select value={form.gestione || "cambiaora"} onValueChange={(v) => set("gestione", v)}>
                  <SelectTrigger data-testid="select-gestione"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cambiaora">CambiaOra (numero 3519460591)</SelectItem>
                    <SelectItem value="enel">ENEL (numero Deborah / Gravedona)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
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
                <FornitoreSelect campo="fornitore_provenienza" value={form.fornitore_provenienza} set={set} suppliers={suppliers}
                                 nuovo={nuovoFornitore} setNuovo={setNuovoFornitore} onAdd={aggiungiFornitore} testid="select-fornitore" />
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
                <FornitoreSelect campo="nuovo_fornitore" value={form.nuovo_fornitore} set={set} suppliers={suppliers}
                                 nuovo={nuovoFornitore} setNuovo={setNuovoFornitore} onAdd={aggiungiFornitore} testid="select-nuovo-fornitore" />
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
              <Field label="Negozio" testid="venditore">
                <Select value={form.venditore_id} onValueChange={(v) => set("venditore_id", v)}>
                  <SelectTrigger data-testid="select-venditore"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                  <SelectContent>
                    {meta.stores.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Venduto da (a chi va il compenso)" testid="operatore">
                <Select value={form.operatore_id || "__negozio__"} onValueChange={(v) => set("operatore_id", v === "__negozio__" ? "" : v)}>
                  <SelectTrigger data-testid="select-operatore"><SelectValue placeholder="Seleziona" /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    <SelectItem value="__negozio__">Negozio (compenso al negozio)</SelectItem>
                    {venditori.map((o) => <SelectItem key={o.id} value={o.id}>{o.nome}</SelectItem>)}
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
