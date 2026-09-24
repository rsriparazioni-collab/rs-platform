import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { VENDITE_CATEGORIE, REGIMI_IVA, isCategoriaUsato } from "../lib/constants";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

const EMPTY = { store_id: "", client_id: "", cliente_nome: "", categoria: "telefono_nuovo", regime_iva: "iva22", articolo: "", marca: "", modello: "",
  imei: "", magazzino_item_id: "", quantita: 1, prezzo: "", costo: "", pagamento: "", numero_fattura: "", data_vendita: "", note: "" };

export default function VenditaForm({ open, onClose, vendita, meta, onSaved, presetClientId }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [clientLabel, setClientLabel] = useState("");
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [newClient, setNewClient] = useState(null);
  const [magSearch, setMagSearch] = useState("");
  const [magResults, setMagResults] = useState([]);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open) return;
    setSearch(""); setResults([]); setNewClient(null); setMagSearch(""); setMagResults([]);
    if (vendita) {
      setForm({ ...EMPTY, ...vendita, prezzo: vendita.prezzo ?? "", costo: vendita.costo ?? "", data_vendita: (vendita.data_vendita || "").slice(0, 10) });
      setClientLabel(vendita.client_name || "");
    } else {
      setForm({ ...EMPTY, store_id: meta.stores[0]?.id || "", data_vendita: new Date().toISOString().slice(0, 10), client_id: presetClientId || "" });
      setClientLabel("");
      if (presetClientId) {
        api.get(`/clients/${presetClientId}`).then((r) => { setClientLabel(`${r.data.cognome} ${r.data.nome}`); if (r.data.venditore_id) set("store_id", r.data.venditore_id); }).catch(() => {});
      }
    }
  }, [open, vendita, meta, presetClientId]);

  useEffect(() => {
    if (search.trim().length < 2 || form.client_id) { setResults([]); return undefined; }
    const t = setTimeout(() => api.get("/clients", { params: { q: search.trim() } }).then((r) => setResults(r.data.slice(0, 8))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [search, form.client_id]);

  useEffect(() => {
    if (magSearch.trim().length < 2 || form.magazzino_item_id) { setMagResults([]); return undefined; }
    const t = setTimeout(() => api.get("/magazzino", { params: { q: magSearch.trim() } }).then((r) => setMagResults(r.data.filter((m) => (m.quantita || 0) > 0).slice(0, 8))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [magSearch, form.magazzino_item_id]);

  const pickItem = (m) => {
    setForm((f) => ({ ...f, magazzino_item_id: m.id, articolo: m.nome, costo: m.prezzo_acquisto ?? "", prezzo: m.prezzo_vendita ?? f.prezzo,
      regime_iva: m.regime_iva || f.regime_iva, store_id: m.store_id || f.store_id,
      categoria: m.condizione === "usato" ? "telefono_usato" : m.condizione === "rigenerato" || m.categoria === "rigenerati" ? "telefono_rigenerato" : m.categoria === "accessori" ? "accessori" : f.categoria }));
    setMagSearch(m.nome); setMagResults([]);
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      let clientId = form.client_id;
      if (!clientId && newClient) {
        const c = await api.post("/clients", { nome: newClient.nome, cognome: newClient.cognome, telefono: newClient.telefono || "",
          codice_fiscale: newClient.codice_fiscale || "", venditore_id: form.store_id, tipo_bolletta: "luce", origine: "riparazione", lavorazione: "" });
        clientId = c.data.id;
      }
      const payload = { ...form, client_id: clientId, prezzo: Number(form.prezzo), costo: form.costo === "" ? null : Number(form.costo),
        quantita: Number(form.quantita) || 1, data_vendita: form.data_vendita ? new Date(form.data_vendita).toISOString() : null };
      if (vendita) await api.patch(`/vendite/${vendita.id}`, payload);
      else await api.post("/vendite", payload);
      toast.success(vendita ? "Vendita aggiornata" : "Vendita registrata");
      onSaved();
    } catch (err) {
      toast.error(apiError(err, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  const usato = isCategoriaUsato(form.categoria);
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto" data-testid="vendita-form-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl">{vendita ? "Modifica vendita" : "Nuova vendita"}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-5" data-testid="vendita-form">
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Cliente</p>
            {form.client_id ? (
              <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2 text-sm" data-testid="vendita-client-selected">
                <span className="font-medium text-emerald-800">{clientLabel || "Cliente selezionato"}</span>
                {!vendita && <Button type="button" size="sm" variant="ghost" onClick={() => { set("client_id", ""); setClientLabel(""); }} data-testid="vendita-client-change">Cambia</Button>}
              </div>
            ) : newClient ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="vendita-new-client">
                <Input required placeholder="Nome *" value={newClient.nome} onChange={(e) => setNewClient({ ...newClient, nome: e.target.value })} data-testid="vendita-new-nome" />
                <Input required placeholder="Cognome *" value={newClient.cognome} onChange={(e) => setNewClient({ ...newClient, cognome: e.target.value })} data-testid="vendita-new-cognome" />
                <Input placeholder="Telefono" value={newClient.telefono} onChange={(e) => setNewClient({ ...newClient, telefono: e.target.value })} data-testid="vendita-new-telefono" />
                <div className="flex gap-1">
                  <Input placeholder="Cod. fiscale" value={newClient.codice_fiscale} onChange={(e) => setNewClient({ ...newClient, codice_fiscale: e.target.value.toUpperCase() })} />
                  <Button type="button" size="sm" variant="ghost" onClick={() => setNewClient(null)}>✕</Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Input placeholder="Cerca cliente esistente (cognome, telefono, CF)..." value={search} onChange={(e) => setSearch(e.target.value)} data-testid="vendita-client-search" />
                  <Button type="button" variant="outline" onClick={() => setNewClient({ nome: "", cognome: "", telefono: "", codice_fiscale: "" })} data-testid="vendita-new-client-button">+ Nuovo cliente</Button>
                </div>
                {results.length > 0 && (
                  <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200">
                    {results.map((c) => (
                      <button type="button" key={c.id} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                              onClick={() => { set("client_id", c.id); setClientLabel(`${c.cognome} ${c.nome}`); setResults([]); }} data-testid={`vendita-client-option-${c.id}`}>
                        <span>{c.cognome} {c.nome}</span><span className="text-xs text-slate-500">{c.telefono}</span>
                      </button>
                    ))}
                  </div>
                )}
                <Input placeholder="oppure nome cliente libero (senza scheda)" value={form.cliente_nome} onChange={(e) => set("cliente_nome", e.target.value)} data-testid="vendita-cliente-nome" />
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 p-4 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Articolo</p>
            {!vendita && (
              <div className="relative">
                <Input placeholder="Prendi dal magazzino: cerca nome o barcode..." value={magSearch}
                       onChange={(e) => { setMagSearch(e.target.value); if (form.magazzino_item_id) set("magazzino_item_id", ""); }} data-testid="vendita-mag-search" />
                {magResults.length > 0 && (
                  <div className="absolute z-10 mt-1 max-h-44 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow">
                    {magResults.map((m) => (
                      <button type="button" key={m.id} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => pickItem(m)} data-testid={`vendita-mag-option-${m.id}`}>
                        <span>{m.nome}{m.barcode ? <span className="ml-2 font-mono text-[10px] text-slate-500">{m.barcode}</span> : null}</span>
                        <span className="text-xs text-slate-500">q.{m.quantita} · {m.prezzo_vendita != null ? `€ ${m.prezzo_vendita}` : ""}</span>
                      </button>
                    ))}
                  </div>
                )}
                {form.magazzino_item_id && <p className="mt-1 text-xs text-emerald-700">Collegato al magazzino: la giacenza verrà scalata</p>}
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <F l="Descrizione articolo *"><Input required value={form.articolo} onChange={(e) => set("articolo", e.target.value)} data-testid="vendita-articolo" /></F>
              <F l="Categoria">
                <Select value={form.categoria} onValueChange={(v) => set("categoria", v)}>
                  <SelectTrigger data-testid="vendita-categoria"><SelectValue /></SelectTrigger>
                  <SelectContent>{VENDITE_CATEGORIE.map((c) => <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>)}</SelectContent>
                </Select>
              </F>
              <F l={usato ? "Regime IVA *" : "Regime IVA"}>
                <Select value={usato ? form.regime_iva : "iva22"} onValueChange={(v) => set("regime_iva", v)} disabled={!usato}>
                  <SelectTrigger data-testid="vendita-regime-iva"><SelectValue /></SelectTrigger>
                  <SelectContent>{REGIMI_IVA.map((r) => <SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>)}</SelectContent>
                </Select>
              </F>
              <F l="Marca"><Input value={form.marca} onChange={(e) => set("marca", e.target.value)} /></F>
              <F l="Modello"><Input value={form.modello} onChange={(e) => set("modello", e.target.value)} /></F>
              <F l="IMEI / Serial"><Input value={form.imei} onChange={(e) => set("imei", e.target.value)} data-testid="vendita-imei" /></F>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <F l="Prezzo vendita € *"><Input required type="number" step="0.01" min="0" value={form.prezzo} onChange={(e) => set("prezzo", e.target.value)} data-testid="vendita-prezzo" /></F>
            <F l="Costo € (per margine)"><Input type="number" step="0.01" min="0" value={form.costo} onChange={(e) => set("costo", e.target.value)} data-testid="vendita-costo" /></F>
            <F l="Quantità"><Input type="number" min="1" value={form.quantita} onChange={(e) => set("quantita", e.target.value)} /></F>
            <F l="Data vendita"><Input type="date" value={form.data_vendita} onChange={(e) => set("data_vendita", e.target.value)} /></F>
            <F l="Negozio">
              <Select value={form.store_id} onValueChange={(v) => set("store_id", v)}>
                <SelectTrigger data-testid="vendita-store"><SelectValue placeholder="Negozio" /></SelectTrigger>
                <SelectContent>{meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}</SelectContent>
              </Select>
            </F>
            <F l="Pagamento">
              <Select value={form.pagamento || "none"} onValueChange={(v) => set("pagamento", v === "none" ? "" : v)}>
                <SelectTrigger data-testid="vendita-pagamento"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">-</SelectItem><SelectItem value="contanti">Contanti</SelectItem><SelectItem value="carta">Carta / POS</SelectItem>
                  <SelectItem value="bonifico">Bonifico</SelectItem><SelectItem value="finanziamento">Finanziamento</SelectItem>
                </SelectContent>
              </Select>
            </F>
            <F l="N° fattura / scontrino"><Input value={form.numero_fattura} onChange={(e) => set("numero_fattura", e.target.value)} data-testid="vendita-fattura" /></F>
          </div>
          <F l="Note"><Textarea rows={2} value={form.note} onChange={(e) => set("note", e.target.value)} /></F>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Annulla</Button>
            <Button type="submit" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="vendita-submit">{saving ? "Salvo..." : "Salva vendita"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function F({ l, children }) {
  return <div className="space-y-1.5"><Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{l}</Label>{children}</div>;
}
