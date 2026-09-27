import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { MESI, fmtDate } from "../../lib/constants";
import { Button } from "../ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { eur } from "./CompensiCalcolo";

const Tabella = ({ titolo, righe, testid }) => (
  <div className="rounded-xl border border-slate-200 bg-white" data-testid={testid}>
    <p className="border-b border-slate-100 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{titolo}</p>
    <table className="w-full text-sm"><tbody className="divide-y divide-slate-100">
      {righe.map((r) => <tr key={r.nome}><td className="px-4 py-1.5 text-slate-800">{r.nome}</td><td className="px-3 py-1.5 text-right text-slate-500">{r.n} ric.{r.fallite > 0 && <span className="ml-1 text-rose-500">({r.fallite} fallite)</span>}</td><td className="px-4 py-1.5 text-right font-semibold">{eur(r.totale)}</td></tr>)}
      {righe.length === 0 && <tr><td className="px-4 py-3 text-sm text-slate-400">Nessun dato</td></tr>}
    </tbody></table>
  </div>
);

export const CompensiRicariche = ({ meta }) => {
  const oggi = new Date();
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();

  const load = useCallback(() => api.get("/ricariche/riepilogo", { params: { anno, mese } }).then((r) => setData(r.data)).catch((e) => toast.error(apiError(e))), [anno, mese]);
  useEffect(() => { load(); }, [load]);

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await api.post("/ricariche/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Importate ${r.data.righe} ricariche (${r.data.nuove} nuove) · mesi: ${r.data.mesi.join(", ")}`);
      const ultimo = r.data.mesi[r.data.mesi.length - 1];
      if (ultimo) { setAnno(parseInt(ultimo.slice(0, 4))); setMese(parseInt(ultimo.slice(5))); }
      load();
    } catch (err) { toast.error(apiError(err, "Import non riuscito")); } finally { setBusy(false); e.target.value = ""; }
  };

  const setMap = async (utente, store_id) => {
    try { await api.put("/ricariche/mapping", { utente, store_id }); toast.success("Assegnazione salvata"); load(); } catch (err) { toast.error(apiError(err)); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-emerald-300 bg-emerald-50/50 p-4">
        <FileSpreadsheet className="h-6 w-6 text-emerald-600" />
        <div className="flex-1 text-sm text-slate-600">Carica il file CSV delle ricariche scaricato dal portale (colonne: #, Partner, Utente, Operatore ricarica, Importo, Data/Ora, Numero, Esito, Note). Le ricariche già presenti non vengono duplicate.
          {data?.ultimo_import && <p className="text-xs text-slate-400">Ultimo import: {fmtDate(data.ultimo_import.at)} · {data.ultimo_import.file} · {data.ultimo_import.righe} righe</p>}</div>
        <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={upload} data-testid="ricariche-file-input" />
        <Button onClick={() => fileRef.current?.click()} disabled={busy} className="gap-1.5 bg-emerald-600 hover:bg-emerald-700" data-testid="ricariche-upload-button"><Upload className="h-4 w-4" /> Carica CSV ricariche</Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={String(mese)} onValueChange={(v) => setMese(parseInt(v))}><SelectTrigger className="w-[140px]" data-testid="ricariche-mese"><SelectValue /></SelectTrigger>
          <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select>
        <Select value={String(anno)} onValueChange={(v) => setAnno(parseInt(v))}><SelectTrigger className="w-[100px]" data-testid="ricariche-anno"><SelectValue /></SelectTrigger>
          <SelectContent>{[anno - 1, anno, anno + 1].map((a) => <SelectItem key={a} value={String(a)}>{a}</SelectItem>)}</SelectContent></Select>
        {data && (
          <div className="ml-auto flex gap-3 text-sm">
            <span className="rounded-full bg-slate-900 px-4 py-1.5 font-semibold text-white" data-testid="ricariche-totale">{data.totale.n} ricariche · {eur(data.totale.totale)}</span>
            {data.totale.fallite > 0 && <span className="rounded-full bg-rose-100 px-4 py-1.5 text-rose-700">{data.totale.fallite} fallite ({eur(data.totale.totale_fallite)})</span>}
          </div>
        )}
      </div>

      {data && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Tabella titolo="Per negozio" righe={data.per_negozio} testid="ricariche-per-negozio" />
          <Tabella titolo="Per utente" righe={data.per_utente} testid="ricariche-per-utente" />
          <Tabella titolo="Per operatore" righe={data.per_operatore} testid="ricariche-per-operatore" />
        </div>
      )}

      {data?.mapping.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="ricariche-mapping">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assegnazione utenti del portale → negozio</p>
          <p className="mb-3 text-xs text-slate-400">"System" sono le ricariche automatiche contestuali alle attivazioni: assegnale al negozio che le fa o lasciale non assegnate.</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data.mapping.map((m) => (
              <div key={m.utente} className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-1.5 text-sm">
                <span className="text-slate-800">{m.utente}</span>
                <Select value={m.store_id || "none"} onValueChange={(v) => setMap(m.utente, v === "none" ? "" : v)}>
                  <SelectTrigger className="h-8 w-40" data-testid={`ricariche-map-${m.utente.replace(/\s+/g, "-")}`}><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="none">Non assegnato</SelectItem>{meta.stores.map((s) => <SelectItem key={s.id} value={s.id}>{s.nome}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
