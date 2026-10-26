import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Rocket } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";

export const VaiOnlineDialog = ({ open, onOpenChange, onDone }) => {
  const [ck, setCk] = useState(null);
  const [mese, setMese] = useState("");
  const load = () => api.get("/incentivi/checklist").then((r) => { setCk(r.data); setMese(r.data.mese_partenza || mese); }).catch((e) => toast.error(apiError(e)));
  useEffect(() => { if (open) load(); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const salvaMese = async () => { try { await api.post("/incentivi/online", { online: false, mese_partenza: mese }); toast.success("Mese di partenza salvato"); load(); } catch (e) { toast.error(apiError(e)); } };
  const attiva = async (forza) => {
    try { await api.post("/incentivi/online", { online: true, mese_partenza: mese, forza }); toast.success("Incentivi ONLINE: i partecipanti vedono la classifica"); onOpenChange(false); onDone(); }
    catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="inc-online-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><Rocket className="h-5 w-5" /> Checklist prima di andare online</DialogTitle></DialogHeader>
        {!ck ? <p className="text-sm text-slate-500">Verifica…</p> : (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-2"><span className="text-slate-600">Mese di partenza</span><input type="month" value={mese} onChange={(e) => setMese(e.target.value)} className="h-9 rounded-md border border-slate-200 px-2" data-testid="inc-online-mese" /><Button size="sm" variant="outline" onClick={salvaMese} data-testid="inc-online-salva-mese">Salva</Button></div>
            <ul className="space-y-2">
              {ck.voci.map((v) => <li key={v.id} className="flex items-start gap-2" data-testid={`inc-ck-${v.id}`}>{v.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> : <XCircle className="mt-0.5 h-4 w-4 text-red-500" />}<div><p className={v.ok ? "" : "font-medium text-red-700"}>{v.label}</p>{v.dettaglio && <p className="text-xs text-slate-500">{v.dettaglio}</p>}</div></li>)}
            </ul>
            <p className="text-xs text-slate-500">Prima della partenza: regolamento firmato da tutti e verifica del consulente del lavoro. Da online, i partecipanti vedono "I miei incentivi" nei KPI dal mese di partenza.</p>
            <div className="flex justify-end gap-2">
              {!ck.pronto && <Button variant="outline" onClick={() => window.confirm("Attivare comunque con checklist incompleta?") && attiva(true)} data-testid="inc-online-forza">Attiva comunque</Button>}
              <Button disabled={!ck.pronto} onClick={() => attiva(false)} data-testid="inc-online-conferma"><Rocket className="mr-1 h-4 w-4" /> Vai online</Button>
            </div>
          </div>)}
      </DialogContent>
    </Dialog>
  );
};
