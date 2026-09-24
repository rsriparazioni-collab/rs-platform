import { useState } from "react";
import { Mail, FileDown, Archive } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

const MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];

export default function ReportCommercialistaDialog({ stores }) {
  const prev = new Date(); prev.setDate(0);
  const [open, setOpen] = useState(false);
  const [storeId, setStoreId] = useState("");
  const [anno, setAnno] = useState(prev.getFullYear());
  const [mese, setMese] = useState(prev.getMonth() + 1);
  const [extra, setExtra] = useState("");
  const [sending, setSending] = useState(false);
  const store = stores.find((s) => s.id === storeId);
  const q = `store_id=${storeId}&anno=${anno}&mese=${mese}`;

  const invia = async () => {
    if (!storeId) return toast.error("Scegli il negozio");
    setSending(true);
    try {
      const r = await api.post("/ritiri/report-mensile/invia", { store_id: storeId, anno, mese, email_extra: extra });
      if (r.data.inviato) toast.success(`Report inviato a ${r.data.to.join(", ")} (${r.data.ritiri} ritiri)`);
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
        <DialogContent className="max-w-lg" data-testid="report-commercialista-dialog">
          <DialogHeader><DialogTitle className="font-heading text-xl">Registro ritiri mensile per la commercialista</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-600">Viene inviato automaticamente il 1° di ogni mese per il mese precedente. Qui puoi scaricarlo o inviarlo subito.</p>
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
