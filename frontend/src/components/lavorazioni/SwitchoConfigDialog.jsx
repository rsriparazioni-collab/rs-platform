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
  const [gruppi, setGruppi] = useState(null);
  const [log, setLog] = useState(null);
  const cercaGruppi = () => api.get("/switcho/gruppi").then((r) => setGruppi(r.data.groups || [])).catch((e) => toast.error(apiError(e)));
  const load = () => {
    api.get("/switcho/config").then((r) => setCfg(r.data)).catch((e) => toast.error(apiError(e)));
    api.get("/switcho/snippet").then((r) => setSnippet(r.data)).catch(() => {});
    api.get("/switcho/inbox-log").then((r) => setLog(r.data)).catch(() => {});
  };
  const save = async () => {
    try {
      await api.put("/switcho/config", { gruppo_jid: cfg.gruppo_jid, mittente: cfg.mittente, session_risposta: cfg.session_risposta, auto_avviso_cliente: cfg.auto_avviso_cliente, attivo: cfg.attivo, ignora_mittenti: cfg.ignora_mittenti || "", auto_risposta_gruppo: cfg.auto_risposta_gruppo !== false, auto_documenti_gruppo: cfg.auto_documenti_gruppo !== false, avviso_silenzio: cfg.avviso_silenzio !== false, grazie_documenti: cfg.grazie_documenti !== false });
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
            <label className="block"><span className="text-xs font-semibold text-slate-600">ID gruppo WhatsApp (…@g.us) — vuoto = accetta qualsiasi gruppo</span>
              <div className="flex gap-1.5"><Input value={cfg.gruppo_jid} onChange={(e) => set("gruppo_jid", e.target.value)} data-testid="switcho-cfg-gruppo" />
                <Button type="button" variant="outline" size="sm" className="h-9 shrink-0 text-xs" onClick={cercaGruppi} data-testid="switcho-cfg-gruppi-btn">Trova gruppi</Button></div>
              {gruppi && (
                <div className="mt-1 max-h-32 space-y-0.5 overflow-y-auto rounded border border-slate-200 p-1">
                  {gruppi.length === 0 && <p className="text-xs text-slate-400">Nessun gruppo su questo numero</p>}
                  {gruppi.map((g) => <button type="button" key={g.id} className="block w-full rounded px-2 py-1 text-left text-xs hover:bg-sky-50" onClick={() => { set("gruppo_jid", g.id); setGruppi(null); }}><b>{g.nome}</b> <span className="text-slate-400">· {g.partecipanti} membri · {g.id}</span></button>)}
                </div>
              )}
            </label>
            <label className="block"><span className="text-xs font-semibold text-slate-600">Numero di Switcho che scrive nel gruppo</span><Input value={cfg.mittente} onChange={(e) => set("mittente", e.target.value)} data-testid="switcho-cfg-mittente" /></label>
            <label className="block"><span className="text-xs font-semibold text-slate-600">Da ignorare: nostri numeri, LID o nomi WhatsApp che rispondono nel gruppo (separati da virgola)</span><Input value={cfg.ignora_mittenti || ""} onChange={(e) => set("ignora_mittenti", e.target.value)} placeholder="es. 3519460591, Deborah, 1234567890123" data-testid="switcho-cfg-ignora" /><span className="text-[11px] text-slate-400">I numeri dei negozi collegati al servizio WhatsApp vengono già esclusi in automatico; qui aggiungi i cellulari personali. Nella diagnostica sotto c'è il tasto "Ignora" accanto a ogni messaggio.</span></label>
            <label className="block"><span className="text-xs font-semibold text-slate-600">Sessione per rispondere (vuoto = negozio Sondrio)</span><Input value={cfg.session_risposta} onChange={(e) => set("session_risposta", e.target.value)} data-testid="switcho-cfg-sessione" /></label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.auto_avviso_cliente} onCheckedChange={(v) => set("auto_avviso_cliente", !!v)} /> WhatsApp automatico al cliente (dal suo negozio) quando Switcho chiede di confermare il link</label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.attivo} onCheckedChange={(v) => set("attivo", !!v)} /> Integrazione attiva (ricezione dal gruppo)</label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.auto_risposta_gruppo !== false} onCheckedChange={(v) => set("auto_risposta_gruppo", !!v)} data-testid="switcho-cfg-auto-risposta" /> Risposta automatica nel gruppo dal numero Sondrio ("Ricevuto, avvisiamo il cliente…") quando la richiesta è stata gestita</label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.auto_documenti_gruppo !== false} onCheckedChange={(v) => set("auto_documenti_gruppo", !!v)} data-testid="switcho-cfg-auto-documenti" /> Se Switcho chiede bollette/documenti già caricati nella scheda cliente, allegali da sola alla risposta nel gruppo</label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.avviso_silenzio !== false} onCheckedChange={(v) => set("avviso_silenzio", !!v)} data-testid="switcho-cfg-silenzio" /> Avvisami su WhatsApp alle 9:30 (lun-sab) se dal gruppo non è arrivato nulla dall'ultimo giorno lavorativo</label>
            <label className="flex items-center gap-2"><Checkbox checked={cfg.grazie_documenti !== false} onCheckedChange={(v) => set("grazie_documenti", !!v)} data-testid="switcho-cfg-grazie" /> "Grazie, bolletta ricevuta" automatico dal negozio quando un cliente manda foto/PDF su WhatsApp (una volta ogni 10 minuti)</label>
            <Button onClick={save} className="w-full" data-testid="switcho-cfg-save">Salva</Button>
            <div className="rounded-lg border border-slate-200 p-2" data-testid="switcho-inbox-log">
              <div className="text-xs font-semibold text-slate-600">Diagnostica ricezione — ultimi messaggi arrivati dal servizio WhatsApp {log && <span className="font-normal text-slate-400">· {log.totale_ok} elaborati · {log.totale_ignorati} ignorati</span>}</div>
              {!log || log.items.length === 0 ? <p className="mt-1 text-xs text-amber-700">Nessun messaggio è mai arrivato dal servizio WhatsApp: controlla su Railway le variabili CRM_URL e CRM_WEBHOOK_SECRET e che il numero Sondrio sia nel gruppo.</p> : (
                <div className="mt-1 max-h-40 space-y-1 overflow-y-auto">
                  {log.items.map((l) => <div key={l.id} className={`rounded px-2 py-1 text-[11px] ${l.esito === "ok" ? "bg-emerald-50 text-emerald-900" : "bg-rose-50 text-rose-900"}`}><b>{l.at?.slice(0, 16).replace("T", " ")}</b> · {l.esito === "ok" ? `${l.segnalazioni} segnalazioni${l.azioni?.length ? ` — ${l.azioni.join("; ")}` : ""}${l.risposta_gruppo ? (l.risposta_gruppo.ok ? ` — risposto nel gruppo: «${l.risposta_gruppo.testo}»` : ` — risposta al gruppo FALLITA: ${l.risposta_gruppo.errore}`) : ""}` : `ignorato: ${l.motivo}`} <span className="text-slate-500">· da {l.push_name || l.sender_pn || l.sender}{l.lid ? " (LID)" : ""} · gruppo {l.group_id}</span>{l.esito === "ok" && <button type="button" className="ml-1 rounded border border-slate-300 px-1 text-[10px] hover:bg-white" title="Aggiungi questo mittente all'elenco da ignorare" onClick={() => set("ignora_mittenti", [cfg.ignora_mittenti, l.sender_pn || l.sender].filter(Boolean).join(", "))} data-testid="switcho-log-ignora">Ignora</button>}<div className="truncate text-slate-600">{l.testo}</div></div>)}
                </div>
              )}
            </div>
            {snippet && (
              <details className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                <summary className="cursor-pointer text-xs font-semibold text-slate-600">Istruzioni Railway (il codice del servizio è già aggiornato nel progetto)</summary>
                <p className="mt-1 text-xs text-slate-500">{snippet.istruzioni}</p>
                <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-900 p-2 text-[10px] text-slate-100">{snippet.codice}</pre>
                <Button size="sm" variant="outline" className="mt-1 h-7 text-xs" onClick={() => { navigator.clipboard.writeText(snippet.codice); toast.success("Copiato"); }}>Copia codice</Button>
                <Button size="sm" variant="outline" className="ml-1 mt-1 h-7 text-xs" data-testid="switcho-scarica-service" onClick={() => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([snippet.codice], { type: "text/javascript" })); a.download = "service.js"; a.click(); URL.revokeObjectURL(a.href); }}>Scarica service.js</Button>
              </details>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
