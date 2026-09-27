import { useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";

export const CompensiTrattenute = ({ meta, reload }) => {
  const [form, setForm] = useState(Object.fromEntries(meta.stores.map((s) => [s.id, { trattenuta_pct: s.trattenuta_pct || 0, trattenuta_iva: !!s.trattenuta_iva }])));
  const salva = async (s) => {
    try { await api.patch(`/compensi/trattenute/${s.id}`, { ...form[s.id], trattenuta_pct: parseFloat(form[s.id].trattenuta_pct) || 0 }); toast.success(`Trattenuta ${s.nome} salvata`); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <p className="border-b border-slate-100 px-5 py-3 text-sm text-slate-500">Percentuale trattenuta sul totale lordo del negozio. Es. Tirano/Sondalo 15% esente IVA, Grosio 15% + IVA 22%.</p>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-2">Negozio</th><th className="px-3 py-2">Trattenuta %</th><th className="px-3 py-2">+ IVA 22%</th><th className="px-3 py-2"></th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          {meta.stores.map((s) => (
            <tr key={s.id} data-testid={`trattenuta-row-${s.id}`}>
              <td className="px-5 py-2 font-medium text-slate-900">{s.nome}</td>
              <td className="px-3 py-2"><Input type="number" step="0.5" className="w-24" value={form[s.id].trattenuta_pct} onChange={(e) => setForm({ ...form, [s.id]: { ...form[s.id], trattenuta_pct: e.target.value } })} data-testid={`trattenuta-pct-${s.id}`} /></td>
              <td className="px-3 py-2"><Switch checked={form[s.id].trattenuta_iva} onCheckedChange={(v) => setForm({ ...form, [s.id]: { ...form[s.id], trattenuta_iva: v } })} data-testid={`trattenuta-iva-${s.id}`} /></td>
              <td className="px-3 py-2"><Button size="sm" variant="outline" onClick={() => salva(s)} data-testid={`trattenuta-salva-${s.id}`}>Salva</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
