import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";

const CAMPI = [
  { key: "recensione_deborah", label: "Recensione ENEL – numero Deborah (Morbegno)", hint: "Inviata 2 minuti dopo la privacy ai clienti ENEL non di Gravedona" },
  { key: "recensione_gravedona", label: "Recensione ENEL – Gravedona", hint: "Inviata dal numero del negozio Gravedona ai suoi clienti ENEL" },
  { key: "truffe", label: "Anti-truffa ENEL", hint: "Inviato 10 giorni dopo l'attivazione. *testo* = grassetto, _testo_ = corsivo" },
];

export default function MessaggiEnelEditor() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/messaggi-enel").then((r) => { setData(r.data); setForm(r.data.messaggi); }).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/messaggi-enel", form);
      setForm(r.data.messaggi);
      toast.success("Testi ENEL salvati");
    } catch (e) {
      toast.error(apiError(e, "Salvataggio fallito"));
    } finally {
      setSaving(false);
    }
  };

  if (!data) return null;
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-5 shadow-sm" data-testid="messaggi-enel-editor">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between text-left" data-testid="messaggi-enel-toggle">
        <div>
          <h2 className="font-heading text-lg font-semibold text-slate-800">Testi WhatsApp ENEL</h2>
          <p className="text-xs text-slate-500">Recensione (Deborah / Gravedona) e anti-truffa per i clienti con gestione ENEL</p>
        </div>
        <span className="text-xs text-slate-500">{open ? "Nascondi" : "Modifica"}</span>
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          {CAMPI.map((c) => (
            <div key={c.key} className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wide text-slate-600">{c.label}</Label>
              <Textarea rows={5} value={form[c.key] || ""} onChange={(e) => setForm((f) => ({ ...f, [c.key]: e.target.value }))}
                        data-testid={`enel-${c.key}`} />
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-500">{c.hint}</p>
                <Button type="button" size="sm" variant="ghost" className="h-7 text-xs"
                        onClick={() => setForm((f) => ({ ...f, [c.key]: data.defaults[c.key] }))} data-testid={`enel-reset-${c.key}`}>
                  Ripristina standard
                </Button>
              </div>
            </div>
          ))}
          <Button type="button" onClick={save} disabled={saving} data-testid="enel-save-button" className="bg-slate-900 hover:bg-slate-800">
            {saving ? "Salvo..." : "Salva testi ENEL"}
          </Button>
        </div>
      )}
    </div>
  );
}
