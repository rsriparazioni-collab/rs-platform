import { useCallback, useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { MessageCircle, CheckCircle2, XCircle, RefreshCw, Store, QrCode } from "lucide-react";
import api from "../lib/api";
import { fmtDateTime } from "../lib/constants";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";

export default function WhatsApp() {
  const { user } = useAuth();
  const seesAll = user?.role === "admin" || user?.can_view_all;
  const [sessions, setSessions] = useState([]);
  const [dryRun, setDryRun] = useState(null);
  const [stores, setStores] = useState([]);
  const [openQr, setOpenQr] = useState(null);
  const [qrValue, setQrValue] = useState(null);
  const [pair, setPair] = useState({});
  const [down, setDown] = useState(false);
  const [waLog, setWaLog] = useState([]);

  const storeName = (sid) => {
    if (sid === "default") return "Principale";
    return stores.find((s) => s.id === sid)?.nome || (sid === "enel-deborah" ? "ENEL – Deborah" : sid ? sid.slice(0, 8) : "-");
  };

  const poll = useCallback(async () => {
    try {
      const res = await api.get("/whatsapp/status");
      setSessions(res.data.sessions || []);
      setDown(false);
      if (user?.role === "admin") api.get("/whatsapp/log").then((r) => setWaLog(r.data)).catch(() => {});
      if (openQr) {
        const qrRes = await api.get("/whatsapp/qr", { params: { session: openQr } });
        setQrValue(qrRes.data.qr || null);
        if (qrRes.data.connected) setOpenQr(null);
      }
    } catch {
      setDown(true);
    }
  }, [openQr, user?.role]);

  useEffect(() => {
    api.get("/meta").then((r) => setStores(r.data.stores || [])).catch(() => {});
    if (user?.role === "admin") api.get("/whatsapp/dry-run").then((r) => setDryRun(r.data.dry_run)).catch(() => {});
  }, [user?.role]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [poll]);

  const setPairField = (id, fields) =>
    setPair((s) => ({ ...s, [id]: { ...(s[id] || {}), ...fields } }));

  const requestPair = async (sessionId) => {
    const p = pair[sessionId] || {};
    setPairField(sessionId, { loading: true, error: "", code: null });
    try {
      const res = await api.post("/whatsapp/pair", { phone: p.phone || "", session: sessionId });
      setPairField(sessionId, { loading: false, code: res.data.code });
    } catch (e) {
      setPairField(sessionId, { loading: false, error: e.response?.data?.detail || "Richiesta codice fallita, riprova" });
    }
  };

  const sessionFor = (id) => sessions.find((s) => s.session === id);
  const tid = (id) => (id === "default" ? "default" : id.slice(0, 8));

  const cards = [
    ...(seesAll ? [
      { id: "default", nome: "Principale (fallback)", desc: "Usato quando il numero del negozio non è collegato" },
      { id: "enel-deborah", nome: "ENEL – Deborah", desc: "Numero per i clienti ENEL (privacy, recensione, anti-truffa). Gravedona usa il proprio numero" },
    ] : []),
    ...stores.map((s) => ({ id: s.id, nome: s.nome, desc: s.nome === "Sondrio" ? "Numero del negozio + tutti i messaggi energia CambiaOra (3519460591)" : "Numero WhatsApp del negozio" })),
  ];

  return (
    <div className="space-y-6" data-testid="whatsapp-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">WhatsApp</h1>
        <p className="mt-1 text-sm text-slate-500">
          Energia CambiaOra: sempre dal numero Sondrio (3519460591). Energia ENEL: dal numero di Deborah (o Gravedona). Riparazioni/telefonia: dal numero del negozio
        </p>
      </div>

      {down && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700" data-testid="whatsapp-service-down">
          Servizio WhatsApp non raggiungibile. Riprova tra poco.
        </div>
      )}
      {dryRun !== null && user?.role === "admin" && (
        <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 text-sm ${dryRun ? "border-amber-300 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`} data-testid="whatsapp-dry-run-banner">
          <span>{dryRun ? "MODALITÀ TEST attiva: i messaggi vengono solo registrati, NON inviati ai clienti." : "Invio reale attivo: i messaggi partono davvero verso i clienti."}</span>
          <Button size="sm" variant="outline" data-testid="whatsapp-dry-run-toggle"
                  onClick={async () => { const r = await api.put("/whatsapp/dry-run", { value: !dryRun }); setDryRun(r.data.dry_run); }}>
            {dryRun ? "Attiva invio reale" : "Passa a modalità test"}
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((c) => {
          const sess = sessionFor(c.id);
          const connected = sess?.connected;
          const p = pair[c.id] || {};
          return (
            <div key={c.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`wa-card-${tid(c.id)}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {c.id === "default"
                    ? <MessageCircle className="h-4 w-4 text-emerald-600" />
                    : <Store className="h-4 w-4 text-sky-600" />}
                  <p className="font-heading text-base font-semibold text-slate-900">{c.nome}</p>
                </div>
                {connected ? (
                  <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300" data-testid={`wa-status-${tid(c.id)}`}>
                    <CheckCircle2 className="h-3 w-3" /> Connesso
                  </span>
                ) : (
                  <span className="status-badge bg-amber-500/15 text-amber-700 border-amber-300" data-testid={`wa-status-${tid(c.id)}`}>
                    <XCircle className="h-3 w-3" /> Non connesso
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500">{c.desc}</p>

              {connected ? (
                <p className="mt-3 text-sm text-slate-600" data-testid={`wa-number-${tid(c.id)}`}>
                  Numero: <strong>+{sess.user?.id?.split(":")[0] || "attivo"}</strong>
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="gap-1.5"
                            onClick={() => setOpenQr(openQr === c.id ? null : c.id)} data-testid={`wa-qr-button-${tid(c.id)}`}>
                      <QrCode className="h-3.5 w-3.5" /> {openQr === c.id ? "Nascondi QR" : "Mostra QR"}
                    </Button>
                  </div>
                  {openQr === c.id && (
                    <div className="text-center" data-testid={`wa-qr-box-${tid(c.id)}`}>
                      {qrValue ? (
                        <div className="inline-block rounded-xl border border-slate-200 bg-white p-3">
                          <QRCode value={qrValue} size={180} />
                        </div>
                      ) : (
                        <p className="text-xs text-slate-500">Generazione QR in corso...</p>
                      )}
                      <p className="mt-2 text-xs text-slate-500">WhatsApp → Dispositivi collegati → Collega un dispositivo</p>
                    </div>
                  )}
                  <div className="rounded-lg border border-slate-200 p-3">
                    <p className="text-xs font-medium text-slate-700">Oppure collega con codice numerico:</p>
                    <div className="mt-2 flex gap-2">
                      <input className="flex-1 rounded-md border border-slate-300 px-2.5 py-1.5 text-sm"
                             placeholder="es. 393519460591" value={p.phone || ""}
                             onChange={(e) => setPairField(c.id, { phone: e.target.value })}
                             data-testid={`wa-pair-phone-${tid(c.id)}`} />
                      <Button size="sm" onClick={() => requestPair(c.id)} disabled={p.loading} data-testid={`wa-pair-button-${tid(c.id)}`}>
                        {p.loading ? "Attendi..." : "Genera codice"}
                      </Button>
                    </div>
                    {p.code && (
                      <div className="mt-2 rounded-lg bg-emerald-50 p-2.5 text-center" data-testid={`wa-pair-code-${tid(c.id)}`}>
                        <p className="font-mono text-xl font-bold tracking-[0.25em] text-emerald-800">{p.code}</p>
                        <p className="mt-1 text-[11px] text-slate-600">
                          WhatsApp → Dispositivi collegati → Collega → <strong>Collega con numero di telefono</strong>
                        </p>
                      </div>
                    )}
                    {p.error && <p className="mt-1.5 text-xs text-rose-600" data-testid={`wa-pair-error-${tid(c.id)}`}>{p.error}</p>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {waLog.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="whatsapp-log">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="font-heading text-lg font-semibold text-slate-800">Ultimi invii</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {waLog.slice(0, 10).map((l, i) => (
              <div key={`${l.at}-${l.phone}-${l.session}`} className="flex items-center justify-between px-5 py-2.5 text-sm" data-testid={`wa-log-${i}`}>
                <div className="flex items-center gap-3">
                  <span className={`status-badge ${l.ok ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-rose-500/15 text-rose-700 border-rose-300"}`}>
                    {l.ok ? "Inviato" : "Fallito"}
                  </span>
                  <div>
                    <p className="font-medium text-slate-900">+{l.phone} · {storeName(l.session)}</p>
                    <p className="max-w-md truncate text-xs text-slate-500">{l.error || l.message}</p>
                  </div>
                </div>
                <span className="text-xs text-slate-400">{fmtDateTime(l.at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-center">
        <Button variant="outline" size="sm" onClick={poll} className="gap-2" data-testid="whatsapp-refresh-button">
          <RefreshCw className="h-4 w-4" /> Aggiorna stato
        </Button>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800" data-testid="whatsapp-info-box">
        <strong>Come funziona:</strong> dalla scheda cliente premi "Invia link privacy" — il messaggio parte dal numero del
        negozio del cliente (se collegato), altrimenti dal numero principale. Dopo 5 minuti il sistema invia in automatico
        la richiesta di recensione Google. Collega ogni numero una sola volta: la sessione resta salvata sul server.
      </div>
    </div>
  );
}
