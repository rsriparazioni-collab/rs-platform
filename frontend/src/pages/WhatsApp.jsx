import { useCallback, useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { MessageCircle, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import api from "../lib/api";
import { Button } from "../components/ui/button";

export default function WhatsApp() {
  const [status, setStatus] = useState(null);
  const [qr, setQr] = useState(null);

  const poll = useCallback(async () => {
    try {
      const res = await api.get("/whatsapp/status");
      setStatus(res.data);
      if (res.data.connected) {
        setQr(null);
      } else {
        const qrRes = await api.get("/whatsapp/qr");
        setQr(qrRes.data.qr || null);
      }
    } catch {
      setStatus({ connected: false, service_down: true });
    }
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [poll]);

  return (
    <div className="space-y-6" data-testid="whatsapp-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">WhatsApp</h1>
        <p className="mt-1 text-sm text-slate-500">
          Collega il numero aziendale per inviare link privacy e richieste recensione
        </p>
      </div>

      <div className="max-w-lg rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm" data-testid="whatsapp-status-card">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
          <MessageCircle className="h-7 w-7 text-emerald-600" />
        </div>
        {status?.connected ? (
          <div className="mt-4">
            <span className="status-badge bg-emerald-500/15 text-emerald-700 border-emerald-300" data-testid="whatsapp-connected-badge">
              <CheckCircle2 className="h-3 w-3" /> Connesso
            </span>
            <p className="mt-3 text-sm text-slate-600">
              Numero collegato: <strong>{status.user?.id?.split(":")[0] || "attivo"}</strong>
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Puoi inviare i messaggi privacy e recensione dalla scheda di ogni cliente.
            </p>
          </div>
        ) : (
          <div className="mt-4">
            <span className="status-badge bg-amber-500/15 text-amber-700 border-amber-300" data-testid="whatsapp-disconnected-badge">
              <XCircle className="h-3 w-3" /> Non connesso
            </span>
            {qr ? (
              <div className="mt-5" data-testid="whatsapp-qr-container">
                <p className="mb-3 text-sm font-medium text-slate-700">Scansiona questo codice con WhatsApp:</p>
                <div className="inline-block rounded-xl border border-slate-200 bg-white p-4">
                  <QRCode value={qr} size={220} data-testid="whatsapp-qr-code" />
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  Apri WhatsApp sul telefono → Dispositivi collegati → Collega un dispositivo
                </p>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500" data-testid="whatsapp-qr-waiting">
                {status?.service_down
                  ? "Servizio WhatsApp non raggiungibile. Riprova tra poco."
                  : "In attesa del codice QR... il servizio si sta avviando."}
              </p>
            )}
            <Button variant="outline" size="sm" onClick={poll} className="mt-4 gap-2" data-testid="whatsapp-refresh-button">
              <RefreshCw className="h-4 w-4" /> Aggiorna stato
            </Button>
          </div>
        )}
      </div>

      <div className="max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800" data-testid="whatsapp-info-box">
        <strong>Come funziona:</strong> dalla scheda cliente premi "Invia link privacy" — il messaggio con il link di firma parte
        subito dal numero collegato, e dopo 5 minuti il sistema invia automaticamente la richiesta di recensione Google.
      </div>
    </div>
  );
}
