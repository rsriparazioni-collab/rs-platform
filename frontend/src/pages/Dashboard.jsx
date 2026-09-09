import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Users, RefreshCw, Wallet, FileText, Zap, Flame, BellRing, Mail, ArrowRight, Wrench, Smartphone, CalendarClock, Package, MessageCircle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { LAVORAZIONI, lavorazioneLabel, lavorazioneBadge, fmtDate } from "../lib/constants";
import { Button } from "../components/ui/button";

function Kpi({ icon: Icon, label, value, sub, color, testid }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={testid}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{label}</p>
        <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${color}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-2 font-heading text-3xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [scadenze, setScadenze] = useState(null);
  const [waStatus, setWaStatus] = useState(null);
  const [ferme, setFerme] = useState([]);
  const [margini, setMargini] = useState(null);
  const [meseMargini, setMeseMargini] = useState(new Date().toISOString().slice(0, 7));

  useEffect(() => {
    if (user.role !== "admin") return;
    api.get("/dashboard/margini-negozi", { params: { mese: meseMargini } }).then((r) => setMargini(r.data)).catch(() => {});
  }, [user.role, meseMargini]);
  const [sendingFerme, setSendingFerme] = useState(false);
  const [sending, setSending] = useState(false);

  const inviaFerme = async () => {
    setSendingFerme(true);
    try {
      const res = await api.post("/riparazioni-ferme/invia-ora");
      const ok = res.data.report.filter((r) => r.inviato).length;
      toast.success(`Avvisi inviati a ${ok} negozi`);
    } catch (e) {
      toast.error(apiError(e, "Invio avvisi fallito"));
    } finally {
      setSendingFerme(false);
    }
  };

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
    api.get("/alerts").then((r) => setAlerts(r.data)).catch(() => {});
    api.get("/scadenze-settimana").then((r) => setScadenze(r.data)).catch(() => {});
    api.get("/riparazioni-ferme").then((r) => setFerme(r.data)).catch(() => {});
    if (user.role === "admin") {
      api.get("/whatsapp/sessions-summary").then((r) => setWaStatus(r.data)).catch(() => {});
    }
  }, []);

  const sendDigest = async () => {
    setSending(true);
    try {
      const res = await api.post("/alerts/send-digest");
      toast.success(res.data.message || "Riepilogo email inviato");
    } catch (e) {
      toast.error(apiError(e, "Invio email fallito"));
    } finally {
      setSending(false);
    }
  };

  const totalAlerts = alerts
    ? alerts.rinnovi.length + alerts.pagamenti_clienti.length + alerts.pagamenti_negozi.length + (alerts.sotto_scorta?.length || 0)
    : 0;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">Panoramica utenze, rinnovi e pagamenti</p>
        </div>
        {user.role === "admin" && (
          <Button onClick={sendDigest} disabled={sending} data-testid="send-digest-button"
                  className="gap-2 bg-sky-600 hover:bg-sky-700">
            <Mail className="h-4 w-4" /> {sending ? "Invio..." : "Invia riepilogo email"}
          </Button>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
          <Kpi icon={Users} label="Clienti totali" value={stats.totale_clienti}
               sub={`${stats.contratti_mese} contratti questo mese`} color="bg-sky-100 text-sky-700" testid="kpi-clienti" />
          <Kpi icon={RefreshCw} label="Rinnovi entro 30gg" value={stats.rinnovi_30gg}
               sub="Finestra rinnovo 10 mesi" color="bg-amber-100 text-amber-700" testid="kpi-rinnovi" />
          <Kpi icon={Wallet} label="Non pagati" value={stats.non_pagati}
               sub="Incluso reset automatico a 6 mesi" color="bg-rose-100 text-rose-700" testid="kpi-non-pagati" />
          <Kpi icon={FileText} label="Luce / Gas" value={`${stats.luce} / ${stats.gas}`}
               sub="Divisione per tipo bolletta" color="bg-emerald-100 text-emerald-700" testid="kpi-tipo" />
          <Kpi icon={Wrench} label="Servizi attivi" value={stats.servizi_attivi ?? 0}
               sub="Riparazioni e telefonia aperte" color="bg-violet-100 text-violet-700" testid="kpi-servizi" />
          <Kpi icon={Smartphone} label="Vincoli in scadenza" value={stats.vincoli_60gg ?? 0}
               sub="Vincoli telefonia entro 60 giorni" color="bg-orange-100 text-orange-700" testid="kpi-vincoli" />
          {user.role === "admin" && waStatus && (
            <Kpi icon={MessageCircle} label="WhatsApp connessi"
                 value={waStatus.connessi === null ? "offline" : `${waStatus.connessi}/${waStatus.totale}`}
                 sub="Numeri collegati (negozi + principale)" color="bg-green-100 text-green-700" testid="kpi-whatsapp" />
          )}
        </div>
      )}

      {scadenze && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="scadenze-panel">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-sky-600" />
              <h2 className="font-heading text-lg font-semibold text-slate-800">Scadenze della settimana</h2>
            </div>
            <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-bold text-sky-800" data-testid="scadenze-count">
              {scadenze.totale}
            </span>
          </div>
          <div className="grid grid-cols-1 divide-y divide-slate-100 md:grid-cols-3 md:divide-x md:divide-y-0">
            <div className="p-4" data-testid="scadenze-rinnovi-section">
              <div className="mb-3 flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-600" />
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Rinnovi energia</p>
              </div>
              {scadenze.rinnovi.length === 0 && (
                <p className="py-3 text-center text-xs text-slate-400" data-testid="scadenze-rinnovi-empty">Nessun rinnovo entro 7 giorni</p>
              )}
              <div className="space-y-1">
                {scadenze.rinnovi.map((r) => (
                  <Link to="/clienti" key={r.client_id} data-testid={`scadenza-rinnovo-${r.client_id}`}
                        className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-50">
                    <div className="flex items-center gap-2">
                      {r.tipo_bolletta === "gas"
                        ? <Flame className="h-3.5 w-3.5 text-orange-500" />
                        : <Zap className="h-3.5 w-3.5 text-sky-500" />}
                      <div>
                        <p className="text-sm font-medium text-slate-900">{r.cognome} {r.nome}</p>
                        <p className="text-xs text-slate-500">Rinnovo: {fmtDate(r.data_rinnovo)}</p>
                      </div>
                    </div>
                    <span className={`text-xs font-bold ${r.giorni <= 2 ? "text-rose-600" : "text-amber-600"}`}>{r.giorni} gg</span>
                  </Link>
                ))}
              </div>
            </div>
            <div className="p-4" data-testid="scadenze-vincoli-section">
              <div className="mb-3 flex items-center gap-2">
                <Smartphone className="h-4 w-4 text-orange-600" />
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Vincoli telefonia</p>
              </div>
              {scadenze.vincoli.length === 0 && (
                <p className="py-3 text-center text-xs text-slate-400" data-testid="scadenze-vincoli-empty">Nessun vincolo in scadenza entro 7 giorni</p>
              )}
              <div className="space-y-1">
                {scadenze.vincoli.map((v) => (
                  <Link to="/telefonia" key={v.id} data-testid={`scadenza-vincolo-${v.id}`}
                        className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-50">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{v.client_name}</p>
                      <p className="text-xs text-slate-500">{v.operatore_tel}{v.numero ? ` · ${v.numero}` : ""} · scade {fmtDate(v.scadenza_vincolo)}</p>
                    </div>
                    <span className={`text-xs font-bold ${v.giorni <= 2 ? "text-rose-600" : "text-orange-600"}`}>{v.giorni} gg</span>
                  </Link>
                ))}
              </div>
            </div>
            <div className="p-4" data-testid="scadenze-riparazioni-section">
              <div className="mb-3 flex items-center gap-2">
                <Wrench className="h-4 w-4 text-emerald-600" />
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Riparazioni da consegnare</p>
              </div>
              {scadenze.riparazioni_pronte.length === 0 && (
                <p className="py-3 text-center text-xs text-slate-400" data-testid="scadenze-riparazioni-empty">Nessuna riparazione pronta</p>
              )}
              <div className="space-y-1">
                {scadenze.riparazioni_pronte.map((r) => (
                  <Link to="/riparazioni" key={r.id} data-testid={`scadenza-riparazione-${r.id}`}
                        className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-50">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{r.client_name}</p>
                      <p className="text-xs text-slate-500">{r.dispositivo}{r.problema ? ` · ${r.problema}` : ""}</p>
                    </div>
                    <span className="rounded-full border border-emerald-300 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-700">Pronto</span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {alerts?.sotto_scorta?.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 shadow-sm" data-testid="sotto-scorta-panel">
          <div className="flex items-center gap-2 border-b border-amber-200 px-5 py-3">
            <Package className="h-4 w-4 text-amber-600" />
            <h2 className="font-heading text-base font-semibold text-amber-900">
              Magazzino sotto scorta ({alerts.sotto_scorta.length})
            </h2>
            <Link to="/magazzino" className="ml-auto inline-flex items-center gap-1 text-xs font-semibold text-amber-700 hover:underline" data-testid="sotto-scorta-link">
              Vai al magazzino <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="flex flex-wrap gap-2 p-4">
            {alerts.sotto_scorta.map((a) => (
              <span key={a.id} className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-medium text-amber-800" data-testid={`sotto-scorta-${a.id}`}>
                {a.nome} · {a.store_name} · <strong>{a.quantita} pz</strong>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-7" data-testid="alerts-panel">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div className="flex items-center gap-2">
              <BellRing className="h-4 w-4 text-amber-600" />
              <h2 className="font-heading text-lg font-semibold text-slate-800">Centro Alert</h2>
            </div>
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800" data-testid="alerts-count">
              {totalAlerts}
            </span>
          </div>
          <div className="max-h-[420px] divide-y divide-slate-100 overflow-y-auto">
            {alerts && totalAlerts === 0 && (
              <p className="px-5 py-10 text-center text-sm text-slate-500" data-testid="alerts-empty">
                Nessun alert attivo. Tutto sotto controllo.
              </p>
            )}
            {alerts?.rinnovi.map((r) => (
              <Link to="/clienti" key={r.client_id} data-testid={`alert-rinnovo-${r.client_id}`}
                    className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-slate-50">
                <div className="flex items-center gap-3">
                  {r.tipo_bolletta === "gas"
                    ? <Flame className="h-4 w-4 text-orange-500" />
                    : <Zap className="h-4 w-4 text-sky-500" />}
                  <div>
                    <p className="text-sm font-medium text-slate-900">{r.cognome} {r.nome}</p>
                    <p className="text-xs text-slate-500">Rinnovo: {fmtDate(r.data_rinnovo)} · {lavorazioneLabel(r.lavorazione)}</p>
                  </div>
                </div>
                <span className={`text-xs font-bold ${r.giorni < 0 ? "text-rose-600" : "text-amber-600"}`}>
                  {r.giorni < 0 ? `${-r.giorni} gg fa` : `${r.giorni} gg`}
                </span>
              </Link>
            ))}
            {alerts?.pagamenti_negozi.map((s) => (
              <Link to="/negozi" key={s.store_id} data-testid={`alert-negozio-${s.store_id}`}
                    className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-slate-50">
                <div>
                  <p className="text-sm font-medium text-slate-900">Negozio {s.nome} ({s.referente})</p>
                  <p className="text-xs text-slate-500">Compenso da rinnovare · ultimo pagamento {fmtDate(s.last_payment_date)}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </Link>
            ))}
            {alerts?.pagamenti_clienti.map((c) => (
              <Link to="/clienti" key={c.client_id} data-testid={`alert-pagamento-${c.client_id}`}
                    className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-slate-50">
                <div>
                  <p className="text-sm font-medium text-slate-900">{c.cognome} {c.nome}</p>
                  <p className="text-xs text-slate-500">Pagamento tornato "non pagato" dopo 6 mesi</p>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5" data-testid="lavorazioni-panel">
          <h2 className="font-heading text-lg font-semibold text-slate-800">Stato lavorazioni</h2>
          <div className="mt-4 space-y-2.5">
            {stats && LAVORAZIONI.filter((l) => stats.per_lavorazione[l.id]).map((l) => {
              const count = stats.per_lavorazione[l.id];
              const pct = Math.round((count / Math.max(stats.totale_clienti, 1)) * 100);
              return (
                <div key={l.id} data-testid={`lavorazione-stat-${l.id}`}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-700">{l.label}</span>
                    <span className="font-bold text-slate-900">{count}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-sky-600 transition-all duration-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
            {stats && Object.keys(stats.per_lavorazione).length === 0 && (
              <p className="py-6 text-center text-sm text-slate-500">Nessun cliente presente</p>
            )}
          </div>
        </div>
      </div>

      {ferme.length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-white shadow-sm" data-testid="riparazioni-ferme-panel">
          <div className="flex flex-wrap items-center gap-2 border-b border-rose-100 px-5 py-4">
            <BellRing className="h-4 w-4 text-rose-600" />
            <h2 className="font-heading text-lg font-semibold text-slate-800">Riparazioni ferme da oltre 7 giorni</h2>
            <span className="text-xs text-slate-500">({ferme.reduce((n, f) => n + f.items.length, 0)} totali)</span>
            {user.role === "admin" && (
              <Button size="sm" variant="outline" onClick={inviaFerme} disabled={sendingFerme} className="ml-auto gap-2" data-testid="invia-avvisi-ferme-button">
                <MessageCircle className="h-4 w-4" /> {sendingFerme ? "Invio..." : "Invia avvisi WhatsApp ora"}
              </Button>
            )}
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
            {ferme.map((f) => (
              <div key={f.store_id} className="rounded-lg border border-slate-200 p-3" data-testid={`ferme-store-${f.store_id}`}>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-slate-900">{f.store_name} <span className="text-rose-700">({f.items.length})</span></p>
                  <span className={`text-[10px] font-medium ${f.telefono_avvisi ? "text-emerald-700" : "text-amber-600"}`}>
                    {f.telefono_avvisi ? "avvisi WA attivi" : "nessun numero avvisi"}
                  </span>
                </div>
                <div className="space-y-1">
                  {f.items.slice(0, 6).map((it) => (
                    <Link to="/riparazioni" key={it.numero} className="flex items-center justify-between text-xs hover:text-sky-700">
                      <span className="truncate"><span className="font-mono font-semibold">{it.numero}</span> {it.dispositivo} · {it.cliente}</span>
                      <span className="ml-2 shrink-0 font-semibold text-rose-700">{it.giorni} gg</span>
                    </Link>
                  ))}
                  {f.items.length > 6 && <p className="text-[10px] text-slate-400">+ altre {f.items.length - 6}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {user.role === "admin" && margini && (
        <div className="rounded-xl border border-emerald-200 bg-white shadow-sm" data-testid="margini-negozi-panel">
          <div className="flex flex-wrap items-center gap-2 border-b border-emerald-100 px-5 py-4">
            <Wallet className="h-4 w-4 text-emerald-700" />
            <h2 className="font-heading text-lg font-semibold text-slate-800">Margine reale riparazioni</h2>
            <input type="month" value={meseMargini} onChange={(e) => setMeseMargini(e.target.value)} max={new Date().toISOString().slice(0, 7)}
                   className="rounded-md border border-slate-200 px-2 py-1 text-sm" data-testid="margini-mese-input" />
            <div className="ml-auto text-right">
              <span className="font-heading text-xl font-bold text-emerald-800" data-testid="margini-totale">€ {margini.totale.toFixed(2)}</span>
              <p className={`text-xs font-medium ${margini.totale - margini.totale_precedente >= 0 ? "text-emerald-700" : "text-rose-700"}`} data-testid="margini-delta-totale">
                {margini.totale - margini.totale_precedente >= 0 ? "▲" : "▼"} € {Math.abs(margini.totale - margini.totale_precedente).toFixed(2)} vs {margini.mese_precedente.split("-").reverse().join("/")} (€ {margini.totale_precedente.toFixed(2)})
              </p>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-5 py-2.5">Negozio</th><th className="px-5 py-2.5">Riparazioni</th><th className="px-5 py-2.5">Incasso (IVA incl.)</th>
                <th className="px-5 py-2.5">Costi</th><th className="px-5 py-2.5">Margine netto</th><th className="px-5 py-2.5">Mese prec.</th><th className="px-5 py-2.5">Variazione</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {margini.negozi.map((m) => (
                <tr key={m.store_id} data-testid={`margine-negozio-${m.store_id}`}>
                  <td className="px-5 py-2.5 font-medium text-slate-900">{m.store_name}</td>
                  <td className="px-5 py-2.5 text-slate-600">{m.riparazioni} <span className="text-xs text-slate-400">({m.consegnate} consegnate)</span></td>
                  <td className="px-5 py-2.5 text-slate-600">€ {m.incasso.toFixed(2)}</td>
                  <td className="px-5 py-2.5 text-slate-600">€ {m.costi.toFixed(2)}</td>
                  <td className={`px-5 py-2.5 font-bold ${m.margine < 0 ? "text-rose-700" : "text-emerald-800"}`}>€ {m.margine.toFixed(2)}</td>
                  <td className="px-5 py-2.5 text-slate-500">€ {m.margine_precedente.toFixed(2)}</td>
                  <td className={`px-5 py-2.5 font-semibold ${m.delta >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{m.delta >= 0 ? "▲" : "▼"} € {Math.abs(m.delta).toFixed(2)}</td>
                </tr>
              ))}
              {margini.negozi.length === 0 && <tr><td colSpan={7} className="px-5 py-6 text-center text-sm text-slate-500">Nessuna riparazione nel mese selezionato</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {stats?.tempi_riparazione?.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="tempi-riparazione-panel">
          <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
            <Wrench className="h-4 w-4 text-slate-500" />
            <h2 className="font-heading text-lg font-semibold text-slate-800">Tempi di riparazione per negozio</h2>
            <span className="ml-auto text-xs text-slate-500">media ingresso → uscita (riparazioni consegnate)</span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-5 py-2.5">Negozio</th>
                <th className="px-5 py-2.5">Media giorni</th>
                <th className="px-5 py-2.5">Chiuse</th>
                <th className="px-5 py-2.5">Aperte</th>
                <th className="px-5 py-2.5">In ritardo (&gt;7gg)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stats.tempi_riparazione.map((t) => (
                <tr key={t.store_id} data-testid={`tempi-riparazione-${t.store_id}`}>
                  <td className="px-5 py-2.5 font-medium text-slate-900">{t.store_name}</td>
                  <td className="px-5 py-2.5">
                    {t.media_giorni != null
                      ? <span className={`font-bold ${t.media_giorni > 7 ? "text-rose-700" : t.media_giorni > 3 ? "text-amber-700" : "text-emerald-700"}`}>{t.media_giorni} gg</span>
                      : <span className="text-slate-400">-</span>}
                  </td>
                  <td className="px-5 py-2.5 text-slate-600">{t.chiuse}</td>
                  <td className="px-5 py-2.5 text-slate-600">{t.aperte}</td>
                  <td className="px-5 py-2.5">
                    {t.aperte_oltre_7gg > 0
                      ? <span className="status-badge bg-rose-500/15 text-rose-700 border-rose-300">{t.aperte_oltre_7gg}</span>
                      : <span className="text-slate-400">0</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
