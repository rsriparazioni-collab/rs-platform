import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Paperclip, Pencil, Trash2, Upload, Wallet, ShieldCheck, Camera } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { ripStatoLabel, ripStatoBadge, servizioTipoLabel, fmtDate, RIP_STATI } from "../lib/constants";
import { Button } from "./ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

function PrezzoBreakdown({ s }) {
  const minuti = Math.max(s.minuti_lavoro || 0, 30);
  const lavoro = minuti * 0.22775;
  const base = s.con_ricambio ? (s.costo_componente || 0) + 2 + lavoro + 60 : 30 + lavoro;
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4" data-testid="servizio-prezzo-card">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Prezzo consigliato</p>
      <p className="font-heading text-3xl font-bold text-emerald-800">€ {(s.prezzo_consigliato ?? 0).toFixed(2)}</p>
      <div className="mt-2 space-y-0.5 text-xs text-slate-600">
        {s.con_ricambio ? (
          <>
            <p>Componente: € {(s.costo_componente || 0).toFixed(2)}</p>
            <p>Trasporto: € 2,00</p>
            <p>Margine: € 60,00</p>
          </>
        ) : (
          <p>Base senza ricambio: € 30,00</p>
        )}
        <p>Lavoro: {minuti} min × 0,22775€ = € {lavoro.toFixed(2)}</p>
        <p>IVA 22% inclusa</p>
      </div>
    </div>
  );
}

export default function ServizioDetail({ servizio, onClose, onEdit, onChanged, isAdmin }) {
  const [detail, setDetail] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [waLoading, setWaLoading] = useState(false);

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

  const changeStato = async (stato) => {
    try {
      await api.patch(`/servizi/${detail.id}`, { client_id: detail.client_id, tipo: detail.tipo, stato });
      toast.success(`Stato aggiornato: ${ripStatoLabel(stato)}`);
      refresh();
      onChanged();
    } catch (e) {
      toast.error(apiError(e));
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
        ? "Messaggio privacy inviato. Recensione del negozio in partenza tra 5 minuti."
        : "Messaggio privacy inviato (nessun link recensioni configurato per questo negozio)");
      refresh();
    } catch (e) {
      toast.error(apiError(e, "Invio fallito"));
    } finally {
      setWaLoading(false);
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
              <div className="flex flex-wrap gap-2">
                {isRip && <span className={`status-badge ${ripStatoBadge(detail.stato)}`} data-testid="servizio-stato-badge">{ripStatoLabel(detail.stato)}</span>}
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
                    <div><p className="text-xs text-slate-500">Ricambio</p><p className="font-medium">{detail.con_ricambio ? "Da ordinare" : "Non necessario"}</p></div>
                    {detail.problema && <div className="col-span-2"><p className="text-xs text-slate-500">Problema</p><p className="font-medium whitespace-pre-wrap">{detail.problema}</p></div>}
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

              <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
                <Button size="sm" onClick={sendPrivacy} disabled={waLoading} data-testid="servizio-wa-privacy-button"
                        className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                  <MessageCircle className="h-4 w-4" /> {waLoading ? "Invio..." : "Invia privacy WhatsApp"}
                </Button>
                {!detail.pagato && (
                  <Button size="sm" variant="outline" onClick={markPaid} data-testid="servizio-mark-paid-button">
                    <Wallet className="mr-2 h-4 w-4" /> Segna pagato
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
      </SheetContent>
    </Sheet>
  );
}
