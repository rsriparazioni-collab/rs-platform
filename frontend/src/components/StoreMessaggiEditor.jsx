import { useEffect, useState } from "react";
import api from "../lib/api";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";

const CAMPI = [
  { key: "msg_privacy", label: "Messaggio privacy", hint: "Inviato col link privacy" },
  { key: "msg_pronto", label: "Messaggio 'pronto per il ritiro'", hint: "Inviato quando la riparazione passa a Pronto" },
  { key: "msg_promemoria", label: "Promemoria ritiro (dopo 7 giorni)", hint: "Se il cliente non ritira entro 7 giorni dall'avviso" },
  { key: "msg_recensione", label: "Richiesta recensione", hint: "Inviata 2 minuti dopo la consegna del dispositivo" },
  { key: "msg_vincolo", label: "Scadenza vincolo telefonia (30 gg prima)", hint: "Per Mobile/Fisso con vincolo > 0 mesi" },
  { key: "msg_offerta_annuale", label: "Scadenza offerta annuale (30 gg prima)", hint: "Per Mobile/Fisso con vincolo 0: ogni anno dall'attivazione" },
  { key: "msg_rinnovo_energia", label: "Rinnovo contratto luce/gas (60 gg prima)", hint: "Inviato al 10° mese dall'attivazione del contratto energia" },
  { key: "msg_truffe", label: "Attenzione alle truffe (10 gg dopo attivazione)", hint: "Inviato una volta, 10 giorni dopo l'attivazione del contratto energia. *testo* = grassetto, _testo_ = corsivo" },
];

export default function StoreMessaggiEditor({ form, setForm }) {
  const [defaults, setDefaults] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/messaggi-default").then((r) => setDefaults(r.data)).catch(() => {});
  }, []);

  return (
    <div className="rounded-xl border border-slate-200 p-3" data-testid="store-messaggi-editor">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between text-left"
              data-testid="store-messaggi-toggle">
        <span className="text-sm font-semibold text-slate-800">Testi messaggi WhatsApp del negozio</span>
        <span className="text-xs text-slate-500">{open ? "Nascondi" : "Personalizza"}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-4">
          <p className="text-xs text-slate-500">
            Lascia vuoto per usare il testo standard. Segnaposto disponibili:{" "}
            {(defaults?.placeholders || []).map((p) => <code key={p} className="mr-1 rounded bg-slate-100 px-1">{p}</code>)}
          </p>
          {CAMPI.map((c) => (
            <div key={c.key} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{c.label}</Label>
                {defaults && (
                  <Button type="button" variant="ghost" size="sm" className="h-6 text-xs"
                          onClick={() => setForm({ ...form, [c.key]: defaults.defaults[c.key] })} data-testid={`store-msg-default-${c.key}`}>
                    Usa testo standard
                  </Button>
                )}
              </div>
              <Textarea rows={4} value={form[c.key] || ""} placeholder={defaults?.defaults[c.key] || ""}
                        onChange={(e) => setForm({ ...form, [c.key]: e.target.value })} data-testid={`store-msg-${c.key}`} />
              <p className="text-[11px] text-slate-400">{c.hint}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
