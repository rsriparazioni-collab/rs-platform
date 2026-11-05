import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Share2 } from "lucide-react";
import api, { apiError } from "../lib/api";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";
import { fmtDate } from "../lib/constants";

const CAMPI = [
  { key: "msg_cambiaora", marchio: "cambiaora", label: "CambiaOra – contratti luce/gas (non Enel)", hint: "Dal numero CambiaOra, 7 giorni dopo la data contratto" },
  { key: "msg_rs", marchio: "rs", label: "RS Riparazioni – riparazioni, SIM, vendite, ritiri, Enel", hint: "Dal numero del negozio, 7 giorni dopo la chiusura" },
];

export default function SocialFollowupPanel() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get("/social-followup").then((r) => { setData(r.data); setForm(r.data.settings); }).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const salva = async (patch) => {
    setBusy(true);
    try {
      const r = await api.put("/social-followup", patch);
      setForm(r.data.settings);
      setData((d) => ({ ...d, settings: r.data.settings }));
      toast.success("Impostazioni social salvate");
    } catch (e) { toast.error(apiError(e, "Salvataggio fallito")); } finally { setBusy(false); }
  };

  const inviaOra = async () => {
    if (!window.confirm(`Invio adesso fino a ${form.per_giorno} messaggi per marchio ai clienti in coda. Confermi?`)) return;
    setBusy(true);
    try {
      const r = await api.post("/social-followup/invia-ora");
      toast.success(`CambiaOra: ${r.data.cambiaora?.inviati ?? 0} inviati · RS: ${r.data.rs?.inviati ?? 0} inviati`);
      load();
    } catch (e) { toast.error(apiError(e, "Invio fallito")); } finally { setBusy(false); }
  };

  if (!data) return null;
  const s = data.settings;
  return (
    <div className="rounded-xl border border-pink-200 bg-pink-50/40 p-5 shadow-sm" data-testid="social-followup-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" onClick={() => setOpen((o) => !o)} className="flex items-center gap-3 text-left" data-testid="social-followup-toggle">
          <Share2 className="h-5 w-5 text-pink-600" />
          <div>
            <h2 className="font-heading text-lg font-semibold text-slate-800">Seguici sui social (7 giorni dopo)</h2>
            <p className="text-xs text-slate-500">
              In coda: CambiaOra {data.in_coda.cambiaora} · RS {data.in_coda.rs} · {s.per_giorno} al giorno per marchio
              {data.ultimo_giro?.last_run && <> · ultimo giro {fmtDate(data.ultimo_giro.last_run)}</>}
            </p>
          </div>
        </button>
        <div className="flex items-center gap-2" data-testid="social-followup-attivo-wrap">
          <span className={`text-xs font-semibold ${s.attivo ? "text-emerald-700" : "text-slate-500"}`}>{s.attivo ? "Acceso" : "Spento"}</span>
          <Switch checked={s.attivo} disabled={busy} onCheckedChange={(v) => salva({ attivo: v })} data-testid="social-followup-attivo" />
        </div>
      </div>
      {open && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wide text-slate-600">Messaggi al giorno per marchio (max 10)</Label>
              <input type="number" min={1} max={10} value={form.per_giorno ?? 5} data-testid="social-followup-per-giorno"
                     onChange={(e) => setForm((f) => ({ ...f, per_giorno: Number(e.target.value) }))}
                     className="h-9 w-24 rounded-md border border-slate-200 px-3 text-sm" />
            </div>
            <Button type="button" variant="outline" size="sm" onClick={inviaOra} disabled={busy} data-testid="social-followup-invia-ora">
              Invia ora il giro di oggi
            </Button>
          </div>
          {CAMPI.map((c) => (
            <div key={c.key} className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wide text-slate-600">{c.label}</Label>
              <Textarea rows={6} value={form[c.key] || ""} onChange={(e) => setForm((f) => ({ ...f, [c.key]: e.target.value }))} data-testid={`social-${c.key}`} />
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-500">{c.hint}. Usa {"{nome}"} per il nome del cliente.</p>
                <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" data-testid={`social-reset-${c.key}`}
                        onClick={() => setForm((f) => ({ ...f, [c.key]: data.defaults[c.key] }))}>Ripristina standard</Button>
              </div>
              {data.prossimi[c.marchio]?.length > 0 && (
                <p className="text-xs text-slate-500" data-testid={`social-prossimi-${c.marchio}`}>
                  Prossimi: {data.prossimi[c.marchio].map((p) => `${p.client_name} (${fmtDate(p.data)})`).join(" · ")}
                </p>
              )}
            </div>
          ))}
          <Button type="button" onClick={() => salva({ per_giorno: form.per_giorno, msg_cambiaora: form.msg_cambiaora, msg_rs: form.msg_rs })}
                  disabled={busy} data-testid="social-followup-save" className="bg-slate-900 hover:bg-slate-800">
            {busy ? "Salvo..." : "Salva testi e quantità"}
          </Button>
          {data.ultimi.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-3" data-testid="social-followup-ultimi">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Ultimi invii</p>
              <ul className="space-y-0.5 text-xs text-slate-600">
                {data.ultimi.map((l) => (
                  <li key={l.id}>{fmtDate(l.at)} · {l.marchio === "rs" ? "RS" : "CambiaOra"} · {l.client_name} · {l.ok ? "inviato" : `errore: ${l.error}`}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
