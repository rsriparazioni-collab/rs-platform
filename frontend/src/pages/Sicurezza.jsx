import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ShieldOff, Smartphone, Copy, KeyRound } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { fmtDate } from "../lib/constants";

export default function Sicurezza() {
  const { user, setUser } = useAuth();
  const [status, setStatus] = useState(null);
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(null);
  const [disable, setDisable] = useState({ password: "", code: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get("/auth/2fa/status").then((r) => setStatus(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const begin = async () => {
    setBusy(true);
    try { setSetup((await api.post("/auth/2fa/enroll")).data); setCode(""); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const confirm = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post("/auth/2fa/enroll/confirm", { code });
      setRecovery(r.data.recovery_codes); setSetup(null); load();
      setUser((u) => ({ ...u, totp_enabled: true }));
      toast.success("Autenticazione a due fattori attivata");
    } catch (err) { toast.error(apiError(err, "Codice non valido")); } finally { setBusy(false); }
  };

  const doDisable = async (e) => {
    e.preventDefault();
    if (!window.confirm("Disattivare la verifica in due passaggi? L'account sarà meno protetto.")) return;
    setBusy(true);
    try {
      await api.post("/auth/2fa/disable", disable);
      setDisable({ password: "", code: "" }); setRecovery(null); load();
      toast.success("Autenticazione a due fattori disattivata");
    } catch (err) { toast.error(apiError(err, "Password o codice non validi")); } finally { setBusy(false); }
  };

  const copyCodes = () => { navigator.clipboard?.writeText(recovery.join("\n")); toast.success("Codici copiati"); };

  return (
    <div className="max-w-3xl space-y-6" data-testid="sicurezza-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Sicurezza account</h1>
        <p className="mt-1 text-sm text-slate-500">{user.name} · {user.email}</p>
      </div>

      {!status?.enabled && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-5 py-4 text-sm text-amber-800" data-testid="2fa-mandatory-banner">
          <b>La verifica in due passaggi è obbligatoria.</b> Per accedere al gestionale devi attivarla ora: bastano 2 minuti con l'app Authenticator sul telefono.
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="2fa-card">
        <div className="flex items-start gap-4">
          <div className={`rounded-xl p-3 ${status?.enabled ? "bg-emerald-500/15 text-emerald-700" : "bg-amber-500/15 text-amber-700"}`}>
            {status?.enabled ? <ShieldCheck className="h-6 w-6" /> : <ShieldOff className="h-6 w-6" />}
          </div>
          <div className="flex-1">
            <h2 className="font-heading text-lg font-semibold text-slate-900">Verifica in due passaggi (Authenticator)</h2>
            <p className="mt-1 text-sm text-slate-600">
              Oltre alla password ti verrà chiesto un codice a 6 cifre generato da Google Authenticator o Microsoft Authenticator sul tuo telefono.
              Protegge i dati dei clienti anche se la password venisse rubata.
            </p>
            <p className="mt-2 text-sm font-medium" data-testid="2fa-status">
              {status?.enabled
                ? <span className="text-emerald-700">Attiva dal {fmtDate(status.enabled_at)} · codici di recupero rimasti: {status.recovery_codes_left}</span>
                : <span className="text-amber-700">Non attiva</span>}
            </p>
          </div>
        </div>

        {!status?.enabled && !setup && !recovery && (
          <Button onClick={begin} disabled={busy} className="mt-5 gap-2 bg-slate-900 hover:bg-slate-800" data-testid="2fa-enable-button">
            <Smartphone className="h-4 w-4" /> Attiva con l'app Authenticator
          </Button>
        )}

        {setup && (
          <div className="mt-6 grid gap-6 md:grid-cols-[220px_1fr]" data-testid="2fa-setup">
            <img src={setup.qr_data_uri} alt="QR code Authenticator" className="h-[220px] w-[220px] rounded-lg border border-slate-200" data-testid="2fa-qr" />
            <div className="space-y-4">
              <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
                <li>Installa <b>Google Authenticator</b> o <b>Microsoft Authenticator</b> sul telefono.</li>
                <li>Tocca "+" → "Scansiona codice QR" e inquadra il codice.</li>
                <li>Inserisci qui sotto il codice a 6 cifre mostrato dall'app.</li>
              </ol>
              <p className="text-xs text-slate-500">Chiave manuale: <code className="rounded bg-slate-100 px-1" data-testid="2fa-manual-key">{setup.manual_key}</code></p>
              <form onSubmit={confirm} className="flex gap-2">
                <Input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)}
                       placeholder="123456" className="max-w-[160px] text-center tracking-widest" data-testid="2fa-confirm-code" />
                <Button type="submit" disabled={busy || code.length !== 6} data-testid="2fa-confirm-button">Conferma</Button>
                <Button type="button" variant="ghost" onClick={() => setSetup(null)} data-testid="2fa-cancel-button">Annulla</Button>
              </form>
            </div>
          </div>
        )}

        {recovery && (
          <div className="mt-6 rounded-lg border border-amber-300 bg-amber-50 p-4" data-testid="2fa-recovery">
            <p className="flex items-center gap-2 text-sm font-semibold text-amber-800"><KeyRound className="h-4 w-4" /> Salva ora i codici di recupero</p>
            <p className="mt-1 text-xs text-amber-700">Se perdi il telefono puoi entrare con uno di questi codici (ognuno vale una sola volta). Non verranno mostrati di nuovo.</p>
            <pre className="mt-3 grid grid-cols-2 gap-1 rounded bg-white p-3 font-mono text-sm text-slate-800" data-testid="2fa-recovery-codes">{recovery.map((c) => <span key={c}>{c}</span>)}</pre>
            <div className="mt-3 flex gap-2">
              <Button size="sm" variant="outline" onClick={copyCodes} className="gap-1" data-testid="2fa-copy-codes"><Copy className="h-3.5 w-3.5" /> Copia</Button>
              <Button size="sm" onClick={() => setRecovery(null)} data-testid="2fa-recovery-done">Ho salvato i codici</Button>
            </div>
          </div>
        )}

        {status?.enabled && !recovery && (
          <form onSubmit={doDisable} className="mt-6 space-y-3 border-t border-slate-200 pt-5" data-testid="2fa-disable-form">
            <p className="text-sm font-medium text-slate-700">Disattiva la verifica in due passaggi</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs">Password attuale</Label>
                <Input type="password" value={disable.password} onChange={(e) => setDisable({ ...disable, password: e.target.value })} data-testid="2fa-disable-password" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Codice Authenticator o di recupero</Label>
                <Input value={disable.code} onChange={(e) => setDisable({ ...disable, code: e.target.value })} data-testid="2fa-disable-code" />
              </div>
            </div>
            <Button type="submit" variant="outline" disabled={busy || !disable.password || !disable.code} className="border-rose-300 text-rose-700" data-testid="2fa-disable-button">
              Disattiva
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
