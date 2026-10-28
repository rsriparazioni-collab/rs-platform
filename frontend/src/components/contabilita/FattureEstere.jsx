import { useCallback, useEffect, useState } from "react";
import { Globe, Plus, Trash2, Check, Copy, Send, Paperclip } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { PeriodoPicker, eur } from "./shared";

const EMPTY = { centro_id: "", data: new Date().toISOString().slice(0, 10), fornitore: "", paese: "", tipo: "ue_rc", numero: "", imponibile: "", iva_pct: 22, iva_dogana: "", note: "" };
const TIPO_CLS = { ue_rc: "bg-sky-100 text-sky-800", extra_ue: "bg-amber-100 text-amber-900", ebay: "bg-violet-100 text-violet-800" };

export const FattureEstere = ({ anno, mese, setAnno, setMese, centri = [] }) => {
  const [d, setD] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [tel, setTel] = useState("");
  const load = useCallback(() => api.get("/estere", { params: { anno, mese } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [anno, mese]);
  useEffect(() => { load(); api.get("/estere/config").then((r) => setTel(r.data.telefono || "")).catch(() => {}); }, [load]);
  useEffect(() => { if (!form.centro_id && centri[0]) setForm((f) => ({ ...f, centro_id: centri[0].id })); }, [centri, form.centro_id]);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const rc = form.tipo !== "extra_ue";
  const imp = Number(form.imponibile) || 0;
  const anteprima = rc ? imp * (Number(form.iva_pct) || 0) / 100 : Number(form.iva_dogana) || 0;
  const salva = async () => {
    try {
      await api.post("/estere", { ...form, imponibile: imp, iva_pct: Number(form.iva_pct) || 0, iva_dogana: Number(form.iva_dogana) || 0 });
      toast.success("Fattura estera registrata"); setForm({ ...EMPTY, centro_id: form.centro_id, tipo: form.tipo }); load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const inviata = async (f) => { try { await api.post(`/estere/fattura/${f.id}/inviata`, { inviata: !f.inviata_at }); load(); } catch (e) { toast.error(apiError(e)); } };
  const allegato = async (f, e) => {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try { await api.post(`/estere/fattura/${f.id}/allegato`, fd); toast.success("Allegato caricato"); load(); } catch (err) { toast.error(apiError(err)); }
  };
  const del = async (f) => { if (!window.confirm(`Eliminare la fattura ${f.fornitore} ${eur(f.imponibile)}?`)) return; try { await api.delete(`/estere/fattura/${f.id}`); load(); } catch (e) { toast.error(apiError(e)); } };
  const copia = async () => { try { const r = await api.get("/estere/riepilogo-commercialista", { params: { anno, mese } }); await navigator.clipboard.writeText(r.data.testo); toast.success("Testo copiato: incollalo nella mail al commercialista"); } catch (e) { toast.error(apiError(e)); } };
  const salvaTel = async () => { try { await api.put("/estere/config", { telefono: tel }); toast.success("Numero promemoria salvato"); } catch (e) { toast.error(apiError(e)); } };
  const nomeCentro = (id) => centri.find((c) => c.id === id)?.nome || id;
  return (
    <div className="space-y-4" data-testid="estere-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><Globe className="h-5 w-5 text-sky-600" /> Fatture estere (UE / extra-UE / eBay)</h2>
        <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
      </div>
      <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-3 text-xs text-slate-700">
        <b>Regola:</b> le fatture UE con P.IVA ed eBay vanno integrate con IVA 22% (reverse charge, saldo zero) e <b>trasmesse allo SdI entro il 15 del mese successivo</b> → caricale appena arrivano, il 1° del mese arriva il promemoria e il 10 l'ultimo avviso. Extra-UE: l'IVA è quella pagata in dogana.
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span>Promemoria WhatsApp (1, 10 e 28 del mese) al numero:</span>
          <Input value={tel} onChange={(e) => setTel(e.target.value)} className="h-7 w-40 bg-white text-xs" data-testid="estere-tel" />
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={salvaTel} data-testid="estere-tel-save">Salva</Button>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-3" data-testid="estere-form">
        <div className="grid gap-2 md:grid-cols-4">
          <select value={form.centro_id} onChange={(e) => set("centro_id", e.target.value)} className="h-9 rounded-lg border border-slate-200 px-2 text-sm" data-testid="estere-centro">
            {centri.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>
          <select value={form.tipo} onChange={(e) => set("tipo", e.target.value)} className="h-9 rounded-lg border border-slate-200 px-2 text-sm" data-testid="estere-tipo">
            {Object.entries(d?.tipi || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <Input type="date" value={form.data} onChange={(e) => set("data", e.target.value)} data-testid="estere-data" />
          <Input placeholder="Fornitore (es. eBay S.à r.l.)" value={form.fornitore} onChange={(e) => set("fornitore", e.target.value)} data-testid="estere-fornitore" />
          <Input placeholder="Paese (es. LU, DE, CN)" value={form.paese} onChange={(e) => set("paese", e.target.value)} data-testid="estere-paese" />
          <Input placeholder="Numero fattura" value={form.numero} onChange={(e) => set("numero", e.target.value)} data-testid="estere-numero" />
          <Input type="number" step="0.01" placeholder="Imponibile €" value={form.imponibile} onChange={(e) => set("imponibile", e.target.value)} data-testid="estere-imponibile" />
          {rc ? <Input type="number" step="1" placeholder="IVA %" value={form.iva_pct} onChange={(e) => set("iva_pct", e.target.value)} data-testid="estere-iva-pct" />
              : <Input type="number" step="0.01" placeholder="IVA pagata in dogana €" value={form.iva_dogana} onChange={(e) => set("iva_dogana", e.target.value)} data-testid="estere-iva-dogana" />}
          <Input placeholder="Note" value={form.note} onChange={(e) => set("note", e.target.value)} className="md:col-span-3" data-testid="estere-note" />
          <Button onClick={salva} disabled={!form.fornitore || !imp} data-testid="estere-save"><Plus className="mr-1 h-4 w-4" /> Registra</Button>
        </div>
        {imp > 0 && <p className="mt-2 text-xs text-slate-500" data-testid="estere-anteprima">{rc ? `IVA integrata ${eur(anteprima)} (a debito e a credito, saldo 0) · costo per il PDP ${eur(imp)}` : `IVA dogana ${eur(anteprima)} · costo per il PDP ${eur(imp + anteprima)}`}</p>}
      </div>
      {d && (
        <div className="rounded-xl border border-slate-200 bg-white" data-testid="estere-lista">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2 text-sm">
            <span><b>{d.items.length}</b> fatture · imponibile <b>{eur(d.totali.imponibile)}</b> · IVA integrata {eur(d.totali.iva_integrata)} · IVA dogana {eur(d.totali.iva_dogana)} · <span className={d.totali.da_inviare ? "font-semibold text-rose-700" : "text-emerald-700"} data-testid="estere-da-inviare">{d.totali.da_inviare} da inviare</span></span>
            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={copia} data-testid="estere-copia"><Copy className="mr-1 h-3 w-3" /> Testo per il commercialista</Button>
          </div>
          {d.items.length === 0 ? <p className="px-4 py-6 text-center text-sm text-slate-400">Nessuna fattura estera nel mese.</p> : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-3 py-2 text-left">Data</th><th className="px-3 py-2 text-left">Fornitore</th><th className="px-3 py-2 text-left">Tipo</th><th className="px-3 py-2 text-right">Imponibile</th><th className="px-3 py-2 text-right">IVA</th><th className="px-3 py-2 text-left">Entità</th><th className="px-3 py-2">Inviata</th><th className="px-3 py-2">Allegato</th><th /></tr></thead>
              <tbody>
                {d.items.map((f) => (
                  <tr key={f.id} className="border-t border-slate-100" data-testid={`estera-${f.id}`}>
                    <td className="px-3 py-2 font-mono text-xs">{f.data}</td>
                    <td className="px-3 py-2"><b>{f.fornitore}</b> <span className="text-xs text-slate-400">{f.paese} {f.numero && `n.${f.numero}`}</span>{f.note && <div className="text-xs text-slate-400">{f.note}</div>}</td>
                    <td className="px-3 py-2"><span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${TIPO_CLS[f.tipo]}`}>{d.tipi[f.tipo].split(" (")[0]}</span></td>
                    <td className="px-3 py-2 text-right tabular-nums">{eur(f.imponibile)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-500">{f.iva_integrata ? `${eur(f.iva_integrata)} RC` : `${eur(f.iva_dogana || 0)} dogana`}</td>
                    <td className="px-3 py-2 text-xs">{nomeCentro(f.centro_id)}</td>
                    <td className="px-3 py-2 text-center"><button type="button" onClick={() => inviata(f)} className={`rounded-full px-2 py-0.5 text-[11px] ${f.inviata_at ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`} data-testid={`estera-inviata-${f.id}`}>{f.inviata_at ? <><Check className="inline h-3 w-3" /> inviata</> : <><Send className="inline h-3 w-3" /> da inviare</>}</button></td>
                    <td className="px-3 py-2 text-center text-xs">
                      {f.allegato_path ? <a href={`${process.env.REACT_APP_BACKEND_URL}/api/estere/fattura/${f.id}/allegato`} target="_blank" rel="noreferrer" className="text-sky-700 hover:underline" data-testid={`estera-allegato-${f.id}`}><Paperclip className="inline h-3 w-3" /> {f.allegato_nome?.slice(0, 18)}</a>
                        : <label className="cursor-pointer text-slate-500 hover:text-sky-700" data-testid={`estera-allegato-up-${f.id}`}><Paperclip className="inline h-3 w-3" /> carica PDF<input type="file" accept=".pdf,image/*" className="hidden" onChange={(e) => allegato(f, e)} /></label>}
                    </td>
                    <td className="px-3 py-2 text-right"><button type="button" onClick={() => del(f)} className="text-slate-300 hover:text-rose-600" data-testid={`estera-del-${f.id}`}><Trash2 className="h-4 w-4" /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};
