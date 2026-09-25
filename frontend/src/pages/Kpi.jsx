import { Fragment, useCallback, useEffect, useState } from "react";
import { BarChart3, FileDown, ArrowUpRight, ArrowDownRight, Minus, BellRing, Target } from "lucide-react";
import ObiettiviDialog, { BarraObiettivo } from "../components/ObiettiviDialog";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];
const AREA_LABEL = { generale: "Generale", energia: "Energia (ENEL / CambiaOra)", telefonia: "Telefonia", internet: "Internet", chiamate: "Chiamate", riparazioni: "Riparazioni" };

export default function Kpi() {
  const { user } = useAuth();
  const now = new Date();
  const [anno, setAnno] = useState(now.getFullYear());
  const [mese, setMese] = useState(now.getMonth() + 1);
  const [utenti, setUtenti] = useState([]);
  const [userId, setUserId] = useState("");
  const [data, setData] = useState(null);
  const [riepilogo, setRiepilogo] = useState([]);
  const [voci, setVoci] = useState([]);
  const [obOpen, setObOpen] = useState(false);
  const [obiettivi, setObiettivi] = useState([]);
  const vedeTutti = user.role === "admin" || user.can_view_all;

  useEffect(() => { api.get("/kpi/voci").then((r) => setVoci(r.data.voci)).catch(() => {}); }, []);

  useEffect(() => { api.get("/kpi/utenti").then((r) => { setUtenti(r.data); if (!vedeTutti && r.data[0]) setUserId(r.data[0].id); }).catch(() => {}); }, [vedeTutti]);
  const load = useCallback(() => {
    if (vedeTutti) api.get("/kpi/riepilogo", { params: { anno, mese } }).then((r) => setRiepilogo(r.data)).catch(() => {});
    if (userId) {
      api.get("/kpi", { params: { anno, mese, user_id: userId } }).then((r) => setData(r.data)).catch((e) => toast.error(apiError(e)));
      api.get("/kpi/obiettivi", { params: { anno, mese, user_id: userId } }).then((r) => setObiettivi(r.data)).catch(() => setObiettivi([]));
    }
  }, [anno, mese, userId, vedeTutti]);
  useEffect(() => { load(); }, [load]);

  const giorni = data ? Array.from({ length: data.giorni }, (_, i) => i + 1) : [];
  const aree = data ? [...new Set(data.voci.map((v) => v.area))] : [];

  return (
    <div className="space-y-6" data-testid="kpi-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900">KPI Team</h1>
          <p className="mt-1 text-sm text-slate-500">Attività per operatore, giorno per giorno: dati automatici dal gestionale + registro rapido{data?.kpi_start ? ` · conteggi dal ${new Date(data.kpi_start).toLocaleDateString("it-IT")}` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={String(mese)} onValueChange={(v) => setMese(parseInt(v))}><SelectTrigger className="w-[140px]" data-testid="kpi-mese"><SelectValue /></SelectTrigger>
            <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select>
          <Select value={String(anno)} onValueChange={(v) => setAnno(parseInt(v))}><SelectTrigger className="w-[100px]" data-testid="kpi-anno"><SelectValue /></SelectTrigger>
            <SelectContent>{[anno - 1, anno, anno + 1].map((a) => <SelectItem key={a} value={String(a)}>{a}</SelectItem>)}</SelectContent></Select>
          {vedeTutti && (
            <Select value={userId || "none"} onValueChange={(v) => setUserId(v === "none" ? "" : v)}><SelectTrigger className="w-[180px]" data-testid="kpi-operatore"><SelectValue placeholder="Operatore" /></SelectTrigger>
              <SelectContent><SelectItem value="none">Scegli operatore…</SelectItem>{utenti.map((u) => <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>)}</SelectContent></Select>
          )}
          <Button variant="outline" className="gap-2" onClick={() => downloadBlob(`/kpi/export?anno=${anno}&mese=${mese}${userId ? `&user_id=${userId}` : ""}`, `kpi_${anno}_${String(mese).padStart(2, "0")}.xlsx`)} data-testid="kpi-export"><FileDown className="h-4 w-4" /> Excel</Button>
          {user.role === "admin" && <Button variant="outline" className="gap-2" onClick={() => setObOpen(true)} data-testid="kpi-obiettivi-btn"><Target className="h-4 w-4" /> Obiettivi</Button>}
          {user.role === "admin" && (
            <Button variant="outline" className="gap-2 border-amber-300 text-amber-800" onClick={async () => { try { const r = await api.post("/kpi/promemoria/invia-ora"); const inv = r.data.report.filter((x) => x.esito === "inviato").length; toast.success(`Promemoria inviati: ${inv} · ${r.data.report.filter((x) => x.esito !== "inviato").map((x) => `${x.user}: ${x.esito}`).join(", ") || "tutti ok"}`); } catch (e) { toast.error(apiError(e)); } }} data-testid="kpi-promemoria-ora" title="Invia adesso il promemoria WhatsApp a chi oggi non ha segnato nulla (automatico alle 18:30)">
              <BellRing className="h-4 w-4" /> Promemoria ora
            </Button>
          )}
        </div>
      </div>

      {data?.prima_inizio && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="kpi-prima-inizio">
          I conteggi KPI partono dal <b>{new Date(data.kpi_start).toLocaleDateString("it-IT")}</b>: i mesi precedenti sono a zero per avere un confronto reale mese su mese.
        </div>
      )}
      {vedeTutti && riepilogo.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="kpi-riepilogo">
          {riepilogo.map((r) => {
            const Delta = ({ cur, prev, testid }) => {
              const diff = cur - prev;
              if (!prev && !cur) return null;
              const cls = diff > 0 ? "text-emerald-700 bg-emerald-50" : diff < 0 ? "text-rose-700 bg-rose-50" : "text-slate-500 bg-slate-100";
              return <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11px] font-semibold ${cls}`} title={`Mese precedente (${r.prev_label}): ${prev}`} data-testid={testid}>{diff > 0 ? <ArrowUpRight className="h-3 w-3" /> : diff < 0 ? <ArrowDownRight className="h-3 w-3" /> : <Minus className="h-3 w-3" />}{diff > 0 ? "+" : ""}{diff}{prev ? ` (${Math.round((diff / prev) * 100)}%)` : ""}</span>;
            };
            return (
            <button key={r.user_id} type="button" onClick={() => setUserId(r.user_id)} className={`rounded-xl border bg-white p-4 text-left shadow-sm transition-colors ${userId === r.user_id ? "border-slate-900" : "border-slate-200 hover:border-slate-400"}`} data-testid={`kpi-card-${r.user_id}`}>
              <div className="flex items-center justify-between"><p className="font-semibold text-slate-900">{r.name}</p><BarChart3 className="h-4 w-4 text-slate-400" /></div>
              <div className="mt-1 flex items-center gap-2"><p className="text-2xl font-bold text-slate-900">{r.totale_mese}</p><Delta cur={r.totale_mese} prev={r.prev_totale_mese} testid={`kpi-delta-${r.user_id}`} /></div>
              <p className="flex items-center gap-1.5 text-xs text-slate-500">{r.role === "tecnico" ? "riparazioni fatte" : <>attività · {r.clienti_serviti} clienti serviti <Delta cur={r.clienti_serviti} prev={r.prev_clienti_serviti} /></>}</p>
              <ul className="mt-2 space-y-0.5 text-[11px] text-slate-600">{r.top.map((t) => <li key={t.label} className="flex justify-between"><span>{t.label}</span><span><b>{t.totale}</b> <span className={t.totale - t.prev > 0 ? "text-emerald-600" : t.totale - t.prev < 0 ? "text-rose-600" : "text-slate-400"}>{t.totale - t.prev > 0 ? "↑" : t.totale - t.prev < 0 ? "↓" : "="}</span></span></li>)}</ul>
              {r.obiettivi?.length > 0 && (
                <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2" data-testid={`kpi-obiettivi-${r.user_id}`}>
                  <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Obiettivi · {r.obiettivi.filter((o) => o.pct >= 100).length}/{r.obiettivi.length} raggiunti</p>
                  {r.obiettivi.slice(0, 4).map((o) => <BarraObiettivo key={o.id} o={o} compact />)}
                </div>
              )}
            </button>
          ); })}
        </div>
      )}

      {data && obiettivi.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="kpi-obiettivi-dettaglio">
          <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900"><Target className="h-4 w-4 text-slate-500" /> Obiettivi di {data.user_name} · {MESI[mese - 1]} {anno}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{obiettivi.map((o) => <BarraObiettivo key={o.id} o={o} />)}</div>
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="kpi-griglia">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <p className="font-semibold text-slate-900">{data.user_name} · {MESI[mese - 1]} {anno}</p>
            <p className="text-xs text-slate-500">{data.solo_riparazioni ? "Riparazioni fatte" : "Totale attività"}: <b>{data.totale_mese}</b></p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="bg-slate-50 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                <th className="sticky left-0 bg-slate-50 px-3 py-2">giorno:</th>{giorni.map((g) => <th key={g} className="px-1 py-2 text-center">{g}</th>)}<th className="px-3 py-2 text-right">Tot. mese</th>
              </tr></thead>
              <tbody>
                {aree.map((a) => (
                  <Fragment key={a}>
                    <tr className="bg-slate-100/80"><td colSpan={giorni.length + 2} className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-700">{AREA_LABEL[a] || a}</td></tr>
                    {data.voci.filter((v) => v.area === a).map((v) => (
                      <tr key={v.id} className="border-t border-slate-100 hover:bg-amber-50/40" data-testid={`kpi-riga-${v.id}`}>
                        <td className="sticky left-0 bg-white px-3 py-1.5 font-medium text-slate-800">{v.dettaglio ? <span className="pl-4 text-slate-500">{v.label.trim()}</span> : v.label}{!v.dettaglio && <span className={`ml-1.5 rounded px-1 text-[9px] uppercase ${v.fonte === "auto" ? "bg-emerald-100 text-emerald-700" : v.fonte === "manuale" ? "bg-amber-100 text-amber-700" : "bg-sky-100 text-sky-700"}`}>{v.fonte}</span>}</td>
                        {giorni.map((g) => <td key={g} className={`px-1 py-1.5 text-center ${v.giorni[g] ? "font-semibold text-slate-900" : "text-slate-300"}`}>{v.giorni[g] || ""}</td>)}
                        <td className="px-3 py-1.5 text-right font-bold text-slate-900" data-testid={`kpi-tot-${v.id}`}>{v.totale}</td>
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {!data && vedeTutti && <p className="text-sm text-slate-500" data-testid="kpi-scegli">Scegli un operatore dalle card o dal menu per vedere la griglia giornaliera.</p>}
      <ObiettiviDialog open={obOpen} onOpenChange={setObOpen} utenti={utenti} voci={voci} anno={anno} mese={mese} userId={userId} onChanged={load} />
    </div>
  );
}
