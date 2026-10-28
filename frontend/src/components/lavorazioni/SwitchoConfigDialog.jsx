import { useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Checkbox } from "../ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";

export const SwitchoConfigDialog = ({ trigger }) => {
  const [open, setOpen] = useState(false);
  const [cfg, setCfg] = useState(null);
  const [snippet, setSnippet] = useState(null);
  const load = () => {
    api.get("/switcho/config").then((r) => setCfg(r.data)).catch((e) => toast.error(apiError(e)));
    api.get("/switcho/snippet").then((r) => setSnippet(r.data)).catch(() => {});
  };
  const save = async () => {
    try {
      await api.put("/switcho/config", { gruppo_jid: cfg.gruppo_jid, mittente: cfg.mittente, session_risposta: cfg.session_risposta, auto_avviso_cliente: cfg.auto_avviso_cliente, attivo: cfg.attivo });
      toast.success("Impostazioni Switcho salvate"); setOpen(false);
    } catch (e) { toast.error(apiError(e)); }
  };
  const set = (k, v) => setCfg((c) => ({ ...c, [k]: v }));
  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (o) load(); }}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-2xl" data-testid="switcho-config-dialog">
        <DialogHeader><DialogTitle>Impostazioni gruppo Switcho</DialogTitle></DialogHeader>
        {cfg && (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-slate-500">Messaggi ricevuti finora: <b>{cfg.messaggi_ricevuti}</b>{cfg.ultimo_messaggio ? ` · ultimo: ${cfg.ultimo_messaggio.at?.slice(0, 16).replace("T", " ")} (${cfg.ultimo_messaggio.origine})` : " · nessuno"}</p>
            <label className="block"><span className="text-xs font-semibold text-slate-600">ID gruppo WhatsApp (…@g.us) — vuoto = accetta qualsiasi gruppo</span><Input value={cfg.gruppo_jid} onChange={(e) => set("gruppo_jid", e.target.value)} data-testid="switcho-cfg-gruppo" /></label>
            <label className="block"><span className="text-xs font-semibold text-slate-600">Numero di Switcho che scrive nel gruppo</span><Input value={cfg.mittente} onChange={(e) => set("mittente", e.target.value)} data-testid="switcho-cfg-mittente" /></label>
            <label className="block"><span className="text-xs font-semibold text-slate-600">Sessione per rispondere (vuoto = negozio Sondrio)</span><Input value={cfg.session_risposta} onChange={(e) => set("session_risposta", e.target.value)} data-testid="switcho-cfg-sessione" /></label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.auto_avviso_cliente} onCheckedChange={(v) => set("auto_avviso_cliente", !!v)} /> WhatsApp automatico al cliente (dal suo negozio) quando Switcho chiede di confermare il link</label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.attivo} onCheckedChange={(v) => set("attivo", !!v)} /> Integrazione attiva (ricezione dal gruppo)</label>
            <Button onClick={save} className="w-full" data-testid="switcho-cfg-save">Salva</Button>
            {snippet && (
              <details className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                <summary className="cursor-pointer text-xs font-semibold text-slate-600">Codice per il microservizio WhatsApp (Railway) — da aggiungere una volta</summary>
                <p className="mt-1 text-xs text-slate-500">{snippet.istruzioni}</p>
                <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-900 p-2 text-[10px] text-slate-100">{snippet.codice}</pre>
                <Button size="sm" variant="outline" className="mt-1 h-7 text-xs" onClick={() => { navigator.clipboard.writeText(snippet.codice); toast.success("Copiato"); }}>Copia codice</Button>
              </details>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
