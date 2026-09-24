import { useEffect, useState } from "react";
import { Mail, FileDown, Archive } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";

const MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];

export default function ReportCommercialistaDialog({ stores }) {
  const prev = new Date(); prev.setDate(0);
  const [open, setOpen] = useState(false);
  const [storeId, setStoreId] = useState("");
  const [anno, setAnno] = useState(prev.getFullYear());
  const [mese, setMese] = useState(prev.getMonth() + 1);
  const [extra, setExtra] = useState("");
  const [sending, setSending] = useState(false);
  const [anteprima, setAnteprima] = useState([]);
  const store = stores.find((s) => s.id === storeId);
  const q = `store_id=${storeId}&anno=${anno}&mese=${mese}`;
  const riga = anteprima.find((a) => a.store_id === storeId);

  useEffect(() => {
    if (!open) return;
    api.get(`/ritiri/report-mensile/anteprima?anno=${anno}&mese=${mese}`).then((r) => setAnteprima(r.data)).catch(() => setAnteprima([]));
  }, [open, anno, mese]);

  const invia = async () => {
    if (!storeId) return toast.error("Scegli il negozio");
    setSending(true);
    try {
      const r = await api.post("/ritiri/report-mensile/invia", { store_id: storeId, anno, mese, email_extra: extra });
      if (r.data.inviato) { toast.success(`Report inviato a ${r.data.to.join(", ")} (${r.data.ritiri} ritiri)`); setAnteprima((a) => a.map((x) => x.store_id === storeId ? { ...x, inviato_at: new Date().toISOString() } : x)); }
      else toast.error(r.data.motivo || "Non inviato");
    } catch (e) {
      toast.error(apiError(e, "Invio fallito"));
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)} className="gap-2" data-testid="report-commercialista-button">
        <Mail className="h-4 w-4" /> Report commercialista
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="report-commercialista-dialog">
          <DialogHeader><DialogTitle className="font-heading text-xl">Registro ritiri mensile per la commercialista</DialogTitle>
            <DialogDescription>Viene inviato automaticamente il 1° di ogni mese per il mese precedente. Qui puoi scaricarlo o inviarlo subito.</DialogDescription></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 space-y-1.5">
              <Label className="text-xs uppercase text-slate-500">Negozio</Label>
              <Select value={storeId} onValueChange={setStoreId}>
                <SelectTrigger data-testid="report-store"><SelectValue placeholder="Scegli negozio" /></SelectTrigger>
                <SelectContent>{stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}</SelectContent>
              </Select>
              {store && (
                <p className="text-xs text-slate-500" data-testid="report-destinatari">
                  Destinatari: {store.email_commercialista || <span className="text-rose-600">nessuno — imposta "Email commercialista" in Gestione Negozi</span>}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase text-slate-500">Mese</Label>
              <Select value={String(mese)} onValueChange={(v) => setMese(Number(v))}>
                <SelectTrigger data-testid="report-mese"><SelectValue /></SelectTrigger>
                <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase text-slate-500">Anno</Label>
              <Input type="number" value={anno} onChange={(e) => setAnno(Number(e.target.value))} data-testid="report-anno" />
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label className="text-xs uppercase text-slate-500">Email aggiuntive (opzionale, separate da virgola)</Label>
              <Input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="es. rsriparazioni@gmail.com" data-testid="report-email-extra" />
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3" data-testid="report-anteprima">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Anteprima {MESI[mese - 1]} {anno} per negozio</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {anteprima.map((a) => (
                <button key={a.store_id} type="button" onClick={() => setStoreId(a.store_id)} data-testid={`report-anteprima-${a.store_id}`}
                        className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition-colors ${a.store_id === storeId ? "border-slate-900 bg-white" : "border-slate-200 bg-white/70 hover:border-slate-400"}`}>
                  <div>
                    <p className="font-semibold text-slate-800">{a.nome}</p>
                    <p className="text-[11px] text-slate-500">{a.inviato_at ? `Inviato il ${new Date(a.inviato_at).toLocaleDateString("it-IT")}` : a.email_commercialista ? "Da inviare" : "Nessuna email commercialista"}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-slate-900">{a.ritiri} ritiri</p>
                    <p className="text-[11px] text-slate-500">{a.valore.toFixed(2)} €{a.senza_documenti > 0 ? ` · ${a.senza_documenti} senza doc.` : ""}</p>
                  </div>
                </button>
              ))}
            </div>
            {riga && riga.righe.length > 0 && (
              <div className="mt-3 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white" data-testid="report-anteprima-righe">
                <table className="w-full text-xs">
                  <thead className="bg-slate-100 text-left text-slate-500"><tr><th className="px-2 py-1">N.</th><th className="px-2 py-1">Data</th><th className="px-2 py-1">Cliente</th><th className="px-2 py-1">Articolo</th><th className="px-2 py-1 text-right">Valore</th><th className="px-2 py-1">Stato</th><th className="px-2 py-1">Doc.</th></tr></thead>
                  <tbody>
                    {riga.righe.map((r) => (
                      <tr key={r.numero} className="border-t border-slate-100">
                        <td className="px-2 py-1 font-medium">{r.numero}</td><td className="px-2 py-1">{r.data ? new Date(r.data).toLocaleDateString("it-IT") : "-"}</td>
                        <td className="px-2 py-1">{r.cliente}</td><td className="px-2 py-1">{r.articolo}</td>
                        <td className="px-2 py-1 text-right">{r.valore != null ? `${Number(r.valore).toFixed(2)} €` : "-"}</td><td className="px-2 py-1">{r.stato}</td>
                        <td className={`px-2 py-1 ${r.documenti ? "text-emerald-700" : "text-amber-600"}`}>{r.documenti || "nessuno"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {riga && riga.righe.length === 0 && <p className="mt-2 text-xs text-slate-500">Nessun ritiro per {riga.nome} nel mese selezionato.</p>}
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" disabled={!storeId} className="gap-1.5" data-testid="report-download-pdf"
                    onClick={() => downloadBlob(`/ritiri/report-mensile?${q}&formato=pdf`, `Report_ritiri_${store?.nome}_${anno}-${String(mese).padStart(2, "0")}.pdf`)}>
              <FileDown className="h-4 w-4" /> Scarica PDF
            </Button>
            <Button variant="outline" disabled={!storeId} className="gap-1.5" data-testid="report-download-zip"
                    onClick={() => downloadBlob(`/ritiri/report-mensile?${q}&formato=zip`, `Ritiri_${store?.nome}_${anno}-${String(mese).padStart(2, "0")}.zip`)}>
              <Archive className="h-4 w-4" /> ZIP bolle + documenti
            </Button>
            <Button disabled={!storeId || sending} onClick={invia} className="gap-1.5 bg-slate-900 hover:bg-slate-800" data-testid="report-send">
              <Mail className="h-4 w-4" /> {sending ? "Invio..." : "Invia ora via email"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
