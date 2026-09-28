import { useCallback, useEffect, useState } from "react";
import { FileDown, FlaskConical } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { MESI } from "../lib/constants";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Switch } from "./ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const eur = (v) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(v || 0);

export default function ReportLaboratorio({ open, onClose }) {
  const oggi = new Date();
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [tecnico, setTecnico] = useState("");
  const [includi, setIncludi] = useState(false);
  const [minMan, setMinMan] = useState(15);
  const [data, setData] = useState(null);
  const params = { anno, mese, tecnico_id: tecnico, includi_non_attribuite: includi, min_manodopera: minMan };

  const load = useCallback(() => {
    if (!open) return;
    api.get("/riparazioni/report-laboratorio", { params }).then((r) => { setData(r.data); if (!tecnico && r.data.tecnico_id) setTecnico(r.data.tecnico_id); }).catch((e) => toast.error(apiError(e)));
  }, [open, anno, mese, tecnico, includi, minMan]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl" data-testid="report-laboratorio-dialog">
        <DialogHeader><DialogTitle className="font-heading flex items-center gap-2"><FlaskConical className="h-5 w-5 text-indigo-600" /> Report laboratorio – cosa devono pagare i negozi</DialogTitle></DialogHeader>
        <div className="flex flex-wrap items-center gap-3">
          <Select value={String(mese)} onValueChange={(v) => setMese(parseInt(v))}><SelectTrigger className="w-[140px]" data-testid="replab-mese"><SelectValue /></SelectTrigger>
            <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select>
          <Select value={String(anno)} onValueChange={(v) => setAnno(parseInt(v))}><SelectTrigger className="w-[100px]" data-testid="replab-anno"><SelectValue /></SelectTrigger>
            <SelectContent>{[anno - 1, anno, anno + 1].map((a) => <SelectItem key={a} value={String(a)}>{a}</SelectItem>)}</SelectContent></Select>
          {data?.tecnici?.length > 1 && (
            <Select value={tecnico} onValueChange={setTecnico}><SelectTrigger className="w-[160px]" data-testid="replab-tecnico"><SelectValue placeholder="Tecnico" /></SelectTrigger>
              <SelectContent>{data.tecnici.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent></Select>
          )}
          <label className="flex items-center gap-2 text-sm text-slate-600">Min. manodopera € <Input type="number" step="0.5" className="h-9 w-20" value={minMan} onChange={(e) => setMinMan(parseFloat(e.target.value) || 0)} data-testid="replab-min" /></label>
          <label className="flex items-center gap-2 text-sm text-slate-600"><Switch checked={includi} onCheckedChange={setIncludi} data-testid="replab-includi" /> Includi riparazioni non attribuite {data?.non_attribuite > 0 && <span className="text-xs text-amber-700">({data.non_attribuite} nel mese)</span>}</label>
          <Button variant="outline" className="ml-auto gap-2" onClick={() => downloadBlob(`/riparazioni/report-laboratorio/export?anno=${anno}&mese=${mese}&tecnico_id=${tecnico}&includi_non_attribuite=${includi}&min_manodopera=${minMan}`, `report_laboratorio_${anno}-${String(mese).padStart(2, "0")}.xlsx`)} data-testid="replab-export"><FileDown className="h-4 w-4" /> Excel</Button>
        </div>

        {data && (
          <div className="grid gap-3 sm:grid-cols-4">
            {[["Riparazioni", data.totali.n, ""], ["Ricambi (centro costo)", eur(data.totali.ricambio), "text-sky-700"], ["Manodopera (centro costo)", eur(data.totali.manodopera), "text-violet-700"], ["Totale da incassare", eur(data.totali.totale), "text-emerald-700"]].map(([l, v, c]) => (
              <div key={l} className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">{l}</p><p className={`font-heading text-xl font-bold ${c}`} data-testid={`replab-tot-${l.split(" ")[0].toLowerCase()}`}>{v}</p></div>
            ))}
          </div>
        )}

        {data?.negozi.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500" data-testid="replab-vuoto">Nessuna riparazione lavorata dal laboratorio nel mese.{data.non_attribuite > 0 && " Attiva \"Includi non attribuite\" per vedere quelle senza tecnico registrato."}</p>}

        {data?.negozi.map((g) => (
          <div key={g.store_id} className="rounded-xl border border-slate-200" data-testid={`replab-negozio-${g.store_id}`}>
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm">
              <span className="font-heading font-semibold text-slate-900">{g.negozio}</span>
              <span className="text-xs text-slate-500">{g.n} rip. · {g.n_ricambio} con ricambio · {g.n_manodopera} solo manodopera</span>
              <span className="ml-auto text-xs text-slate-600">Ricambi {eur(g.ricambio)} · Manodopera {eur(g.manodopera)} · <b className="text-emerald-700" data-testid={`replab-negozio-tot-${g.store_id}`}>Totale {eur(g.totale)}</b></span>
            </div>
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-1.5">Data</th><th className="px-2 py-1.5">N.</th><th className="px-2 py-1.5">Cliente / dispositivo</th><th className="px-2 py-1.5">Tipo</th><th className="px-2 py-1.5">Min.</th><th className="px-2 py-1.5">Ricambio</th><th className="px-2 py-1.5">Manodopera</th><th className="px-4 py-1.5">Totale</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {g.righe.map((r) => (
                  <tr key={r.id} className={r.attribuita ? "" : "text-slate-500"}>
                    <td className="px-4 py-1.5">{r.data}</td><td className="px-2 py-1.5 font-medium">{r.numero}</td>
                    <td className="px-2 py-1.5">{r.cliente} <span className="text-xs text-slate-500">{r.dispositivo}{r.guasto ? ` · ${r.guasto}` : ""}</span>{!r.attribuita && <span className="ml-1 text-xs text-amber-700">(non attribuita)</span>}</td>
                    <td className="px-2 py-1.5"><span className={`status-badge ${r.tipo === "ricambio" ? "bg-sky-500/15 text-sky-700 border-sky-300" : "bg-violet-500/15 text-violet-700 border-violet-300"}`}>{r.tipo === "ricambio" ? `Ricambio${r.tipo_ricambio ? ` · ${r.tipo_ricambio}` : ""}` : "Solo manodopera"}</span></td>
                    <td className="px-2 py-1.5">{r.minuti || "-"}</td><td className="px-2 py-1.5">{eur(r.ricambio)}</td><td className="px-2 py-1.5">{eur(r.manodopera)}</td><td className="px-4 py-1.5 font-semibold">{eur(r.totale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  );
}
