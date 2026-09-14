import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Paperclip, Pencil, Trash2, Upload, Wallet, ShieldCheck, Camera, Printer, Package, Recycle, FileDown, Ban, Lock } from "lucide-react";
import RitiroDaRiparazione from "./RitiroDaRiparazione";
import WhatsAppLog from "./WhatsAppLog";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import PortaleBox from "./PortaleBox";
import { ripStatoLabel, ripStatoBadge, servizioTipoLabel, fmtDate, RIP_STATI, magazzinoCategoriaLabel } from "../lib/constants";
import { Button } from "./ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

function PrezzoBreakdown({ s }) {
  const costi = s.costi || { componente: 0, lavoro: 0, totale: 0 };
  const finale = s.prezzo_finale ?? s.prezzo_consigliato ?? 0;
  const margine = s.margine_reale ?? Math.round((finale / 1.22 - costi.totale) * 100) / 100;
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4" data-testid="servizio-prezzo-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-500">{s.prezzo_finale != null ? "Prezzo finale" : "Prezzo consigliato"}</p>
          <p className="font-heading text-3xl font-bold text-emerald-800" data-testid="servizio-prezzo-finale">€ {Number(finale).toFixed(2)}</p>
          {s.prezzo_finale != null && <p className="text-xs text-slate-500">consigliato € {(s.prezzo_consigliato ?? 0).toFixed(2)}</p>}
        </div>
        <div className="text-right">
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-500">Margine reale</p>
          <p className={`font-heading text-2xl font-bold ${margine < 0 ? "text-rose-700" : margine < 15 ? "text-amber-700" : "text-emerald-800"}`} data-testid="servizio-margine">€ {margine.toFixed(2)}</p>
          <p className="text-xs text-slate-500">netto IVA, dopo costi</p>
        </div>
      </div>
      <div className="mt-2 space-y-0.5 text-xs text-slate-600">
        {s.con_ricambio && <p>{s.tipo_ricambio === "batteria" ? "Batteria" : "Componente"} + trasporto: € {costi.componente.toFixed(2)}</p>}
        <p>Lavoro: € {costi.lavoro.toFixed(2)} ({s.minuti_lavoro || 0} min × 0,22775€)</p>
        <p>Imponibile: € {(Number(finale) / 1.22).toFixed(2)} · IVA 22% inclusa</p>
      </div>
    </div>
  );
}

export default function ServizioDetail({ servizio, onClose, onEdit, onChanged, isAdmin }) {
  const [detail, setDetail] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [waLoading, setWaLoading] = useState(false);
  const [ricercaRic, setRicercaRic] = useState("");
  const [risultatiRic, setRisultatiRic] = useState([]);
  const [compatibili, setCompatibili] = useState([]);
  const [ricQty, setRicQty] = useState(1);
  const [ricPrezzo, setRicPrezzo] = useState("");
  const [ritiroOpen, setRitiroOpen] = useState(false);
  const [segreti, setSegreti] = useState(null);

  const mostraSegreti = async () => {
    try { setSegreti((await api.get(`/servizi/${detail.id}/segreti`)).data); }
    catch (e) { toast.error(apiError(e)); }
  };

  const refresh = useCallback(async () => {
    if (!servizio) return;
    try {
      const res = await api.get(`/servizi/${servizio.id}`);
      setDetail(res.data);
      const att = await api.get(`/servizi/${servizio.id}/attachments`);
      setAttachments(att.data);
    } catch (e) {
      toast.error(apiError(e, "Impossibile caricare il servizio"));
    }
  }, [servizio]);

  useEffect(() => {
    setDetail(null);
    setAttachments([]);
    if (servizio) refresh();
  }, [servizio, refresh]);

  const downloadBlob = async (url, filename) => {
    try {
      const res = await api.get(url, { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(res.data);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      toast.error(apiError(e, "Download fallito"));
    }
  };

  const uploadPhoto = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !detail) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/servizi/${detail.id}/attachments`, fd);
      toast.success("Foto/documento caricato");
      refresh();
    } catch (err) {
      toast.error(apiError(err, "Upload fallito"));
    }
  };

  const deleteAttachment = async (att) => {
    try {
      await api.delete(`/attachments/${att.id}`);
      toast.success("Allegato eliminato");
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  useEffect(() => {
    if (detail?.tipo === "riparazione" && detail?.dispositivo) {
      const q = detail.dispositivo.split(/\s+/).slice(0, 2).join(" ");
      if (q.length >= 3) {
        api.get("/magazzino/disponibilita", { params: { q } })
          .then((r) => setCompatibili(r.data))
          .catch(() => {});
      }
    }
  }, [detail?.id, detail?.tipo, detail?.dispositivo]);

  useEffect(() => {
    if (ricercaRic.trim().length < 2) {
      setRisultatiRic([]);
      return;
    }
    const t = setTimeout(() => {
      api.get("/magazzino/disponibilita", { params: { q: ricercaRic.trim() } })
        .then((r) => setRisultatiRic(r.data))
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [ricercaRic]);

  const usaRicambio = async (storeEntry, categoria) => {
    if (!detail) return;
    try {
      const payload = { magazzino_id: storeEntry.item_id, quantita: ricQty };
      if (categoria === "rigenerati" && ricPrezzo !== "") {
        payload.prezzo_manuale = parseFloat(ricPrezzo);
      }
      await api.post(`/servizi/${detail.id}/ricambi`, payload);
      toast.success("Ricambio assegnato e scalato dal magazzino");
      setRicQty(1);
      setRicPrezzo("");
      setRicercaRic("");
      setRisultatiRic([]);
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const removeRicambio = async (idx) => {
    try {
      await api.delete(`/servizi/${detail.id}/ricambi/${idx}`);
      toast.success("Ricambio rimosso, giacenza ripristinata");
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const changeStato = async (stato) => {
    try {
      await api.patch(`/servizi/${detail.id}`, { client_id: detail.client_id, tipo: detail.tipo, stato });
      toast.success(stato === "pronto" && !detail.pronto_msg_sent_at
        ? "Stato aggiornato: Pronto. Avviso WhatsApp al cliente in invio..."
        : stato === "consegnato" && !detail.client_contacts?.no_recensioni
          ? "Dispositivo consegnato. Richiesta recensione in partenza tra 2 minuti."
          : `Stato aggiornato: ${ripStatoLabel(stato)}`);
      setTimeout(refresh, 2500);
      refresh();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const sendPronto = async () => {
    setWaLoading(true);
    try {
      await api.post(`/servizi/${detail.id}/whatsapp/pronto`);
      toast.success("Avviso 'pronto per il ritiro' inviato al cliente");
      refresh();
    } catch (e) {
      toast.error(apiError(e, "Invio fallito"));
    } finally {
      setWaLoading(false);
    }
  };

  const markPaid = async () => {
    try {
      await api.post(`/servizi/${detail.id}/mark-paid`);
      toast.success("Pagamento registrato");
      refresh();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const sendPrivacy = async () => {
    setWaLoading(true);
    try {
      const res = await api.post(`/servizi/${detail.id}/whatsapp/privacy`);
      if (res.data.privacy_registered) toast.success("Modulo privacy compilato e inviato in automatico sul sito");
      if (res.data.registration_error) toast.warning(`Registrazione sito: ${res.data.registration_error}`);
      if (res.data.wa_error) toast.warning(`WhatsApp non inviato: ${res.data.wa_error}`);
      else toast.success(res.data.review_queued
        ? "Messaggio privacy inviato. Recensione del negozio in partenza tra 2 minuti."
        : detail.tipo === "riparazione"
          ? "Messaggio privacy inviato. La recensione partirà alla consegna del dispositivo."
          : "Messaggio privacy inviato (nessun link recensioni configurato per questo negozio)");
      refresh();
    } catch (e) {
      toast.error(apiError(e, "Invio fallito"));
    } finally {
      setWaLoading(false);
    }
  };

  const toggleBlacklist = async () => {
    const next = !detail.client_contacts?.no_recensioni;
    if (next && !window.confirm("Bloccare l'invio delle richieste di recensione a questo cliente?")) return;
    try {
      await api.post(`/clients/${detail.client_id}/blacklist-recensioni`, { no_recensioni: next });
      toast.success(next ? "Cliente in blacklist: nessuna recensione verrà inviata" : "Blacklist rimossa");
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const remove = async () => {
    if (!window.confirm("Eliminare questo servizio?")) return;
    try {
      await api.delete(`/servizi/${detail.id}`);
      toast.success("Servizio eliminato");
      onClose();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const isRip = detail?.tipo === "riparazione";

  return (
    <Sheet open={Boolean(servizio)} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl" data-testid="servizio-detail-sheet">
        {!detail && <SheetHeader><SheetTitle className="sr-only">Dettaglio servizio</SheetTitle></SheetHeader>}
        {detail && (
          <>
            <SheetHeader>
              <SheetTitle className="font-heading text-xl">
                {detail.client_name} · {servizioTipoLabel(detail.tipo)}
              </SheetTitle>
            </SheetHeader>
            <div className="mt-6 space-y-6">
              {isRip && !detail.ritiro_id && (
                <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 px-4 py-3" data-testid="servizio-ritirato-box">
                  <div>
                    <p className="text-sm font-semibold text-emerald-900">Il cliente lascia il telefono?</p>
                    <p className="text-xs text-emerald-700">Crea la bolla di ritiro con documenti e carica il dispositivo tra i rigenerati.</p>
                  </div>
                  <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => setRitiroOpen(true)} data-testid="servizio-ritirato-button">
                    <Recycle className="mr-2 h-4 w-4" /> Ritirato
                  </Button>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {isRip && detail.numero_riparazione && (
                  <span className="status-badge bg-sky-500/15 text-sky-700 border-sky-300" data-testid="servizio-numero-badge">N° {detail.numero_riparazione}</span>
                )}
                {isRip && <span className={`status-badge ${ripStatoBadge(detail.stato)}`} data-testid="servizio-stato-badge">{ripStatoLabel(detail.stato)}</span>}
                {isRip && detail.ritiro_numero && (
                  <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300" data-testid="servizio-ritiro-badge">
                    <Recycle className="h-3 w-3" /> Ritiro {detail.ritiro_numero}
                  </span>
                )}
                {isRip && detail.pronto_msg_sent_at && (
                  <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300" data-testid="servizio-pronto-sent-badge">
                    <MessageCircle className="h-3 w-3" /> Cliente avvisato {fmtDate(detail.pronto_msg_sent_at)}
                  </span>
                )}
                {isRip && !detail.pronto_msg_sent_at && detail.pronto_msg_error && (
                  <span className="status-badge bg-amber-500/15 text-amber-700 border-amber-300" title={detail.pronto_msg_error} data-testid="servizio-pronto-error-badge">
                    Avviso "pronto" non inviato
                  </span>
                )}
                {isRip && detail.review_msg_sent_at && (
                  <span className="status-badge bg-sky-500/15 text-sky-700 border-sky-300" data-testid="servizio-review-sent-badge">Recensione inviata {fmtDate(detail.review_msg_sent_at)}</span>
                )}
                {isRip && !detail.review_msg_sent_at && detail.review_queued_at && (
                  <span className="status-badge bg-sky-500/15 text-sky-700 border-sky-300" data-testid="servizio-review-queued-badge">Recensione in invio</span>
                )}
                {detail.client_contacts?.no_recensioni && (
                  <span className="status-badge bg-slate-500/15 text-slate-700 border-slate-300" data-testid="servizio-blacklist-badge">
                    <Ban className="h-3 w-3" /> No recensioni
                  </span>
                )}
                {detail.pagato
                  ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">Pagato</span>
                  : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300">Non pagato</span>}
                {detail.privacy_firmata && (
                  <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">
                    <ShieldCheck className="h-3 w-3" /> Privacy firmata
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div><p className="text-xs text-slate-500">Telefono cliente</p><p className="font-medium">{detail.client_contacts?.telefono || "-"}</p></div>
                <div><p className="text-xs text-slate-500">Email cliente</p><p className="font-medium">{detail.client_contacts?.email || "-"}</p></div>
                {isRip && (
                  <>
                    <div><p className="text-xs text-slate-500">Dispositivo</p><p className="font-medium">{detail.dispositivo || "-"}</p></div>
                    <div><p className="text-xs text-slate-500">Ricambio</p><p className="font-medium">{detail.con_ricambio ? (detail.tipo_ricambio === "batteria" ? "Batteria" : "Da ordinare") : "Non necessario"}</p></div>
                    <div className="col-span-2 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3" data-testid="servizio-date-info">
                      <div><p className="text-xs text-slate-500">Ingresso</p><p className="font-medium" data-testid="servizio-data-ingresso-info">{fmtDate(detail.data_ingresso)}</p></div>
                      <div><p className="text-xs text-slate-500">Lavorazione</p><p className="font-medium" data-testid="servizio-data-lavorazione-info">{fmtDate(detail.data_lavorazione)}</p></div>
                      <div><p className="text-xs text-slate-500">Uscita</p><p className="font-medium" data-testid="servizio-data-uscita-info">{fmtDate(detail.data_uscita)}</p></div>
                    </div>
                    {detail.problema && <div className="col-span-2"><p className="text-xs text-slate-500">Problema</p><p className="font-medium whitespace-pre-wrap">{detail.problema}</p></div>}
                    {detail.codice_sblocco_tipo && detail.codice_sblocco_tipo !== "nessuno" && (
                      <div><p className="text-xs text-slate-500">Codice sblocco</p>
                        <p className="font-medium" data-testid="servizio-sblocco-info">{detail.codice_sblocco_tipo}: {segreti ? (segreti.codice_sblocco || "-") : (detail.has_codice_sblocco ? "••••" : "-")}</p></div>
                    )}
                    {detail.account_email && (
                      <div><p className="text-xs text-slate-500">Account dispositivo</p>
                        <p className="font-medium" data-testid="servizio-account-info">{detail.account_email}{segreti ? (segreti.account_password ? ` · ${segreti.account_password}` : "") : (detail.has_account_password ? " · ••••" : "")}</p></div>
                    )}
                    {(detail.has_codice_sblocco || detail.has_account_password) && !segreti && (
                      <div className="col-span-2">
                        <Button size="sm" variant="outline" onClick={mostraSegreti} className="gap-1" data-testid="servizio-mostra-codici">
                          <Lock className="h-3.5 w-3.5" /> Mostra codici (accesso registrato)
                        </Button>
                      </div>
                    )}
                    {detail.segreti_cancellati_at && (
                      <p className="col-span-2 text-xs text-slate-500" data-testid="servizio-segreti-cancellati">Codici dispositivo cancellati alla consegna ({fmtDate(detail.segreti_cancellati_at)}) per tutela privacy.</p>
                    )}
                    {detail.operazioni && <div className="col-span-2"><p className="text-xs text-slate-500">Operazioni svolte</p><p className="font-medium whitespace-pre-wrap" data-testid="servizio-operazioni-info">{detail.operazioni}</p></div>}
                  </>
                )}
                {["sim", "internet", "fisso"].includes(detail.tipo) && (
                  <>
                    <div><p className="text-xs text-slate-500">Operatore</p><p className="font-medium">{detail.operatore_tel || "-"}</p></div>
                    <div><p className="text-xs text-slate-500">Numero</p><p className="font-medium">{detail.numero || "-"}</p></div>
                    {detail.iccid && <div><p className="text-xs text-slate-500">ICCID</p><p className="font-medium">{detail.iccid}</p></div>}
                    <div><p className="text-xs text-slate-500">Attivazione</p><p className="font-medium">{fmtDate(detail.data_attivazione)}</p></div>
                    {detail.scadenza_vincolo && (
                      <div>
                        <p className="text-xs text-slate-500">Scadenza vincolo ({detail.vincolo_mesi} mesi)</p>
                        <p className={`font-semibold ${detail.giorni_alla_scadenza <= 60 ? "text-amber-700" : ""}`} data-testid="servizio-scadenza-vincolo">
                          {fmtDate(detail.scadenza_vincolo)} ({detail.giorni_alla_scadenza} gg)
                        </p>
                      </div>
                    )}
                    {detail.importo != null && <div><p className="text-xs text-slate-500">Importo</p><p className="font-medium">€ {detail.importo}/mese</p></div>}
                    {(detail.tipo === "internet" || detail.tipo === "fisso") && (
                      <div><p className="text-xs text-slate-500">Cliente contattato</p>
                        <p className={`font-medium ${detail.cliente_contattato ? "text-emerald-700" : "text-slate-400"}`} data-testid="servizio-contattato-info">
                          {detail.cliente_contattato ? "Sì" : "No"}
                        </p>
                      </div>
                    )}
                  </>
                )}
                {["accessori", "vendita"].includes(detail.tipo) && (
                  <>
                    <div><p className="text-xs text-slate-500">Prodotto</p><p className="font-medium">{detail.prodotto || "-"}</p></div>
                    <div><p className="text-xs text-slate-500">Importo</p><p className="font-medium">€ {detail.importo ?? "-"}</p></div>
                  </>
                )}
              </div>

              {isRip && (
                <>
                  <div className="rounded-xl border border-slate-200 p-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Avanzamento lavorazione</p>
                    <Select value={detail.stato} onValueChange={changeStato}>
                      <SelectTrigger data-testid="servizio-stato-change"><SelectValue /></SelectTrigger>
                      <SelectContent className="max-h-64">
                        {RIP_STATI.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <PrezzoBreakdown s={detail} />
                  <div className="rounded-xl border border-slate-200 p-4" data-testid="servizio-ricambi-card">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
                      <Package className="mr-1 inline h-3.5 w-3.5" /> Ricambi dal magazzino
                    </p>
                    <div className="space-y-1.5" data-testid="servizio-ricambi-list">
                      {(detail.ricambi_usati || []).map((u, idx) => (
                        <div key={`${u.item_id}-${u.at || idx}`} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                          <span>{u.nome} <span className="text-xs text-slate-500">x{u.quantita}</span></span>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeRicambio(idx)} data-testid={`servizio-ricambio-del-${idx}`}>
                            <Trash2 className="h-3.5 w-3.5 text-rose-500" />
                          </Button>
                        </div>
                      ))}
                      {(detail.ricambi_usati || []).length === 0 && <p className="text-xs text-slate-400">Nessun ricambio assegnato</p>}
                    </div>
                    {compatibili.length > 0 && (
                      <div className="mb-2 rounded-lg border border-sky-200 bg-sky-50 p-3" data-testid="ricambi-compatibili">
                        <p className="text-xs font-semibold uppercase tracking-wide text-sky-800">Compatibili con {detail.dispositivo}</p>
                        {compatibili.map((g) => (
                          <div key={`${g.nome}|${g.categoria}`} className="mt-1.5 flex flex-wrap items-center gap-1">
                            <span className="text-xs font-medium text-slate-800">{g.nome}</span>
                            {g.stores.map((s) => (
                              <span key={s.item_id} className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${s.store_id === detail.venditore_id && s.quantita > 0 ? "bg-emerald-100 text-emerald-800" : s.quantita > 0 ? "bg-slate-200 text-slate-600" : "bg-slate-100 text-slate-400"}`}>
                                {s.store_name}: {s.quantita}
                              </span>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                    <input placeholder="Cerca ricambio in tutti i magazzini (es. batteria iPhone 12)..." value={ricercaRic}
                           onChange={(e) => setRicercaRic(e.target.value)}
                           className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm" data-testid="servizio-ricambio-search" />
                    {risultatiRic.length > 0 && (
                      <div className="mt-2 space-y-2" data-testid="servizio-ricambi-risultati">
                        {risultatiRic.map((g, gi) => {
                          const own = g.stores.find((s) => s.store_id === detail.venditore_id);
                          const others = g.stores.filter((s) => s.store_id !== detail.venditore_id && s.quantita > 0);
                          return (
                            <div key={`${g.nome}|${g.categoria}`} className="rounded-lg border border-slate-200 p-2.5" data-testid={`servizio-ricambio-risultato-${gi}`}>
                              <div className="flex flex-wrap items-center gap-1">
                                <span className="text-sm font-medium text-slate-900">{g.nome}</span>
                                <span className="text-xs text-slate-400">({magazzinoCategoriaLabel(g.categoria)})</span>
                                {g.stores.map((s) => (
                                  <span key={s.item_id} className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${s.store_id === detail.venditore_id && s.quantita > 0 ? "bg-emerald-100 text-emerald-800" : s.quantita > 0 ? "bg-slate-200 text-slate-600" : "bg-slate-100 text-slate-400"}`}>
                                    {s.store_name}: {s.quantita}
                                  </span>
                                ))}
                              </div>
                              {own && own.quantita > 0 ? (
                                <div className="mt-2 flex items-center gap-2">
                                  <input type="number" min="1" max={own.quantita} value={ricQty}
                                         onChange={(e) => setRicQty(Math.max(parseInt(e.target.value) || 1, 1))}
                                         className="w-16 rounded-md border border-slate-300 px-2 py-1.5 text-sm" data-testid={`servizio-ricambio-qty-${gi}`} />
                                  {g.categoria === "rigenerati" && (
                                    <input type="number" step="0.01" min="0" placeholder="Prezzo € a mano" value={ricPrezzo}
                                           onChange={(e) => setRicPrezzo(e.target.value)}
                                           className="w-36 rounded-md border border-amber-300 px-2 py-1.5 text-sm" data-testid={`servizio-ricambio-prezzo-${gi}`} />
                                  )}
                                  <Button type="button" size="sm" variant="outline" onClick={() => usaRicambio(own, g.categoria)} data-testid={`servizio-ricambio-usa-${gi}`}>Usa</Button>
                                </div>
                              ) : others.length > 0 ? (
                                <p className="mt-1.5 text-xs text-amber-600">Non in questo negozio — disponibile presso: {others.map((o) => `${o.store_name} (${o.quantita} pz)`).join(", ")}</p>
                              ) : (
                                <p className="mt-1.5 text-xs text-slate-400">Esaurito in tutti i negozi</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}

              <div className="rounded-xl border border-slate-200 p-4" data-testid="servizio-photos-card">
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
                  {isRip ? "Foto riparazione / documenti" : "Allegati"}
                </p>
                <div className="space-y-1.5" data-testid="servizio-attachments-list">
                  {attachments.map((a) => (
                    <div key={a.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <button className="flex items-center gap-2 text-sky-700 hover:underline"
                              onClick={() => downloadBlob(`/attachments/${a.id}/download`, a.original_filename)}
                              data-testid={`servizio-attachment-${a.id}`}>
                        <Paperclip className="h-3.5 w-3.5" /> {a.original_filename}
                      </button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteAttachment(a)} data-testid={`servizio-attachment-del-${a.id}`}>
                        <Trash2 className="h-3.5 w-3.5 text-rose-500" />
                      </Button>
                    </div>
                  ))}
                  {attachments.length === 0 && <p className="text-xs text-slate-400">Nessun allegato</p>}
                </div>
                <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 transition-colors hover:border-sky-400 hover:text-sky-700"
                       data-testid="servizio-upload-label">
                  {isRip ? <Camera className="h-4 w-4" /> : <Upload className="h-4 w-4" />}
                  {isRip ? "Carica foto riparazione" : "Carica allegato"}
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={uploadPhoto} data-testid="servizio-upload-input" />
                </label>
              </div>

              {detail.note && (
                <div><p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Note</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{detail.note}</p></div>
              )}

              <PortaleBox kind="servizio" id={detail.id} tipo={detail.tipo} operatore={detail.operatore_tel || detail.fornitore_ricambio}
                          insertedAt={detail.portale_inserito_at} insertedBy={detail.portale_inserito_da}
                          extraAt={detail.portale_extra_at} extraBy={detail.portale_extra_da} onChanged={refresh} />
              {isRip && (
                <WhatsAppLog url={`/servizi/${detail.id}/whatsapp-log`} refreshKey={detail.updated_at} onResent={refresh}
                             title="WhatsApp di questa riparazione" />
              )}

              <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
                <Button size="sm" onClick={sendPrivacy} disabled={waLoading} data-testid="servizio-wa-privacy-button"
                        className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                  <MessageCircle className="h-4 w-4" /> {waLoading ? "Invio..." : "Invia privacy WhatsApp"}
                </Button>
                {isRip && detail.stato === "pronto" && (
                  <Button size="sm" variant="outline" onClick={sendPronto} disabled={waLoading} className="border-emerald-300 text-emerald-700" data-testid="servizio-wa-pronto-button">
                    <MessageCircle className="mr-2 h-4 w-4" /> {detail.pronto_msg_sent_at ? "Reinvia avviso pronto" : "Avvisa cliente: pronto"}
                  </Button>
                )}
                <Button size="sm" variant="outline" onClick={toggleBlacklist}
                        className={detail.client_contacts?.no_recensioni ? "" : "border-slate-300 text-slate-600"} data-testid="servizio-blacklist-button">
                  <Ban className="mr-2 h-4 w-4" /> {detail.client_contacts?.no_recensioni ? "Riattiva recensioni" : "Blacklist recensioni"}
                </Button>
                {!detail.pagato && (
                  <Button size="sm" variant="outline" onClick={markPaid} data-testid="servizio-mark-paid-button">
                    <Wallet className="mr-2 h-4 w-4" /> Segna pagato
                  </Button>
                )}
                {isRip && (
                  <Button size="sm" variant="outline"
                          onClick={() => downloadBlob(`/servizi/${detail.id}/scheda`, `scheda_${detail.numero_riparazione || detail.id}.pdf`)}
                          data-testid="servizio-scheda-button">
                    <Printer className="mr-2 h-4 w-4" /> Scheda
                  </Button>
                )}
                {isRip && !detail.ritiro_id && (
                  <Button size="sm" variant="outline" className="border-emerald-300 text-emerald-700" onClick={() => setRitiroOpen(true)} data-testid="servizio-ritiro-button">
                    <Recycle className="mr-2 h-4 w-4" /> Ritirato
                  </Button>
                )}
                {isRip && detail.ritiro_id && (
                  <Button size="sm" variant="outline" onClick={() => downloadBlob(`/ritiri/${detail.ritiro_id}/pdf`, `${detail.ritiro_numero}.pdf`)} data-testid="servizio-ritiro-pdf-button">
                    <FileDown className="mr-2 h-4 w-4" /> Bolla {detail.ritiro_numero}
                  </Button>
                )}
                <Button size="sm" variant="outline" onClick={() => onEdit(detail)} data-testid="servizio-edit-button">
                  <Pencil className="mr-2 h-4 w-4" /> Modifica
                </Button>
                {isAdmin && (
                  <Button size="sm" variant="outline" className="text-rose-600" onClick={remove} data-testid="servizio-delete-button">
                    <Trash2 className="mr-2 h-4 w-4" /> Elimina
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
        <RitiroDaRiparazione open={ritiroOpen} onClose={() => setRitiroOpen(false)} servizio={detail}
                             onCreated={() => { refresh(); onChanged(); }} />
      </SheetContent>
    </Sheet>
  );
}
