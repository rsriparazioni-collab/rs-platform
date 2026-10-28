import { useState } from "react";
import { Hand, RotateCcw, CalendarPlus, AlertTriangle, StickyNote } from "lucide-react";
import { Input } from "../ui/input";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { lavorazioneLabel, lavorazioneBadge } from "../../lib/constants";
import { RicordiLine } from "../Ricordi";

const SEMAFORO = { verde: "bg-emerald-500", giallo: "bg-amber-400", rosso: "bg-red-500" };
const COLORI = { sky: "border-sky-200 bg-sky-50/60", emerald: "border-emerald-200 bg-emerald-50/60", rose: "border-rose-200 bg-rose-50/60" };

const Riga = ({ r, lavorate, reinserire, onOpen, onChanged, onAgenda, ricordi }) => {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [notaOpen, setNotaOpen] = useState(false);
  const [nota, setNota] = useState("");
  const mia = r.presa_in_carico_da === user.id;
  const salvaNota = async (e) => {
    e.stopPropagation();
    if (!nota.trim()) return;
    setBusy(true);
    try { await api.post(`/lavorazioni/${r.id}/nota`, { nota }); setNota(""); setNotaOpen(false); toast.success("Nota salvata"); onChanged(); } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };
  const presa = async (e) => {
    e.stopPropagation(); setBusy(true);
    try { await api.post(`/lavorazioni/${r.id}/presa-in-carico`, { attiva: !mia }); onChanged(); } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };
  const reins = async (e) => {
    e.stopPropagation();
    const motivo = window.prompt("Motivo del reinserimento (facoltativo):", "");
    if (motivo === null) return;
    setBusy(true);
    try { await api.post(`/lavorazioni/${r.id}/reinserisci`, { motivo }); toast.success("Pratica reinserita: ora è in 'Da lavorare'"); onChanged(); } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };
  return (
    <div className={`rounded-lg border bg-white p-2.5 shadow-sm transition-colors hover:border-sky-300 cursor-pointer ${!lavorate && !r.presa_in_carico_da ? "border-amber-300" : "border-slate-200"}`}
         onClick={() => onOpen({ id: r.id })} data-testid={`pratica-${r.id}`}>
      <div className="flex items-start gap-2">
        {!lavorate && <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${SEMAFORO[r.semaforo]}`} title={`${r.giorni_fermo} giorni`} data-testid={`semaforo-${r.semaforo}`} />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate font-semibold text-slate-900">{r.client_name}</span>
            <span className="text-xs text-slate-500">{r.negozio}</span>
            <Badge variant="outline" className="text-[10px] uppercase">{r.gestione}</Badge>
            {r.reinserimenti > 0 && <Badge variant="outline" className="text-[10px] border-violet-300 text-violet-700">reinserita ×{r.reinserimenti}</Badge>}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
            <span className={`rounded border px-1.5 py-0.5 ${lavorazioneBadge(r.lavorazione)}`}>{lavorazioneLabel(r.lavorazione)}</span>
            <span>{lavorate ? "lavorata" : "ferma"} da {r.giorni_fermo} gg</span>
            {r.verifica_esito && <span className="flex items-center gap-1 text-orange-600 font-medium" data-testid="verifica-esito"><AlertTriangle className="h-3 w-3" /> verifica esito</span>}
            {r.presa_in_carico_nome && <span className="text-sky-700">in carico a {r.presa_in_carico_nome}</span>}
            {!lavorate && r.gestione !== "enel" && r.documenti === 0 && <span className="rounded bg-rose-50 px-1 text-rose-700" data-testid={`senza-doc-${r.id}`}>senza documenti</span>}
            {r.documenti > 0 && <span className="text-slate-400">{r.documenti} doc</span>}
          </div>
          <RicordiLine testi={ricordi?.[r.id]} />
          {r.ultima_nota && (
            <p className="mt-1 flex items-start gap-1 rounded bg-amber-50 px-1.5 py-1 text-xs text-amber-900" data-testid={`ultima-nota-${r.id}`}>
              <StickyNote className="mt-0.5 h-3 w-3 shrink-0" /><span className="truncate"><b>{r.ultima_nota.da}</b>: {r.ultima_nota.n}</span>
            </p>
          )}
        </div>
      </div>
      {notaOpen && (
        <div className="mt-2 flex gap-1.5" onClick={(e) => e.stopPropagation()}>
          <Input autoFocus value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Nota rapida…" className="h-7 text-xs"
                 onKeyDown={(e) => { if (e.key === "Enter") salvaNota(e); if (e.key === "Escape") setNotaOpen(false); }} data-testid={`nota-input-${r.id}`} />
          <Button size="sm" className="h-7 text-xs" disabled={busy || !nota.trim()} onClick={salvaNota} data-testid={`nota-save-${r.id}`}>Salva</Button>
        </div>
      )}
      {!lavorate && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Button size="sm" variant={mia ? "default" : "outline"} className="h-7 text-xs" disabled={busy} onClick={presa} data-testid={`presa-${r.id}`}>
            <Hand className="mr-1 h-3 w-3" /> {mia ? "La lavoro io ✓" : "Prendi in carico"}
          </Button>
          {reinserire && <Button size="sm" variant="outline" className="h-7 text-xs border-rose-300 text-rose-700" disabled={busy} onClick={reins} data-testid={`reinserisci-${r.id}`}><RotateCcw className="mr-1 h-3 w-3" /> Reinserisci</Button>}
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); onAgenda(r); }} data-testid={`agenda-${r.id}`}><CalendarPlus className="mr-1 h-3 w-3" /> Agenda</Button>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); setNotaOpen((o) => !o); }} data-testid={`nota-btn-${r.id}`}><StickyNote className="mr-1 h-3 w-3" /> Nota</Button>
        </div>
      )}
    </div>
  );
};

export const ColonnaPratiche = ({ titolo, colore, righe, testid, ...rest }) => (
  <section className={`rounded-xl border p-3 ${COLORI[colore]}`} data-testid={testid}>
    <h2 className="mb-2 flex items-center justify-between text-base font-bold text-slate-800">{titolo}<span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-600" data-testid={`${testid}-count`}>{righe.length}</span></h2>
    <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
      {righe.length === 0 && <p className="py-6 text-center text-xs text-slate-400">Nessuna pratica</p>}
      {righe.map((r) => <Riga key={r.id} r={r} {...rest} />)}
    </div>
  </section>
);
