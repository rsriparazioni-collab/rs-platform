import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Mail, MessageCircle } from "lucide-react";
import api, { apiError, downloadBlob } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI, PeriodoPicker, eur } from "./shared";
import { GiornoDialog } from "./GiornoDialog";
import { SpeseCassa } from "./SpeseCassa";

export const Corrispettivi = ({ storeId, anno, mese, setAnno, setMese }) => {
  const [dati, setDati] = useState(null);
  const [giorno, setGiorno] = useState(null);
  const load = useCallback(() => api.get("/contabilita/corrispettivi", { params: { store_id: storeId, anno, mese } }).then((r) => setDati(r.data)).catch((e) => toast.error(apiError(e))), [storeId, anno, mese]);
  useEffect(() => { load(); }, [load]);

  const inviaEmail = async () => {
    try { const r = await api.post("/contabilita/corrispettivi/invia-email", null, { params: { store_id: storeId, anno, mese } }); r.data.inviato ? toast.success(`Email inviata a ${r.data.to}`) : toast.warning(r.data.motivo); }
    catch (e) { toast.error(apiError(e)); }
  };
  const inviaWa = async (data) => {
    try { const r = await api.post("/contabilita/corrispettivi/invia-whatsapp", null, { params: { store_id: storeId, data } }); const ok = r.data.every((x) => x.ok); ok ? toast.success("WhatsApp inviato") : toast.error(r.data.find((x) => !x.ok)?.error || "Numero WhatsApp non impostato"); }
    catch (e) { toast.error(apiError(e)); }
  };
  if (!dati) return null;
  const t = dati.totali;
  const oggi = new Date().toISOString().slice(0, 10);
  return (
    <div className="space-y-6" data-testid="corrispettivi-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => setGiorno(dati.righe.find((r) => r.data === oggi) || dati.righe[0])} data-testid="corrispettivo-oggi-btn">+ Corrispettivo di oggi</Button>
          <Button size="sm" variant="outline" onClick={() => downloadBlob(`/contabilita/corrispettivi/pdf?store_id=${storeId}&anno=${anno}&mese=${mese}`, `Corrispettivi_${dati.store.nome}_${anno}-${mese}.pdf`)} data-testid="corrispettivi-pdf-btn"><Download className="mr-1 h-4 w-4" /> PDF mese</Button>
          <Button size="sm" variant="outline" onClick={inviaEmail} data-testid="corrispettivi-email-btn"><Mail className="mr-1 h-4 w-4" /> Invia email mese</Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" data-testid="corrispettivi-totali">
        {[["Totale corrispettivi", t.totale, "text-slate-900"], ["Contanti", t.contanti, "text-emerald-700"], ["POS", t.pos, "text-sky-700"], ["Spese contanti", t.spese_contanti, "text-rose-700"], ["IVA 22% scorporata", t.iva, "text-amber-700"]].map(([l, v, c]) => (
          <div key={l} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs uppercase tracking-wide text-slate-500">{l}</p><p className={`mt-1 text-xl font-semibold tabular-nums ${c}`}>{eur(v)}</p></div>
        ))}
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm" data-testid="corrispettivi-table">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>{["Giorno", "Riparazioni", "Merce", "Art. 74", "Fatture", "Totale", "Contanti", "POS", "Versati", ""].map((h) => <th key={h} className="px-3 py-2 text-right first:text-left">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {dati.righe.map((r) => (
              <tr key={r.data} className={`cursor-pointer hover:bg-sky-50 ${r.vuoto ? "text-slate-400" : ""}`} onClick={() => setGiorno(r)} data-testid={`corr-row-${r.data}`}>
                <td className="px-3 py-1.5 font-medium">{r.data.slice(8)} {MESI[mese].slice(0, 3)}</td>
                {r.vuoto ? <td colSpan={8} className="px-3 py-1.5 text-right text-xs">— non inserito —</td> : (
                  ["riparazioni", "merce", "art74", "fatture", "totale", "contanti", "pos", "versati"].map((k) => <td key={k} className={`px-3 py-1.5 text-right tabular-nums ${k === "totale" ? "font-semibold" : ""}`}>{r[k] ? eur(r[k]) : ""}</td>)
                )}
                <td className="px-2 py-1.5 text-right">{!r.vuoto && <button className="text-slate-400 hover:text-emerald-600" title="Invia WhatsApp del giorno" onClick={(e) => { e.stopPropagation(); inviaWa(r.data); }} data-testid={`corr-wa-${r.data}`}><MessageCircle className="h-4 w-4" /></button>}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-slate-50 font-semibold">
            <tr><td className="px-3 py-2">Totale</td>{["riparazioni", "merce", "art74", "fatture", "totale", "contanti", "pos", "versati"].map((k) => <td key={k} className="px-3 py-2 text-right tabular-nums" data-testid={`corr-tot-${k}`}>{eur(t[k])}</td>)}<td /></tr>
          </tfoot>
        </table>
      </div>
      <SpeseCassa storeId={storeId} anno={anno} mese={mese} spese={dati.spese} reload={load} />
      {giorno && <GiornoDialog storeId={storeId} riga={giorno} onClose={() => setGiorno(null)} onSaved={() => { setGiorno(null); load(); }} />}
    </div>
  );
};
