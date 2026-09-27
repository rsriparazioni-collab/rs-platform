import { useCallback, useEffect, useState } from "react";
import { Trophy, Save } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { MESI } from "../../lib/constants";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { eur } from "./CompensiCalcolo";

export const GaraWindTre = () => {
  const oggi = new Date();
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [data, setData] = useState(null);
  const [premio, setPremio] = useState("");
  const [tariffe, setTariffe] = useState(null);
  const [tariffeText, setTariffeText] = useState("");

  const load = useCallback(() => api.get("/gara-windtre/calcolo", { params: { anno, mese } }).then((r) => { setData(r.data); setPremio(String(r.data.premio_totale || "")); }).catch((e) => toast.error(apiError(e))), [anno, mese]);
  useEffect(() => { load(); }, [load]);

  const salvaPremio = async () => {
    try { await api.post("/gara-windtre/premio", { mese: `${anno}-${String(mese).padStart(2, "0")}`, premio_totale: parseFloat(premio) || 0 }); toast.success("Premio salvato"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const apriTariffe = async () => {
    const r = await api.get("/gara-windtre/tariffe"); setTariffe(r.data); setTariffeText(JSON.stringify(r.data, null, 2));
  };
  const salvaTariffe = async () => {
    try { const t = JSON.parse(tariffeText); await api.put("/gara-windtre/tariffe", { tariffe: t }); toast.success("Tariffe regolamento salvate"); setTariffe(null); load(); }
    catch (e) { toast.error(e?.response ? apiError(e) : "JSON non valido"); }
  };

  return (
    <div className="space-y-4" data-testid="gara-windtre">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={String(mese)} onValueChange={(v) => setMese(parseInt(v))}><SelectTrigger className="w-[140px]" data-testid="gara-mese"><SelectValue /></SelectTrigger>
          <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select>
        <Select value={String(anno)} onValueChange={(v) => setAnno(parseInt(v))}><SelectTrigger className="w-[100px]" data-testid="gara-anno"><SelectValue /></SelectTrigger>
          <SelectContent>{[anno - 1, anno, anno + 1].map((a) => <SelectItem key={a} value={String(a)}>{a}</SelectItem>)}</SelectContent></Select>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5">
          <Trophy className="h-4 w-4 text-amber-500" /><span className="text-sm text-slate-600">Premio totale rete €</span>
          <Input type="number" step="0.01" className="h-8 w-28" value={premio} onChange={(e) => setPremio(e.target.value)} data-testid="gara-premio" />
          <Button size="sm" variant="outline" onClick={salvaPremio} className="gap-1" data-testid="gara-premio-salva"><Save className="h-3.5 w-3.5" /> Salva</Button>
        </div>
        <Button variant="ghost" size="sm" onClick={apriTariffe} data-testid="gara-tariffe-button">Modifica tariffe regolamento</Button>
        {data && <span className="ml-auto rounded-full bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white" data-testid="gara-totale-rete">Generato rete {eur(data.totale_rete)}</span>}
      </div>

      {tariffe && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 space-y-2">
          <p className="text-sm text-slate-600">Tabella compensi del regolamento (soglie e importi). Modifica i valori e salva.</p>
          <textarea className="h-72 w-full rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs" value={tariffeText} onChange={(e) => setTariffeText(e.target.value)} data-testid="gara-tariffe-json" />
          <div className="flex gap-2"><Button size="sm" onClick={salvaTariffe} data-testid="gara-tariffe-salva">Salva tariffe</Button><Button size="sm" variant="outline" onClick={() => setTariffe(null)}>Chiudi</Button></div>
        </div>
      )}

      {data && (
        <div className="flex flex-wrap gap-2 text-xs" data-testid="gara-soglie">
          <span className={`status-badge ${data.extra_mnp_attivo ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-amber-500/15 text-amber-700 border-amber-300"}`}>MNP rete {data.mnp_rete}/{data.extra_mnp_soglia} {data.extra_mnp_attivo ? "· extra MNP attivi" : "· extra MNP non attivi"}</span>
          {Object.entries(data.soglie).map(([c, v]) => <span key={c} className="status-badge bg-sky-500/15 text-sky-700 border-sky-300">{c}: {v.conteggio} attivazioni</span>)}
        </div>
      )}

      {data?.ripartizione.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="gara-ripartizione">
          {data.ripartizione.map((n) => (
            <div key={n.store_id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-baseline justify-between"><h3 className="font-heading font-semibold text-slate-900">{n.nome}</h3><span className="text-xs text-slate-500">{n.attivazioni} attivazioni</span></div>
              <p className="text-sm text-slate-600">Generato <b>{eur(n.generato)}</b> · Quota premio <b className="text-emerald-700">{eur(n.quota)}</b></p>
              <ul className="mt-2 space-y-1 text-xs text-slate-600">{n.inseritori.map((i) => <li key={i.id} className="flex justify-between"><span>{i.nome} ({i.attivazioni})</span><span>{eur(i.generato)} → quota {eur(i.quota)}</span></li>)}</ul>
            </div>
          ))}
        </div>
      )}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm" data-testid="gara-attivazioni">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-2">Data</th><th className="px-3 py-2">Cliente</th><th className="px-3 py-2">Negozio / Inseritore</th><th className="px-3 py-2">Prodotto</th><th className="px-3 py-2">Categoria</th><th className="px-3 py-2">MNP</th><th className="px-3 py-2">Soglia</th><th className="px-3 py-2">Base</th><th className="px-3 py-2">Extra</th><th className="px-3 py-2">Finale</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {data.attivazioni.length === 0 && <tr><td colSpan={10} className="px-4 py-6 text-center text-slate-400">Nessuna attivazione WindTre/Very nel mese</td></tr>}
              {data.attivazioni.map((a) => (
                <tr key={a.id} className={a.riconosciuta ? "" : "opacity-50"}>
                  <td className="px-4 py-2 text-slate-600">{a.data}</td>
                  <td className="px-3 py-2 text-slate-800">{a.cliente}{a.piva && <span className="ml-1 text-xs text-indigo-600">P.IVA</span>}</td>
                  <td className="px-3 py-2 text-slate-600">{a.negozio} / {a.inseritore}</td>
                  <td className="px-3 py-2">{a.prodotto}{a.convergente && " · Conv."}{a.tied && " · Tied"}</td>
                  <td className="px-3 py-2 text-slate-600">{a.categoria}</td>
                  <td className="px-3 py-2">{a.mobile ? (a.mnp ? `MNP${a.provenienza ? ` da ${a.provenienza}` : ""}` : "NO MNP") : "-"}</td>
                  <td className="px-3 py-2">{a.soglia ? `da ${a.soglia}` : <span className="text-xs text-amber-600">{a.nota}</span>}</td>
                  <td className="px-3 py-2">{eur(a.compenso_base)}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{a.extra.map((e) => `${e.nome} +${e.importo}€`).join(", ")}</td>
                  <td className="px-3 py-2 font-semibold">{eur(a.compenso_finale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
