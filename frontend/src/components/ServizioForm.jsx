import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { apriPortaleDopoSalvataggio } from "./PortaleBox";
import { SERVIZIO_TIPI, RIP_STATI, TEL_OPERATORS, SBLOCCO_TIPI, SIM_ATTIVAZIONI, SIM_PROVENIENZE, WT_CATEGORIE_FISSO, WT_ESITI } from "../lib/constants";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import VenditaOrdineBox from "./VenditaOrdineBox";
import { DocumentiPicker, uploadDocumenti } from "./DocumentiPicker";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Switch } from "./ui/switch";

const EMPTY_NEW_CLIENT = { nome: "", cognome: "", telefono: "", email: "", codice_fiscale: "" };

const marcaDispositivo = (d = "") => {
  const s = d.toLowerCase();
  if (["iphone", "apple", "ipad", "macbook", "airpods", "watch"].some((k) => s.includes(k))) return "apple";
  if (s.includes("samsung") || s.includes("galaxy")) return "samsung";
  return "altri";
};
const round5 = (x) => 5 * Math.round(x / 5);

export function regolaPer(regole, form) {
  const tip = form.con_ricambio ? (form.tipo_ricambio || "altro") : "software";
  const marca = marcaDispositivo(form.dispositivo);
  const cands = (regole || []).filter((r) => r.tipologia === tip);
  return cands.find((r) => r.marca === marca) || cands.find((r) => r.marca === "*") || null;
}

function prezzoConsigliato(tipo, conRicambio, costo, minuti, tipoRicambio, regole, dispositivo) {
  if (tipo !== "riparazione") return null;
  const minRaw = parseInt(minuti) || 0;
  const regola = regolaPer(regole, { con_ricambio: conRicambio, tipo_ricambio: tipoRicambio, dispositivo });
  if (regola) {
    const c = conRicambio ? (parseFloat(costo) || 0) + 2.5 : 0;
    const base = c * (1 + regola.ricarico_pct / 100) + regola.manodopera + Math.max(minRaw - 30, 0) * 0.22775;
    let p = round5(base * 1.22);
    if (regola.prezzo_min && (!conRicambio || c * 1.22 < regola.prezzo_min)) p = Math.max(p, regola.prezzo_min);
    if (regola.prezzo_max && c * 1.22 + regola.manodopera * 1.22 <= regola.prezzo_max) p = Math.min(p, regola.prezzo_max);
    return p;
  }
  if (conRicambio && tipoRicambio === "batteria") {
    return Math.round(((parseFloat(costo) || 0) + 2 + minRaw * 0.22775 + 20) * 1.22 * 100) / 100;
  }
  const min = Math.max(minRaw, 30);
  const lavoro = min * 0.22775;
  const base = conRicambio ? (parseFloat(costo) || 0) + 2 + lavoro + 60 : 30 + lavoro;
  return Math.round(base * 1.22 * 100) / 100;
}

export default function ServizioForm({ open, onClose, servizio, defaultTipo, meta, onSaved, presetClient }) {
  const isEdit = Boolean(servizio);
  const [tipo, setTipo] = useState(defaultTipo || "riparazione");
  const [form, setForm] = useState({});
  const [clientId, setClientId] = useState("");
  const [clientLabel, setClientLabel] = useState("");
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [newClient, setNewClient] = useState(null);
  const [saving, setSaving] = useState(false);
  const [nuoviDoc, setNuoviDoc] = useState([]);

  useEffect(() => {
    if (open) {
      const t = servizio?.tipo || defaultTipo || "riparazione";
      setTipo(t);
      setForm(servizio ? { ...servizio } : { stato: "ingresso", con_ricambio: false, pagato: false, data_ingresso: new Date().toISOString().slice(0, 10), data_attivazione: new Date().toISOString().slice(0, 10) });
      setNuoviDoc([]);
      setRicambioMag(null); setMagLabel(""); setMagSearch("");
      setClientId(servizio?.client_id || presetClient?.id || "");
      setClientLabel(servizio?.client_name || presetClient?.label || "");
      setSearch("");
      setResults([]);
      setNewClient(null);
    }
  }, [open, servizio, defaultTipo, presetClient]);

  useEffect(() => {
    if (search.trim().length < 2 || clientId) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      api.get("/clients", { params: { q: search.trim() } })
        .then((r) => setResults(r.data.slice(0, 6)))
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [search, clientId]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const [magSearch, setMagSearch] = useState("");
  const [magResults, setMagResults] = useState([]);
  const [magLabel, setMagLabel] = useState("");
  const [ricambioMag, setRicambioMag] = useState(null);
  useEffect(() => {
    if (magSearch.trim().length < 2 || form.magazzino_item_id || ricambioMag) { setMagResults([]); return undefined; }
    const t = setTimeout(() => api.get("/magazzino/disponibilita", { params: { q: magSearch.trim(), ...(tipo === "sim" ? { categoria: "sim" } : {}) } }).then((r) => setMagResults(r.data.slice(0, 8))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [magSearch, form.magazzino_item_id, ricambioMag, tipo]);
  const pickMag = (g, s) => {
    if (tipo === "sim") { setForm((f) => ({ ...f, magazzino_item_id: s.item_id, quantita: 1 })); setMagLabel(`${g.nome} · ${s.store_name}`); setMagSearch(""); setMagResults([]); return; }
    setForm((f) => ({ ...f, magazzino_item_id: s.item_id, quantita: 1, prodotto: g.nome, importo: s.prezzo_vendita ?? f.importo }));
    setMagLabel(`${g.nome} · ${s.store_name}`); setMagSearch(""); setMagResults([]);
  };
  const pickRicambio = (g, s) => {
    setRicambioMag({ item_id: s.item_id, store_id: s.store_id, store_name: s.store_name, nome: g.nome, tipologia: g.tipologia || "altro", quantita: 1, disponibile: s.quantita > 0 });
    setForm((f) => ({ ...f, con_ricambio: true, tipo_ricambio: g.tipologia && g.tipologia !== "altro" ? g.tipologia : f.tipo_ricambio,
      costo_componente: s.prezzo_acquisto ?? f.costo_componente }));
    setMagSearch(""); setMagResults([]);
  };
  const collegaRicambio = async (servizioId) => {
    if (!ricambioMag) return;
    const r = ricambioMag;
    if (r.disponibile) {
      await api.post(`/servizi/${servizioId}/ricambi`, { magazzino_id: r.item_id, quantita: r.quantita });
    } else {
      await api.post(`/servizi/${servizioId}/ricambi/ordina`, { magazzino_id: r.item_id, quantita: r.quantita, tipologia: r.tipologia, da_store_id: r.store_id !== form.venditore_id ? r.store_id : "" });
    }
  };
  const isRip = tipo === "riparazione";
  const isTel = ["sim", "internet", "fisso"].includes(tipo);
  const isSim = tipo === "sim";
  const isWT = isTel && ["windtre", "very"].includes((form.operatore_tel || "").toLowerCase());
  const isShop = ["accessori", "vendita"].includes(tipo);
  const [regole, setRegole] = useState([]);
  const [listinoQ, setListinoQ] = useState("");
  const [listino, setListino] = useState([]);
  useEffect(() => { if (open) api.get("/regole-prezzi").then((r) => setRegole(r.data.regole)).catch(() => {}); }, [open]);
  useEffect(() => {
    if (!listinoQ || listinoQ.length < 2) { setListino([]); return; }
    const t = setTimeout(() => api.get("/listino", { params: { q: listinoQ, limit: 8 } }).then((r) => setListino(r.data)).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [listinoQ]);
  const prezzo = useMemo(
    () => prezzoConsigliato(tipo, form.con_ricambio, form.costo_componente, form.minuti_lavoro, form.tipo_ricambio, regole, form.dispositivo),
    [tipo, form.con_ricambio, form.costo_componente, form.minuti_lavoro, form.tipo_ricambio, regole, form.dispositivo]
  );
  const regolaAttiva = regolaPer(regole, { con_ricambio: form.con_ricambio, tipo_ricambio: form.tipo_ricambio, dispositivo: form.dispositivo });

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      let cid = clientId;
      if (!isEdit && !cid && newClient) {
        const c = await api.post("/clients", {
          ...EMPTY_NEW_CLIENT, ...newClient,
          venditore_id: form.venditore_id || meta.stores[0]?.id || "",
          lavorazione: "da_quotare",
          origine: tipo === "riparazione" ? "riparazione" : "telefonia",
        });
        cid = c.data.id;
      }
      const payload = {
        ...form, tipo, client_id: cid,
        costo_componente: form.costo_componente === "" || form.costo_componente == null ? null : parseFloat(form.costo_componente),
        minuti_lavoro: form.minuti_lavoro === "" || form.minuti_lavoro == null ? null : parseInt(form.minuti_lavoro),
        importo: form.importo === "" || form.importo == null ? null : parseFloat(form.importo),
        acconto: form.acconto === "" || form.acconto == null ? null : parseFloat(form.acconto),
        vincolo_mesi: form.vincolo_mesi === "" || form.vincolo_mesi == null ? null : parseInt(form.vincolo_mesi),
        data_attivazione: form.data_attivazione || null,
        data_ingresso: form.data_ingresso || null,
        data_lavorazione: form.data_lavorazione || null,
        data_uscita: form.data_uscita || null,
        prezzo_finale: form.prezzo_finale === "" || form.prezzo_finale == null ? null : parseFloat(form.prezzo_finale),
        codice_sblocco: form.codice_sblocco || "",
        account_password: form.account_password || "",
      };
      let servizioId = servizio?.id;
      if (isEdit) {
        await api.patch(`/servizi/${servizio.id}`, payload);
        toast.success("Servizio aggiornato");
      } else {
        const created = await api.post("/servizi", payload);
        servizioId = created.data.id;
        toast.success("Servizio inserito");
        if (tipo === "riparazione" && ricambioMag) {
          try { await collegaRicambio(created.data.id); toast.success(ricambioMag.disponibile ? "Ricambio scalato dal magazzino" : "Ricambio messo in ordine"); }
          catch (e) { toast.error(apiError(e, "Ricambio non collegato: aggiungilo dal dettaglio riparazione")); }
        }
        const sez = { sim: "mobile", internet: "fisso", fisso: "fisso", riparazione: "riparazioni" }[tipo];
        api.get("/portali").then((r) => apriPortaleDopoSalvataggio(r.data, sez, payload.operatore_tel || payload.fornitore_ricambio)).catch(() => {});
      }
      if (nuoviDoc.length) {
        try { await uploadDocumenti(nuoviDoc, { clientId: cid, servizioId }); toast.success(`${nuoviDoc.length} documenti allegati al cliente e al servizio`); }
        catch (e) { toast.error(apiError(e, "Servizio salvato ma documenti non caricati: allegali dal dettaglio")); }
      }
      onSaved();
      onClose();
    } catch (err) {
      toast.error(apiError(err, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="servizio-form-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">
            {isEdit ? "Modifica servizio" : "Nuovo servizio"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5" data-testid="servizio-form">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipo servizio</Label>
              <Select value={tipo} onValueChange={setTipo} disabled={isEdit}>
                <SelectTrigger data-testid="servizio-tipo-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SERVIZIO_TIPI.filter((t) => !defaultTipo || t.section === SERVIZIO_TIPI.find((x) => x.id === defaultTipo)?.section)
                    .map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Negozio</Label>
              <Select value={form.venditore_id || ""} onValueChange={(v) => set("venditore_id", v)}>
                <SelectTrigger data-testid="servizio-venditore-select"><SelectValue placeholder="Seleziona negozio" /></SelectTrigger>
                <SelectContent>
                  {meta.stores.map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {!isEdit && (
            <div className="space-y-2 rounded-xl border border-slate-200 p-4" data-testid="servizio-client-picker">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cliente *</Label>
              {clientId ? (
                <div className="flex items-center justify-between rounded-lg bg-sky-50 px-3 py-2">
                  <span className="text-sm font-medium text-sky-800" data-testid="servizio-client-selected">{clientLabel}</span>
                  <Button type="button" variant="ghost" size="sm" onClick={() => { setClientId(""); setClientLabel(""); }} data-testid="servizio-client-clear">Cambia</Button>
                </div>
              ) : newClient ? (
                <div className="grid grid-cols-2 gap-3">
                  <Input placeholder="Nome *" value={newClient.nome} onChange={(e) => setNewClient({ ...newClient, nome: e.target.value })} data-testid="servizio-newclient-nome" />
                  <Input placeholder="Cognome *" value={newClient.cognome} onChange={(e) => setNewClient({ ...newClient, cognome: e.target.value })} data-testid="servizio-newclient-cognome" />
                  <Input placeholder="Telefono *" value={newClient.telefono} onChange={(e) => setNewClient({ ...newClient, telefono: e.target.value })} data-testid="servizio-newclient-telefono" />
                  <Input placeholder="Email" value={newClient.email} onChange={(e) => setNewClient({ ...newClient, email: e.target.value })} data-testid="servizio-newclient-email" />
                  <Button type="button" variant="ghost" size="sm" className="col-span-2" onClick={() => setNewClient(null)} data-testid="servizio-newclient-cancel">
                    ← Torna alla ricerca cliente esistente
                  </Button>
                </div>
              ) : (
                <>
                  <Input placeholder="Cerca cliente per nome, telefono, CF..." value={search}
                         onChange={(e) => setSearch(e.target.value)} data-testid="servizio-client-search" />
                  {results.length > 0 && (
                    <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                      {results.map((c) => (
                        <button type="button" key={c.id}
                                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                                onClick={() => { setClientId(c.id); setClientLabel(`${c.cognome} ${c.nome}`); setResults([]); }}
                                data-testid={`servizio-client-option-${c.id}`}>
                          <span className="font-medium">{c.cognome} {c.nome}</span>
                          <span className="text-xs text-slate-500">{c.telefono}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  <Button type="button" variant="outline" size="sm" onClick={() => setNewClient({ ...EMPTY_NEW_CLIENT })} data-testid="servizio-newclient-open">
                    + Crea nuovo cliente
                  </Button>
                </>
              )}
            </div>
          )}

          {isRip && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Dispositivo *</Label>
                <Input required placeholder="es. iPhone 13" value={form.dispositivo || ""} onChange={(e) => set("dispositivo", e.target.value)} data-testid="servizio-dispositivo" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Stato</Label>
                <Select value={form.stato || "ingresso"} onValueChange={(v) => set("stato", v)}>
                  <SelectTrigger data-testid="servizio-stato-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    {RIP_STATI.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-full grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3" data-testid="servizio-date-box">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data ingresso</Label>
                  <Input type="date" value={form.data_ingresso || ""} onChange={(e) => set("data_ingresso", e.target.value)} data-testid="servizio-data-ingresso" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data lavorazione</Label>
                  <Input type="date" value={form.data_lavorazione || ""} onChange={(e) => set("data_lavorazione", e.target.value)} data-testid="servizio-data-lavorazione" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data uscita</Label>
                  <Input type="date" value={form.data_uscita || ""} onChange={(e) => set("data_uscita", e.target.value)} data-testid="servizio-data-uscita" />
                </div>
              </div>
              <div className="col-span-full space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Problema</Label>
                <Textarea rows={2} value={form.problema || ""} onChange={(e) => set("problema", e.target.value)} data-testid="servizio-problema" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Codice sblocco dispositivo</Label>
                <Select value={form.codice_sblocco_tipo || "nessuno"} onValueChange={(v) => set("codice_sblocco_tipo", v)}>
                  <SelectTrigger data-testid="servizio-sblocco-tipo"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SBLOCCO_TIPI.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {form.codice_sblocco_tipo && form.codice_sblocco_tipo !== "nessuno" && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {form.codice_sblocco_tipo === "simbolo" ? "Sequenza (es. 1-5-9-6)" : form.codice_sblocco_tipo === "pin" ? "PIN" : "Password"}
                  </Label>
                  <Input value={form.codice_sblocco || ""} onChange={(e) => set("codice_sblocco", e.target.value)} placeholder={isEdit && servizio?.has_codice_sblocco ? "•••• salvato cifrato (lascia vuoto per non cambiare)" : ""} data-testid="servizio-sblocco" />
                </div>
              )}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Email account dispositivo</Label>
                <Input placeholder="es. account Google / Apple ID" value={form.account_email || ""} onChange={(e) => set("account_email", e.target.value)} data-testid="servizio-account-email" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Password account dispositivo</Label>
                <Input value={form.account_password || ""} onChange={(e) => set("account_password", e.target.value)} placeholder={isEdit && servizio?.has_account_password ? "•••• salvata cifrata (lascia vuoto per non cambiare)" : ""} data-testid="servizio-account-password" />
              </div>
              <div className="col-span-full space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Operazioni svolte</Label>
                <Textarea rows={2} placeholder="es. Sostituito display, testato touch e batteria..." value={form.operazioni || ""} onChange={(e) => set("operazioni", e.target.value)} data-testid="servizio-operazioni" />
              </div>
              <div className="flex items-center gap-3 pt-5">
                <Switch checked={Boolean(form.con_ricambio)} onCheckedChange={(v) => set("con_ricambio", v)} data-testid="servizio-ricambio-switch" />
                <Label className="text-sm">Richiede ricambio da ordinare</Label>
              </div>
              {form.con_ricambio && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Ricambio acquistato da</Label>
                  <Select value={form.ricambio_acquistato_da || "auto"} onValueChange={(v) => set("ricambio_acquistato_da", v === "auto" ? "" : v)}>
                    <SelectTrigger data-testid="servizio-ricambio-acquistato"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Automatico (dal magazzino di provenienza)</SelectItem>
                      <SelectItem value="laboratorio">Laboratorio / magazzino Morbegno (addebitato al negozio)</SelectItem>
                      <SelectItem value="negozio">Negozio (già pagato dal negozio)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              {!isEdit ? (
                <div className="space-y-1.5" data-testid="servizio-ricambio-mag-box">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Ricambio dal magazzino</Label>
                  {ricambioMag ? (
                    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${ricambioMag.disponibile ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`} data-testid="servizio-ricambio-mag-selezionato">
                      <span className="flex-1">{ricambioMag.nome} · {ricambioMag.store_name}{!ricambioMag.disponibile && " · esaurito: verrà messo in ordine"}</span>
                      <input type="number" min="1" value={ricambioMag.quantita} onChange={(e) => setRicambioMag({ ...ricambioMag, quantita: Math.max(parseInt(e.target.value) || 1, 1) })} className="w-14 rounded border border-slate-300 px-1.5 py-0.5 text-xs" data-testid="servizio-ricambio-mag-qta" />
                      <button type="button" className="text-xs text-rose-700 hover:underline" onClick={() => setRicambioMag(null)} data-testid="servizio-ricambio-mag-rimuovi">Rimuovi</button>
                    </div>
                  ) : (
                    <div className="relative">
                      <Input placeholder="Cerca ricambio in magazzino (es. display iphone 12)" value={magSearch} onChange={(e) => setMagSearch(e.target.value)} className="h-9 text-sm" data-testid="servizio-ricambio-mag-search" />
                      {magResults.length > 0 && (
                        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg" data-testid="servizio-ricambio-mag-risultati">
                          {magResults.map((g) => g.stores.map((s) => (
                            <li key={s.item_id}>
                              <button type="button" onClick={() => pickRicambio(g, s)} className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-slate-50" data-testid={`servizio-ricambio-mag-pick-${s.item_id}`}>
                                <span>{g.nome}</span>
                                <span className={`text-xs ${s.quantita > 0 ? "text-emerald-700" : "text-rose-600"}`}>{s.store_name} · {s.quantita > 0 ? `${s.quantita} pz` : "esaurito"}{s.prezzo_acquisto != null ? ` · ${s.prezzo_acquisto} €` : ""}</span>
                              </button>
                            </li>
                          )))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              ) : <div />}
              {form.con_ricambio ? (
                <>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipo ricambio</Label>
                  <Select value={form.tipo_ricambio || "altro"} onValueChange={(v) => set("tipo_ricambio", v)}>
                    <SelectTrigger data-testid="servizio-tipo-ricambio"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="display">Display OLED / originale</SelectItem>
                      <SelectItem value="display_compatibile">Display compatibile (CPY)</SelectItem>
                      <SelectItem value="batteria">Batteria</SelectItem>
                      <SelectItem value="connettore">Connettore di ricarica / flat</SelectItem>
                      <SelectItem value="fotocamera">Fotocamera / altoparlante / sensori</SelectItem>
                      <SelectItem value="vetro_camera">Vetrino fotocamera</SelectItem>
                      <SelectItem value="vetro_posteriore">Vetro posteriore</SelectItem>
                      <SelectItem value="altro">Altro componente</SelectItem>
                      <SelectItem value="vetro_temperato">Vetro temperato (10 €)</SelectItem>
                      <SelectItem value="pellicola">Pellicola (20 €)</SelectItem>
                      <SelectItem value="cover">Cover (15 €)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Costo {form.tipo_ricambio === "batteria" ? "batteria" : "componente"} € (netto)</Label>
                  <Input type="number" step="0.01" value={form.costo_componente ?? ""} onChange={(e) => set("costo_componente", e.target.value)} data-testid="servizio-costo" />
                  <div className="relative">
                    <Input value={listinoQ} onChange={(e) => setListinoQ(e.target.value)} placeholder="Cerca nel listino fornitore (es. display iphone 13)" className="h-8 text-xs" data-testid="servizio-listino-search" />
                    {listino.length > 0 && (
                      <ul className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg" data-testid="servizio-listino-results">
                        {listino.map((l) => (
                          <li key={l.id}>
                            <button type="button" onClick={() => { set("costo_componente", String(l.prezzo_netto)); if (l.tipologia) set("tipo_ricambio", l.tipologia); setListinoQ(""); setListino([]); }}
                                    className="flex w-full items-center justify-between px-3 py-1.5 text-left text-xs hover:bg-slate-50" data-testid={`servizio-listino-item-${l.id}`}>
                              <span className="truncate">{l.codice ? <span className="font-mono text-slate-400">{l.codice} </span> : null}{l.modello ? <span className="font-semibold">{l.modello} · </span> : null}{l.descrizione}</span>
                              <span className="ml-2 shrink-0 font-semibold">€ {l.prezzo_netto.toFixed(2)}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                </>
              ) : null}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Minuti di lavoro {form.con_ricambio && form.tipo_ricambio === "batteria" ? "(reali, senza minimo)" : "(min. 30)"}</Label>
                <Input type="number" value={form.minuti_lavoro ?? ""} onChange={(e) => set("minuti_lavoro", e.target.value)} data-testid="servizio-minuti" />
              </div>
              <div className="col-span-full rounded-lg bg-emerald-50 px-4 py-3" data-testid="servizio-prezzo-preview">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Prezzo consigliato (IVA inclusa)</p>
                <p className="font-heading text-2xl font-bold text-emerald-800">€ {prezzo != null ? prezzo.toFixed(2) : "-"}</p>
                <p className="text-xs text-emerald-700" data-testid="servizio-prezzo-formula">
                  {regolaAttiva
                    ? `Regola "${regolaAttiva.label}": ${form.con_ricambio ? `(costo ricambio + 2,50€ sped.) +${regolaAttiva.ricarico_pct}% + ` : ""}manodopera ${regolaAttiva.manodopera}€ + IVA 22%, arrotondato ai 5€${regolaAttiva.prezzo_min || regolaAttiva.prezzo_max ? ` (fascia ${regolaAttiva.prezzo_min}–${regolaAttiva.prezzo_max}€)` : ""}`
                    : form.con_ricambio
                    ? (form.tipo_ricambio === "batteria"
                      ? "costo batteria + 2€ trasporto + minuti reali × 0,22775€ + 20€ margine + IVA 22%"
                      : "costo componente + 2€ trasporto + minuti × 0,22775€ + 60€ margine + IVA 22%")
                    : "30€ base + minuti × 0,22775€ + IVA 22%"}
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold uppercase tracking-wide text-slate-600">Prezzo finale al cliente € (vuoto = consigliato)</Label>
                    <Input type="number" step="0.01" value={form.prezzo_finale ?? ""} onChange={(e) => set("prezzo_finale", e.target.value)} placeholder={prezzo != null ? prezzo.toFixed(2) : ""} data-testid="servizio-prezzo-finale" />
                  </div>
                  <div className="rounded-lg bg-white/70 px-3 py-2" data-testid="servizio-margine-preview">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Margine reale (netto IVA)</p>
                    {(() => {
                      const finale = form.prezzo_finale !== "" && form.prezzo_finale != null ? parseFloat(form.prezzo_finale) : prezzo;
                      if (finale == null || isNaN(finale)) return <p className="text-slate-400">-</p>;
                      const minRaw = parseInt(form.minuti_lavoro) || 0;
                      const bat = form.con_ricambio && form.tipo_ricambio === "batteria";
                      const costi = (form.con_ricambio ? (parseFloat(form.costo_componente) || 0) + 2.5 : 0) + (bat ? minRaw : Math.max(minRaw, 30)) * 0.22775;
                      const m = finale / 1.22 - costi;
                      return <p className={`font-heading text-xl font-bold ${m < 0 ? "text-rose-700" : m < 15 ? "text-amber-700" : "text-emerald-800"}`}>€ {m.toFixed(2)}</p>;
                    })()}
                  </div>
                </div>
              </div>
            </div>
          )}

          {isTel && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Operatore *</Label>
                <Select value={form.operatore_tel || ""} onValueChange={(v) => set("operatore_tel", v)}>
                  <SelectTrigger data-testid="servizio-operatore-select"><SelectValue placeholder="Seleziona operatore" /></SelectTrigger>
                  <SelectContent>
                    {(TEL_OPERATORS[tipo] || TEL_OPERATORS.fisso).map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Numero</Label>
                <Input value={form.numero || ""} onChange={(e) => set("numero", e.target.value)} data-testid="servizio-numero" />
              </div>
              {tipo === "sim" && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipo attivazione *</Label>
                  <Select value={form.tipo_attivazione || ""} onValueChange={(v) => set("tipo_attivazione", v)}>
                    <SelectTrigger data-testid="servizio-tipo-attivazione"><SelectValue placeholder="Numero nuovo o MNP?" /></SelectTrigger>
                    <SelectContent>{SIM_ATTIVAZIONI.map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              )}
              {tipo === "sim" && form.tipo_attivazione === "mnp" && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Proviene da (operatore)</Label>
                  <Select value={form.provenienza_operatore || ""} onValueChange={(v) => set("provenienza_operatore", v)}>
                    <SelectTrigger data-testid="servizio-provenienza"><SelectValue placeholder="Operatore di provenienza" /></SelectTrigger>
                    <SelectContent>{SIM_PROVENIENZE.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              )}
              {tipo === "sim" && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prima ricarica € (da plafond)</Label>
                  <Input type="number" step="0.01" value={form.ricarica_iniziale ?? ""} onChange={(e) => set("ricarica_iniziale", e.target.value)} placeholder="es. 10 o 15" data-testid="servizio-ricarica" />
                </div>
              )}
              {tipo === "sim" && !isEdit && (
                <div className="space-y-1.5 sm:col-span-2" data-testid="servizio-sim-magazzino-box">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">SIM dal magazzino (scarico automatico)</Label>
                  {form.magazzino_item_id ? (
                    <div className="flex items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm" data-testid="servizio-sim-magazzino-selezionata">
                      <span className="flex-1">{magLabel}</span>
                      <button type="button" className="text-xs text-rose-700 hover:underline" onClick={() => { set("magazzino_item_id", ""); setMagLabel(""); }} data-testid="servizio-sim-magazzino-rimuovi">Rimuovi</button>
                    </div>
                  ) : (
                    <>
                      <Input placeholder={`Cerca SIM in magazzino (es. ${form.operatore_tel || "operatore"}, ICCID, barcode)…`} value={magSearch} onChange={(e) => setMagSearch(e.target.value)} data-testid="servizio-sim-magazzino-search" />
                      {magResults.length > 0 && (
                        <div className="space-y-1 rounded-md border border-slate-200 p-2">
                          {magResults.map((g) => g.stores.filter((s) => s.quantita > 0).map((s) => (
                            <button key={s.item_id} type="button" onClick={() => pickMag(g, s)} className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm hover:bg-slate-100" data-testid={`servizio-sim-magazzino-pick-${s.item_id}`}>
                              <span>{g.nome}</span><span className="text-xs text-slate-500">{s.store_name} · {s.quantita} pz</span>
                            </button>
                          )))}
                        </div>
                      )}
                      <p className="text-[11px] text-slate-500">Se la SIM non è a magazzino lascia vuoto: non verrà scaricato nulla.</p>
                    </>
                  )}
                </div>
              )}

              {tipo === "sim" && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Costo SIM €</Label>
                  <Input type="number" step="0.01" value={form.costo_sim ?? ""} onChange={(e) => set("costo_sim", e.target.value)} placeholder="es. 5" data-testid="servizio-costo-sim" />
                </div>
              )}
              {tipo === "sim" && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">ICCID</Label>
                  <Input value={form.iccid || ""} onChange={(e) => set("iccid", e.target.value)} data-testid="servizio-iccid" />
                </div>
              )}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data attivazione</Label>
                <Input type="date" value={form.data_attivazione || ""} onChange={(e) => set("data_attivazione", e.target.value)} data-testid="servizio-attivazione" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vincolo (mesi, 0-999)</Label>
                <Input type="number" min="0" max="999" value={form.vincolo_mesi ?? ""} onChange={(e) => set("vincolo_mesi", e.target.value)} data-testid="servizio-vincolo" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Importo €/mese</Label>
                <Input type="number" step="0.01" value={form.importo ?? ""} onChange={(e) => set("importo", e.target.value)} data-testid="servizio-importo" />
              </div>
              {(tipo === "internet" || tipo === "fisso") && (
                <div className="flex items-center gap-3 pt-5">
                  <Switch checked={Boolean(form.cliente_contattato)} onCheckedChange={(v) => set("cliente_contattato", v)} data-testid="servizio-contattato-switch" />
                  <Label className="text-sm">Cliente contattato</Label>
                </div>
              )}
              {isWT && !isSim && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Categoria prodotto (gara WindTre)</Label>
                  <Select value={form.categoria_prodotto || ""} onValueChange={(v) => set("categoria_prodotto", v)}>
                    <SelectTrigger data-testid="servizio-categoria-prodotto"><SelectValue placeholder="Seleziona" /></SelectTrigger>
                    <SelectContent>{WT_CATEGORIE_FISSO.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              )}
              {isWT && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Esito attivazione</Label>
                  <Select value={form.esito_attivazione || "riconosciuta"} onValueChange={(v) => set("esito_attivazione", v)}>
                    <SelectTrigger data-testid="servizio-esito-attivazione"><SelectValue /></SelectTrigger>
                    <SelectContent>{WT_ESITI.map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              )}
              {isWT && !isSim && (
                <div className="flex items-center gap-3 pt-5">
                  <Switch checked={Boolean(form.convergente)} onCheckedChange={(v) => set("convergente", v)} data-testid="servizio-convergente" />
                  <Label className="text-sm">Convergente (+30 €)</Label>
                </div>
              )}
              {isWT && isSim && (
                <div className="flex items-center gap-3 pt-5">
                  <Switch checked={Boolean(form.tied)} onCheckedChange={(v) => set("tied", v)} data-testid="servizio-tied" />
                  <Label className="text-sm">Tied (vincolata)</Label>
                </div>
              )}
            </div>
          )}

          {isShop && (
            <div className="space-y-3">
              {!isEdit && <VenditaOrdineBox form={form} set={set} />}
              {!isEdit && !form.da_ordinare && (
                <div className="space-y-1.5" data-testid="servizio-magazzino-box">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Articolo di magazzino (scarico automatico) *</Label>
                  {!form.magazzino_item_id && (
                    <label className="flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={!!form.non_a_magazzino} onChange={(e) => set("non_a_magazzino", e.target.checked)} data-testid="servizio-non-a-magazzino" /> Articolo non a magazzino (nessuno scarico)</label>
                  )}
                  {form.magazzino_item_id ? (
                    <div className="flex items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm" data-testid="servizio-magazzino-selezionato">
                      <span className="flex-1 text-emerald-900">{magLabel}</span>
                      <input type="number" min="1" value={form.quantita || 1} onChange={(e) => set("quantita", Math.max(parseInt(e.target.value) || 1, 1))} className="w-14 rounded border border-slate-300 px-1.5 py-0.5 text-xs" data-testid="servizio-magazzino-qta" />
                      <button type="button" className="text-xs text-rose-700 hover:underline" onClick={() => { set("magazzino_item_id", ""); setMagLabel(""); }} data-testid="servizio-magazzino-rimuovi">Rimuovi</button>
                    </div>
                  ) : (
                    <>
                      <Input placeholder="Cerca per nome, marca, barcode…" value={magSearch} onChange={(e) => setMagSearch(e.target.value)} data-testid="servizio-magazzino-search" />
                      {magResults.length > 0 && (
                        <div className="space-y-1 rounded-md border border-slate-200 p-2" data-testid="servizio-magazzino-risultati">
                          {magResults.map((g) => g.stores.filter((s) => s.quantita > 0).map((s) => (
                            <button key={s.item_id} type="button" onClick={() => pickMag(g, s)} className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm hover:bg-slate-100" data-testid={`servizio-magazzino-pick-${s.item_id}`}>
                              <span>{g.nome}</span><span className="text-xs text-slate-500">{s.store_name} · {s.quantita} pz{s.prezzo_vendita != null ? ` · ${s.prezzo_vendita} €` : ""}</span>
                            </button>
                          )))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prodotto *</Label>
                <Input required value={form.prodotto || ""} onChange={(e) => set("prodotto", e.target.value)} data-testid="servizio-prodotto" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Importo €</Label>
                <Input type="number" step="0.01" value={form.importo ?? ""} onChange={(e) => set("importo", e.target.value)} data-testid="servizio-importo" />
              </div>
            </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-3">
              <Switch checked={Boolean(form.pagato)} onCheckedChange={(v) => set("pagato", v)} data-testid="servizio-pagato-switch" />
              <Label className="text-sm">Pagato dal cliente</Label>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Note</Label>
            <Textarea rows={2} value={form.note || ""} onChange={(e) => set("note", e.target.value)} data-testid="servizio-note" />
          </div>
          <DocumentiPicker files={nuoviDoc} onChange={setNuoviDoc} testid="servizio-documenti" label="Allega documenti (salvati sul cliente e sul servizio)" />

          <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
            <Button type="button" variant="outline" onClick={onClose} data-testid="servizio-form-cancel">Annulla</Button>
            <Button type="submit" disabled={saving || (!isEdit && !clientId && !newClient)} className="bg-slate-900 hover:bg-slate-800" data-testid="servizio-form-submit">
              {saving ? "Salvataggio..." : isEdit ? "Salva modifiche" : "Inserisci servizio"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
