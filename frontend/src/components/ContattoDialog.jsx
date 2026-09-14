import { useEffect, useState } from "react";
import { PhoneCall, PhoneMissed, CalendarClock, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDate } from "../lib/constants";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

export const ESITI = {
  non_risponde: { label: "Non risponde", short: "Non risponde", icon: PhoneMissed, cls: "bg-amber-50 text-amber-700 border-amber-200" },
  richiamare: { label: "Richiamare più tardi", short: "Richiamare", icon: CalendarClock, cls: "bg-sky-50 text-sky-700 border-sky-200" },
  contattato: { label: "Contattato, tutto ok", short: "Contattato", icon: CheckCircle2, cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  non_interessato: { label: "Non interessato", short: "Non interessato", icon: XCircle, cls: "bg-slate-100 text-slate-600 border-slate-200" },
  chiuso: { label: "Chiuso / risolto", short: "Chiuso", icon: CheckCircle2, cls: "bg-slate-100 text-slate-600 border-slate-200" },
};
export const MOTIVI = { rinnovo: "Rinnovo energia", vincolo: "Vincolo telefonia", riparazione_pronta: "Riparazione pronta", pagamento: "Pagamento", altro: "Altro" };

const plusDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

export function ContattoBadge({ contatto, testid }) {
  if (!contatto) return null;
  const e = ESITI[contatto.esito] || ESITI.chiuso;
  const Icon = e.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${e.cls}`} data-testid={testid} title={contatto.note || ""}>
      <Icon className="h-3 w-3" /> {e.short}{contatto.richiamare_il && contatto.aperto ? ` · richiama ${fmtDate(contatto.richiamare_il)}` : ""}
    </span>
  );
}

export function ContattoButton({ onClick, testid }) {
  return (
    <button type="button" onClick={(ev) => { ev.preventDefault(); ev.stopPropagation(); onClick(); }} title="Registra esito contatto"
            className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-900 hover:text-white" data-testid={testid}>
      <PhoneCall className="h-3.5 w-3.5" />
    </button>
  );
}

export default function ContattoDialog({ target, onClose, onSaved }) {
  const [esito, setEsito] = useState("non_risponde");
  const [data, setData] = useState(plusDays(2));
  const [note, setNote] = useState("");
  const [storico, setStorico] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!target) return;
    setEsito("non_risponde"); setData(plusDays(2)); setNote("");
    api.get(`/followup?target_type=${target.target_type}&target_id=${target.target_id}`).then((r) => setStorico(r.data)).catch(() => setStorico([]));
  }, [target]);

  if (!target) return null;
  const needsDate = esito === "non_risponde" || esito === "richiamare";

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/followup", { target_type: target.target_type, target_id: target.target_id, motivo: target.motivo, esito, richiamare_il: needsDate ? data : null, note });
      toast.success(needsDate ? `Segnato: richiamare il ${fmtDate(data)}` : "Esito registrato");
      onSaved?.(); onClose();
    } catch (err) { toast.error(apiError(err)); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md" data-testid="contatto-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl">Esito contatto</DialogTitle></DialogHeader>
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
          <p className="font-medium text-slate-900" data-testid="contatto-target">{target.label}</p>
          <p className="text-xs text-slate-500">{MOTIVI[target.motivo] || target.motivo}{target.dettaglio ? ` · ${target.dettaglio}` : ""}{target.telefono ? ` · ${target.telefono}` : ""}</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 gap-2" data-testid="contatto-esiti">
            {Object.entries(ESITI).map(([k, v]) => (
              <label key={k} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${esito === k ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 hover:bg-slate-50"}`}>
                <input type="radio" name="esito" value={k} checked={esito === k} onChange={() => setEsito(k)} className="sr-only" data-testid={`contatto-esito-${k}`} />
                <v.icon className="h-4 w-4" /> {v.label}
              </label>
            ))}
          </div>
          {needsDate && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Richiamare il</Label>
              <div className="flex gap-2">
                <Input type="date" required value={data} onChange={(e) => setData(e.target.value)} data-testid="contatto-data" />
                {[1, 2, 7].map((n) => <Button key={n} type="button" variant="outline" size="sm" onClick={() => setData(plusDays(n))} data-testid={`contatto-plus-${n}`}>+{n}g</Button>)}
              </div>
            </div>
          )}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Note</Label>
            <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="es. richiamare dopo le 18, preferisce WhatsApp..." data-testid="contatto-note" />
          </div>
          {storico.length > 0 && (
            <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-slate-100 p-2 text-xs" data-testid="contatto-storico">
              <p className="font-semibold text-slate-500">Tentativi precedenti</p>
              {storico.map((s) => (
                <p key={s.id} className="text-slate-600">{fmtDate(s.created_at)} · {ESITI[s.esito]?.short || s.esito}{s.richiamare_il ? ` → ${fmtDate(s.richiamare_il)}` : ""} · {s.user_name}{s.note ? ` — ${s.note}` : ""}</p>
              ))}
            </div>
          )}
          <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
            <Button type="button" variant="outline" onClick={onClose}>Annulla</Button>
            <Button type="submit" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="contatto-submit">Salva esito</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
