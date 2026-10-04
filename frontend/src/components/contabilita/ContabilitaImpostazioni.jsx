import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";
import { AccessiContabilita } from "./AccessiContabilita";

export const ContabilitaImpostazioni = ({ meta, storeId, reload }) => {
  const store = meta.stores.find((s) => s.id === storeId);
  const [f, setF] = useState(store?.config || {});
  const [log, setLog] = useState([]);
  useEffect(() => { setF(store?.config || {}); }, [store]);
  useEffect(() => { api.get("/contabilita/log").then((r) => setLog(r.data)).catch(() => {}); }, [storeId]);
  const salva = async () => {
    try { await api.patch(`/contabilita/config/${storeId}`, f); toast.success("Impostazioni salvate"); reload(); } catch (e) { toast.error(apiError(e)); }
  };
  if (!store) return null;
  const Row = ({ label, hint, children }) => <div className="grid gap-1 sm:grid-cols-[220px_1fr] sm:items-center"><div><p className="text-sm font-medium text-slate-800">{label}</p>{hint && <p className="text-xs text-slate-500">{hint}</p>}</div>{children}</div>;
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_380px]" data-testid="impostazioni-panel">
      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-900">Invii automatici — {store.nome}</h3>
        <Row label="WhatsApp giornaliero (19:00)" hint={`Numero destinatario; parte dal WhatsApp del negozio. Amministrazione: ${meta.numero_amministrazione}`}>
          <div className="flex items-center gap-3"><Input value={f.wa_numero || ""} onChange={(e) => setF({ ...f, wa_numero: e.target.value })} placeholder="es. 3792773557" data-testid="cfg-wa-numero" /><Switch checked={f.wa_attivo !== false} onCheckedChange={(v) => setF({ ...f, wa_attivo: v })} data-testid="cfg-wa-attivo" /></div>
        </Row>
        <Row label="Email mensile — destinatario" hint="Il 1° del mese, PDF completo del mese precedente">
          <div className="flex items-center gap-3"><Input value={f.email_to || ""} onChange={(e) => setF({ ...f, email_to: e.target.value })} placeholder="commercialista@studio.it" data-testid="cfg-email-to" /><Switch checked={f.email_attivo !== false} onCheckedChange={(v) => setF({ ...f, email_attivo: v })} data-testid="cfg-email-attivo" /></div>
        </Row>
        <Row label="Email mensile — mittente" hint="Usato come nome mittente e indirizzo di risposta">
          <Input value={f.email_from || ""} onChange={(e) => setF({ ...f, email_from: e.target.value })} placeholder="rscontabilita@gmail.com" data-testid="cfg-email-from" />
        </Row>
        <Row label="Condividi con l'amministrazione" hint="Se disattivo, l'amministratore vede solo che il negozio è attivo, non gli importi">
          <Switch checked={!!f.condividi_admin} onCheckedChange={(v) => setF({ ...f, condividi_admin: v })} data-testid="cfg-condividi" />
        </Row>
        <div className="flex justify-end"><Button onClick={salva} data-testid="cfg-salva">Salva impostazioni</Button></div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white" data-testid="contabilita-log">
        <h3 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">Ultimi invii</h3>
        <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto text-xs">
          {log.map((l) => (
            <li key={l.id} className="px-4 py-2">
              <p className="font-medium text-slate-700">{l.tipo === "wa_giornaliero" ? `WhatsApp ${l.giorno}` : l.tipo === "wa_fine_mese" ? `Avviso fine mese ${l.giorno}` : `Email ${l.mese}/${l.anno} → ${l.to}`}</p>
              <p className="text-slate-500">{l.tipo === "wa_giornaliero" ? (l.esiti || []).map((e) => `${e.negozi.join("+")} → ${e.numero} ${e.ok ? "✓" : "✗ " + (e.error || "")}`).join(" | ") || "nessun negozio configurato" : l.tipo === "wa_fine_mese" ? (l.esiti || []).map((e) => e.skip || `${e.negozio} ${e.da_versare}€ ${e.ok ? "✓" : "✗ " + (e.error || "")}`).join(" | ") || "nessun negozio con non versato" : `da ${l.from || "-"} · ${new Date(l.at).toLocaleString("it-IT")}`}</p>
            </li>
          ))}
          {!log.length && <li className="px-4 py-3 text-slate-400">Nessun invio registrato</li>}
        </ul>
      </div>
      {meta.is_admin && <AccessiContabilita />}
    </div>
  );
};
