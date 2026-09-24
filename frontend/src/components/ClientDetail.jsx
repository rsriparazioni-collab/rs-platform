import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, XCircle, FileText, MessageCircle, Paperclip, Pencil, ShieldCheck, Trash2, Upload, Wallet, Ban, Zap, Wrench, Smartphone, Wifi, PackageOpen, ArrowLeftRight, ShoppingBag } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import WhatsAppLog from "./WhatsAppLog";
import MessaggiPrevisti from "./MessaggiPrevisti";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import PortaleBox from "./PortaleBox";
import { lavorazioneLabel, lavorazioneBadge, fmtDate, servizioTipoLabel, ripStatoLabel, ripStatoBadge, tipoClienteInfo, enelOperazioneLabel } from "../lib/constants";
import { Button } from "./ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";

export default function ClientDetail({ client, onClose, onEdit, onChanged, isAdmin, onNuovaUtenza, onNuovoServizio }) {
  const { user } = useAuth();
  const canSposta = user?.role === "admin" || user?.role === "operatore" || user?.can_view_all;
  const [detail, setDetail] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [waLoading, setWaLoading] = useState("");
  const [servizi, setServizi] = useState([]);
  const [collegati, setCollegati] = useState([]);
  const [logKey, setLogKey] = useState(0);

  const loadCollegati = useCallback(async () => {
    if (!client) return;
    try {
      const res = await api.get(`/clients/${client.id}/collegati`);
      setCollegati(res.data);
    } catch {
      setCollegati([]);
    }
  }, [client]);

  const toggleBlacklist = async () => {
    const next = !detail.no_recensioni;
    if (next && !window.confirm("Bloccare l'invio delle richieste di recensione a questo cliente?")) return;
    try {
      await api.post(`/clients/${detail.id}/blacklist-recensioni`, { no_recensioni: next });
      toast.success(next ? "Cliente in blacklist: nessuna recensione verrà inviata" : "Blacklist rimossa");
      refresh();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const loadServizi = useCallback(async () => {
    if (!client) return;
    try {
      const res = await api.get(`/clients/${client.id}/servizi`);
      setServizi(res.data);
    } catch {
      setServizi([]);
    }
  }, [client]);

  const refresh = useCallback(async () => {
    if (!client) return;
    try {
      const res = await api.get(`/clients/${client.id}`);
      setDetail(res.data);
    } catch {
      toast.error("Impossibile caricare il cliente");
    }
  }, [client]);

  const loadAttachments = useCallback(async () => {
    if (!client) return;
    try {
      const res = await api.get(`/clients/${client.id}/attachments`);
      setAttachments(res.data);
    } catch {
      setAttachments([]);
    }
  }, [client]);

  useEffect(() => {
    setDetail(null);
    setAttachments([]);
    if (client) {
      refresh();
      loadAttachments();
      loadServizi();
      loadCollegati();
    }
  }, [client, refresh, loadAttachments, loadServizi, loadCollegati]);

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

  const uploadAttachment = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !detail) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/clients/${detail.id}/attachments`, fd);
      toast.success("Allegato caricato");
      loadAttachments();
    } catch (err) {
      toast.error(apiError(err, "Upload fallito"));
    }
  };

  const deleteAttachment = async (att) => {
    try {
      await api.delete(`/attachments/${att.id}`);
      toast.success("Allegato eliminato");
      loadAttachments();
    } catch (e) {
      toast.error(apiError(e, "Eliminazione fallita"));
    }
  };

  const sendWhatsApp = async (tipo) => {
    setWaLoading(tipo);
    try {
      const res = await api.post(`/clients/${detail.id}/whatsapp/${tipo}`);
      if (tipo === "privacy") {
        if (res.data.privacy_registered) {
          toast.success("Modulo privacy compilato e inviato in automatico sul sito");
        } else if (res.data.registration_error) {
          toast.warning(`Registrazione sito non riuscita: ${res.data.registration_error}`);
        }
        if (res.data.wa_error) {
          toast.warning(`WhatsApp non inviato: ${res.data.wa_error}`);
        } else {
          toast.success("Messaggio privacy inviato. La richiesta recensione partirà automaticamente tra 5 minuti.");
        }
      } else {
        toast.success("Richiesta recensione inviata");
      }
      refresh();
      setLogKey((k) => k + 1);
    } catch (e) {
      toast.error(apiError(e, "Invio WhatsApp fallito"));
    } finally {
      setWaLoading("");
    }
  };

  const markPaid = async () => {
    try {
      await api.post(`/clients/${detail.id}/mark-paid`);
      toast.success("Pagamento registrato. Tornerà 'non pagato' tra 6 mesi.");
      refresh();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const spostaGestione = async () => {
    const aEnel = detail.gestione !== "enel";
    const motivo = window.prompt(aEnel
      ? "Spostare questo cliente nell'ufficio ENEL (utenza diretta Enel)? Indica il motivo:"
      : "SBLOCCO cliente ENEL → CambiaOra. Usare solo se il cliente si è spostato di sua volontà o risulta vecchio cliente Enel. Indica il motivo:");
    if (motivo === null) return;
    try {
      await api.post(`/clients/${detail.id}/sposta-gestione`, { gestione: aEnel ? "enel" : "cambiaora", motivo, enel_operazione: aEnel ? "altro" : "" });
      toast.success(aEnel ? "Cliente spostato in gestione ENEL" : "Cliente sbloccato e spostato a CambiaOra");
      refresh();
      onChanged();
    } catch (e) {
      toast.error(apiError(e, "Spostamento non riuscito"));
    }
  };

  const remove = async () => {
    if (!window.confirm(`Eliminare ${detail.cognome} ${detail.nome}?`)) return;
    try {
      await api.delete(`/clients/${detail.id}`);
      toast.success("Cliente eliminato");
      onClose();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const anonimizza = async () => {
    const ok = window.prompt(`ANONIMIZZAZIONE GDPR di ${detail.cognome} ${detail.nome}.\nVerranno cancellati per sempre: dati personali, allegati, messaggi WhatsApp, codici dispositivo. Restano solo i dati statistici (servizi, importi, date).\n\nScrivi ANONIMIZZA per confermare:`);
    if (ok !== "ANONIMIZZA") return;
    try {
      const r = await api.post(`/clients/${detail.id}/anonimizza`);
      toast.success(`Cliente anonimizzato: ${r.data.allegati_eliminati} allegati e ${r.data.messaggi_eliminati} messaggi eliminati`);
      onClose();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <Sheet open={Boolean(client)} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl" data-testid="client-detail-sheet">
        {!detail && (
          <SheetHeader><SheetTitle className="sr-only">Dettaglio cliente</SheetTitle></SheetHeader>
        )}
        {detail && (
          <>
            <SheetHeader>
              <SheetTitle className="font-heading text-xl">{detail.cognome} {detail.nome}</SheetTitle>
            </SheetHeader>
            <div className="mt-6 space-y-6">
              <div className="flex flex-wrap gap-2">
                <span className={`status-badge ${lavorazioneBadge(detail.lavorazione)}`}>{lavorazioneLabel(detail.lavorazione)}</span>
                <span data-testid="detail-tipo-cliente-badge" className={`status-badge ${tipoClienteInfo(detail.tipo_cliente).badge}`}>
                  {tipoClienteInfo(detail.tipo_cliente).label}
                </span>
                <span data-testid="detail-gestione-badge" className={`status-badge ${detail.gestione === "enel" ? "bg-amber-500/15 text-amber-700 border-amber-300" : "bg-fuchsia-500/15 text-fuchsia-700 border-fuchsia-300"}`}>
                  {detail.gestione === "enel" ? `ENEL${detail.enel_operazione ? ` · ${enelOperazioneLabel(detail.enel_operazione)}` : ""}` : "CambiaOra"}
                </span>
                {detail.gestione !== "enel" && /enel/i.test(detail.fornitore_provenienza || "") && (
                  <span className="status-badge bg-slate-500/10 text-slate-600 border-slate-300" data-testid="detail-da-enel-badge" title="Cliente CambiaOra proveniente da Enel (fornitore precedente), NON cliente ufficio ENEL">
                    da Enel (fornitore precedente)
                  </span>
                )}
                <span className={`status-badge ${detail.tipo_contratto === "fisso" ? "bg-sky-500/15 text-sky-700 border-sky-300" : "bg-violet-500/15 text-violet-700 border-violet-300"}`}>
                  Contratto {detail.tipo_contratto}
                </span>
                {detail.privacy_firmata && (
                  <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">
                    <ShieldCheck className="h-3 w-3" /> Privacy firmata
                  </span>
                )}
                {detail.anonimizzato_at && (
                  <span className="status-badge bg-slate-500/15 text-slate-700 border-slate-300" data-testid="client-anonimizzato-badge">Anonimizzato {fmtDate(detail.anonimizzato_at)}</span>
                )}
                {detail.no_recensioni && (
                  <span className="status-badge bg-slate-500/15 text-slate-700 border-slate-300" data-testid="client-blacklist-badge">
                    <Ban className="h-3 w-3" /> No recensioni
                  </span>
                )}
                {detail.pagato_effettivo
                  ? <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300">Pagato</span>
                  : <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300">Non pagato</span>}
              </div>

              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Timeline contratto</p>
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div><p className="text-xs text-slate-500">Contratto</p><p className="font-semibold" data-testid="detail-data-contratto">{fmtDate(detail.data_contratto)}</p></div>
                  <div><p className="text-xs text-slate-500">Attivazione (+2m)</p><p className="font-semibold" data-testid="detail-data-attivazione">{fmtDate(detail.data_attivazione)}</p></div>
                  <div><p className="text-xs text-slate-500">Rinnovo (+10m)</p><p className="font-semibold text-amber-700" data-testid="detail-data-rinnovo">{fmtDate(detail.data_rinnovo)}</p></div>
                  <div><p className="text-xs text-slate-500">Scadenza</p><p className="font-semibold" data-testid="detail-data-scadenza">{fmtDate(detail.data_scadenza)}</p></div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div><p className="text-xs text-slate-500">Telefono</p><p className="font-medium">{detail.telefono || "-"}</p></div>
                <div><p className="text-xs text-slate-500">Email</p><p className="font-medium">{detail.email || "-"}</p></div>
                <div><p className="text-xs text-slate-500">Codice Fiscale</p><p className="font-medium">{detail.codice_fiscale || "-"}</p></div>
                <div><p className="text-xs text-slate-500">P.IVA</p><p className="font-medium">{detail.p_iva || "-"}</p></div>
                <div className="col-span-2"><p className="text-xs text-slate-500">Indirizzo</p><p className="font-medium" data-testid="detail-indirizzo">{[[detail.indirizzo, detail.civico].filter(Boolean).join(" "), [detail.cap, detail.comune].filter(Boolean).join(" "), detail.provincia].filter(Boolean).join(", ") || "-"}</p></div>
                <div><p className="text-xs text-slate-500">POD</p><p className="font-medium">{detail.pod || "-"}</p></div>
                <div><p className="text-xs text-slate-500">PDR</p><p className="font-medium">{detail.pdr || "-"}</p></div>
                <div className="col-span-2"><p className="text-xs text-slate-500">IBAN</p><p className="font-medium">{detail.iban || "-"}</p></div>
                {detail.tipo_bolletta === "luce" && <div><p className="text-xs text-slate-500">Potenza</p><p className="font-medium">{detail.kw_potenza ?? "-"} kW</p></div>}
              </div>

              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Confronto tariffe</p>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs font-semibold text-slate-500">Attuale — {detail.fornitore_provenienza || "-"}</p>
                    {detail.tipo_bolletta === "luce"
                      ? <p className="mt-1 font-medium">{detail.costo_kwh_attuale ?? "-"} €/kWh</p>
                      : <p className="mt-1 font-medium">{detail.costo_smc_attuale ?? "-"} €/Smc</p>}
                    <p className="text-xs text-slate-500">Fisse: {detail.spese_fisse_attuale ?? "-"} €/mese</p>
                  </div>
                  <div className="rounded-lg bg-sky-50 p-3">
                    <p className="text-xs font-semibold text-sky-700">Nuovo — {detail.nuovo_fornitore || "-"}</p>
                    {detail.tipo_bolletta === "luce"
                      ? <p className="mt-1 font-medium">{detail.costo_kwh_nuovo ?? "-"} €/kWh</p>
                      : <p className="mt-1 font-medium">{detail.costo_smc_nuovo ?? "-"} €/Smc</p>}
                    <p className="text-xs text-slate-500">Fisse: {detail.spese_fisse_nuovo ?? "-"} €/mese</p>
                  </div>
                </div>
              </div>

              {detail.note && (
                <div><p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Note</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700" data-testid="detail-note">{detail.note}</p></div>
              )}

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Storico lavorazioni</p>
                <div className="max-h-48 space-y-2 overflow-y-auto" data-testid="detail-history">
                  {(detail.history || []).map((h) => (
                    <div key={h.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
                      <span><strong>{h.operatore_name}</strong> · {lavorazioneLabel(h.status)}</span>
                      <span className="text-slate-500">{fmtDate(h.created_at)}</span>
                    </div>
                  ))}
                  {(detail.history || []).length === 0 && <p className="text-xs text-slate-400">Nessuno storico</p>}
                </div>
              </div>

              {collegati.length > 0 && (
                <div data-testid="client-utenze-collegate">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Altre utenze della stessa persona (stesso CF / P.IVA / telefono)</p>
                  <div className="space-y-1.5">
                    {collegati.map((u) => (
                      <button type="button" key={u.id} onClick={() => onNuovoServizio?.("apri_utenza", u)}
                              className="flex w-full items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-left text-xs hover:bg-slate-100"
                              data-testid={`utenza-collegata-${u.id}`}>
                        <span className="font-medium text-slate-800">
                          {u.tipo_bolletta === "gas" ? "Gas" : "Luce"}{u.pod ? ` · POD ${u.pod}` : ""}{u.pdr ? ` · PDR ${u.pdr}` : ""}{u.nuovo_fornitore ? ` · ${u.nuovo_fornitore}` : ""}
                        </span>
                        <span className={`status-badge ${lavorazioneBadge(u.lavorazione)}`}>{lavorazioneLabel(u.lavorazione)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {(onNuovaUtenza || onNuovoServizio) && !detail.anonimizzato_at && (
                <div className="rounded-xl border border-sky-200 bg-sky-50/50 p-4" data-testid="aggiungi-al-cliente">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Aggiungi al cliente</p>
                  <div className="flex flex-wrap gap-2">
                    {onNuovaUtenza && (
                      <Button size="sm" variant="outline" className="gap-1.5" data-testid="aggiungi-utenza-button"
                              onClick={() => onNuovaUtenza(detail, detail.tipo_bolletta === "luce" ? "gas" : "luce")}>
                        <Zap className="h-4 w-4" /> Utenza {detail.tipo_bolletta === "luce" ? "Gas" : "Luce"}
                      </Button>
                    )}
                    {onNuovoServizio && (
                      <>
                        <Button size="sm" variant="outline" className="gap-1.5" data-testid="aggiungi-riparazione-button" onClick={() => onNuovoServizio("riparazione", detail)}>
                          <Wrench className="h-4 w-4" /> Riparazione
                        </Button>
                        <Button size="sm" variant="outline" className="gap-1.5" data-testid="aggiungi-sim-button" onClick={() => onNuovoServizio("sim", detail)}>
                          <Smartphone className="h-4 w-4" /> SIM
                        </Button>
                        <Button size="sm" variant="outline" className="gap-1.5" data-testid="aggiungi-internet-button" onClick={() => onNuovoServizio("internet", detail)}>
                          <Wifi className="h-4 w-4" /> Internet / Fisso
                        </Button>
                        <Button size="sm" variant="outline" className="gap-1.5" data-testid="aggiungi-ritiro-button" onClick={() => onNuovoServizio("ritiro", detail)}>
                          <PackageOpen className="h-4 w-4" /> Ritiro telefono
                        </Button>
                        <Button size="sm" variant="outline" className="gap-1.5" data-testid="aggiungi-vendita-button" onClick={() => onNuovoServizio("vendita", detail)}>
                          <ShoppingBag className="h-4 w-4" /> Vendita
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}

              {servizi.length > 0 && (
                <div data-testid="client-servizi-collegati">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Servizi collegati (riparazioni, telefonia)</p>
                  <div className="space-y-1.5">
                    {servizi.map((s) => (
                      <div key={s.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
                        <span className="font-medium text-slate-800">
                          {servizioTipoLabel(s.tipo)}{s.dispositivo ? ` · ${s.dispositivo}` : ""}{s.operatore_tel ? ` · ${s.operatore_tel}` : ""}
                        </span>
                        {s.tipo === "riparazione"
                          ? <span className={`status-badge ${ripStatoBadge(s.stato)}`}>{ripStatoLabel(s.stato)}</span>
                          : <span className={`status-badge ${s.pagato ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-rose-500/15 text-rose-700 border-rose-300"}`}>{s.pagato ? "Pagato" : "Non pagato"}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4" data-testid="whatsapp-card">
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">WhatsApp automatico</p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => sendWhatsApp("privacy")} disabled={waLoading !== ""}
                          data-testid="wa-privacy-button" className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                    <MessageCircle className="h-4 w-4" />
                    {waLoading === "privacy" ? "Invio..." : "Invia link privacy"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => sendWhatsApp("review")} disabled={waLoading !== "" || detail.no_recensioni}
                          data-testid="wa-review-button" className="gap-2">
                    <MessageCircle className="h-4 w-4" />
                    {waLoading === "review" ? "Invio..." : "Invia richiesta recensione"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={toggleBlacklist} data-testid="client-blacklist-button" className="gap-2">
                    <Ban className="h-4 w-4" /> {detail.no_recensioni ? "Riattiva recensioni" : "Blacklist recensioni"}
                  </Button>
                </div>
                <div className="mt-2 space-y-0.5 text-xs text-slate-500">
                  {detail.no_recensioni && <p className="text-slate-700" data-testid="wa-blacklist-info">Cliente in blacklist: nessuna richiesta recensione automatica.</p>}
                  {detail.privacy_msg_sent_at && <p data-testid="wa-privacy-sent">Privacy inviata il {fmtDate(detail.privacy_msg_sent_at)}</p>}
                  {detail.review_msg_sent_at && <p data-testid="wa-review-sent">Recensione richiesta il {fmtDate(detail.review_msg_sent_at)}</p>}
                  {detail.rinnovo_msg_sent_at && <p data-testid="wa-rinnovo-sent">Avviso rinnovo luce/gas inviato il {fmtDate(detail.rinnovo_msg_sent_at)}</p>}
                  {detail.truffe_msg_sent_at && <p data-testid="wa-truffe-sent">Avviso anti-truffa inviato il {fmtDate(detail.truffe_msg_sent_at)}</p>}
                </div>
              </div>

              <PortaleBox kind="cliente" id={detail.id} sezione="energia" operatore={detail.nuovo_fornitore}
                          insertedAt={detail.portale_inserito_at} insertedBy={detail.portale_inserito_da}
                          extraAt={detail.portale_extra_at} extraBy={detail.portale_extra_da} onChanged={refresh} />
              <MessaggiPrevisti clientId={detail.id} refreshKey={logKey} />
              {isAdmin && (
                <Button size="sm" variant="outline" className="w-full gap-2" data-testid="client-gdpr-export-button"
                        onClick={() => downloadBlob(`/clients/${detail.id}/gdpr-export`, `dati_personali_${detail.cognome}.pdf`)}>
                  <FileText className="h-4 w-4" /> Esporta pacchetto dati GDPR (PDF)
                </Button>
              )}
              <WhatsAppLog url={`/clients/${detail.id}/whatsapp-log`} refreshKey={logKey} onResent={refresh} />

              <div className="rounded-xl border border-slate-200 p-4" data-testid="attachments-card">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Allegati (bollette, documenti)</p>
                  {attachments.length > 0 && (
                    <Button size="sm" variant="outline" data-testid="merged-pdf-button"
                            onClick={() => downloadBlob(`/clients/${detail.id}/attachments/merged`, `documenti_${detail.cognome}.pdf`)}>
                      <FileText className="mr-2 h-4 w-4" /> PDF unico
                    </Button>
                  )}
                </div>
                <div className="space-y-1.5" data-testid="attachments-list">
                  {attachments.map((a) => (
                    <div key={a.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <button className="flex items-center gap-2 text-sky-700 hover:underline"
                              onClick={() => downloadBlob(`/attachments/${a.id}/download`, a.original_filename)}
                              data-testid={`attachment-download-${a.id}`}>
                        <Paperclip className="h-3.5 w-3.5" /> {a.original_filename}
                      </button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" data-testid={`attachment-delete-${a.id}`}
                              onClick={() => deleteAttachment(a)}>
                        <Trash2 className="h-3.5 w-3.5 text-rose-500" />
                      </Button>
                    </div>
                  ))}
                  {attachments.length === 0 && <p className="text-xs text-slate-400">Nessun allegato</p>}
                </div>
                <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 transition-colors hover:border-sky-400 hover:text-sky-700"
                       data-testid="attachment-upload-label">
                  <Upload className="h-4 w-4" /> Carica PDF o immagine
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={uploadAttachment}
                         data-testid="attachment-upload-input" />
                </label>
              </div>

              <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
                {!detail.pagato_effettivo && (
                  <Button size="sm" onClick={markPaid} data-testid="detail-mark-paid-button"
                          className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                    <Wallet className="h-4 w-4" /> Segna pagato
                  </Button>
                )}
                <Button size="sm" variant="outline" data-testid="detail-edit-button" onClick={() => onEdit(detail)}>
                  <Pencil className="mr-2 h-4 w-4" /> Modifica
                </Button>
                {canSposta && !detail.anonimizzato_at && (
                  <Button size="sm" variant="outline" data-testid="detail-sposta-gestione-button" onClick={spostaGestione}
                          className={detail.gestione === "enel" ? "border-amber-300 text-amber-700" : "border-fuchsia-300 text-fuchsia-700"}
                          title={detail.gestione === "enel" ? "Sblocca: il cliente lascia l'ufficio ENEL e passa a CambiaOra" : "Sposta il cliente nell'ufficio ENEL (utenza diretta)"}>
                    <ArrowLeftRight className="mr-2 h-4 w-4" /> {detail.gestione === "enel" ? "Sblocca → CambiaOra" : "Sposta a ENEL"}
                  </Button>
                )}
                {(
                  <Button size="sm" variant="outline" data-testid="detail-delete-button"
                          className="text-rose-600 hover:text-rose-700" onClick={remove}>
                    <Trash2 className="mr-2 h-4 w-4" /> Elimina
                  </Button>
                )}
                {isAdmin && !detail.anonimizzato_at && (
                  <Button size="sm" variant="outline" data-testid="detail-anonimizza-button"
                          className="text-slate-600" onClick={anonimizza} title="Cancellazione dati personali (art. 17 GDPR)">
                    <ShieldCheck className="mr-2 h-4 w-4" /> Anonimizza (GDPR)
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
