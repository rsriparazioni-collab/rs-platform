import { useEffect, useState } from "react";
import { BellRing, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";

const LABEL = { "rinnovo-energia": "Rinnovo energia", bollette: "Richiesta bollette", "avvisi-vincolo": "Vincolo telefonia", "riparazioni-ferme": "Riparazioni ferme", "promemoria-ritiro": "Promemoria ritiro", "avvisi-truffe": "Avvisi truffe", "ordini-fermi": "Ordini fermi", "ritiri-in-attesa": "Ritiri in attesa" };
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "mai");

export default function AvvisiStato() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/avvisi/stato").then((r) => setD(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const ripristina = async () => {
    if (!window.confirm("Riabilito gli avvisi che risultano 'inviati' ma erano stati fatti in MODALITÀ TEST (mai arrivati al cliente)? Partiranno al prossimo giro delle 8:30.")) return;
    setBusy(true);
    try { const r = await api.post("/avvisi/ripristina-test"); toast.success(`Riabilitati: ${r.data.rinnovo_energia} rinnovi · ${r.data.bollette} bollette · ${r.data.vincolo} vincoli`); load(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  const [esito, setEsito] = useState(null);
  const verifica = async () => {
    if (!window.confirm("Controllo le scadenze da 30 a 1 giorno (rinnovi luce/gas e vincoli telefonia) e mando SUBITO i WhatsApp non ancora inviati. Procedo?")) return;
    setBusy(true);
    try {
      const r = await api.post("/avvisi/verifica-invia?min_giorni=1&max_giorni=30");
      setEsito(r.data);
      const tot = r.data.rinnovo_energia.inviati_ora + r.data.vincolo.inviati_ora;
      toast.success(r.data.dry_run ? "Modalità test: nessun invio reale" : `Inviati ora: ${tot} avvisi`);
      load();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  if (!d) return null;
  const giri = Object.entries(LABEL).map(([k, l]) => [k, l, d.giri[k]]);
  return (
    <details className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="avvisi-stato">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-5 py-3 text-sm font-semibold text-slate-800">
        <BellRing className="h-4 w-4 text-sky-600" /> Avvisi automatici WhatsApp (ogni mattina 8:30)
        {d.dry_run && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800" data-testid="avvisi-dry-run">MODALITÀ TEST: nessun invio reale</span>}
        <span className="ml-auto text-xs font-normal text-slate-500">in attesa: {d.in_attesa.rinnovo_energia} rinnovi · {d.in_attesa.bollette} bollette · ultimi 7 gg: {Object.values(d.invii).reduce((a, v) => a + v.inviati_7gg, 0)} inviati, {Object.values(d.invii).reduce((a, v) => a + v.errori_7gg, 0)} errori</span>
      </summary>
      <div className="grid gap-2 border-t px-5 py-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
        {giri.map(([k, l, g]) => (
          <div key={k} className="flex items-start gap-2 rounded-lg border border-slate-100 p-2" data-testid={`avvisi-giro-${k}`}>
            {g ? (g.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-emerald-600" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 text-rose-600" />) : <span className="mt-0.5 h-3.5 w-3.5 rounded-full border border-slate-300" />}
            <div>
              <div className="font-medium text-slate-800">{l}</div>
              <div className="text-slate-500">ultimo giro {fmt(g?.last_run)}{g?.n != null && ` · ${g.n} elaborati`}</div>
              {g?.error && <div className="text-rose-600">{g.error}</div>}
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t px-5 py-2 text-[11px] text-slate-500">
        <span>{Object.values(d.regole).join(" · ")}</span>
        <div className="flex gap-2">
          <button type="button" onClick={verifica} disabled={busy} className="rounded-md border border-sky-300 bg-sky-50 px-2 py-1 text-[11px] font-semibold text-sky-800 hover:bg-sky-100" data-testid="avvisi-verifica-invia">
            {busy ? "Controllo…" : "Verifica scadenze 30→1 gg e invia i mancanti"}
          </button>
          <button type="button" onClick={ripristina} disabled={busy} className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-800 hover:bg-amber-100" data-testid="avvisi-ripristina-test">
            Riabilita avvisi fatti in modalità test
          </button>
        </div>
      </div>
      {esito && (
        <div className="border-t px-5 py-2 text-xs" data-testid="avvisi-verifica-esito">
          <p className="font-medium text-slate-800">Esito controllo scadenze {esito.finestra.a}→{esito.finestra.da} giorni{esito.dry_run && <span className="ml-2 text-amber-700">(modalità test: nessun invio reale)</span>}</p>
          <p className="text-slate-600">Rinnovi luce/gas: <b className="text-emerald-700">{esito.rinnovo_energia.inviati_ora} inviati ora</b> · {esito.rinnovo_energia.gia_inviati} già avvisati in precedenza · {esito.rinnovo_energia.errori.length} errori</p>
          <p className="text-slate-600">Vincoli telefonia: <b className="text-emerald-700">{esito.vincolo.inviati_ora} inviati ora</b> · {esito.vincolo.errori.length} errori</p>
          {[...esito.rinnovo_energia.errori, ...esito.vincolo.errori].slice(0, 10).map((e, i) => <p key={i} className="text-rose-600">• {e.client_id || e.servizio}: {e.errore}</p>)}
        </div>
      )}
    </details>
  );
}
