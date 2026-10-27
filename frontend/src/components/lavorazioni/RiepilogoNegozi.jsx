const Cell = ({ v, cls = "text-slate-800", testid }) => <td className={`px-3 py-2 text-center font-semibold ${v ? cls : "text-slate-300"}`} data-testid={testid}>{v}</td>;

export const RiepilogoNegozi = ({ negozi, totali, storeId, onSelect }) => (
  <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white" data-testid="riepilogo-negozi">
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-3 py-2 text-left">Negozio</th>
          <th className="px-3 py-2">Da lavorare</th>
          <th className="px-3 py-2">Lavorate</th>
          <th className="px-3 py-2">Da reinserire</th>
          <th className="px-3 py-2">Ferme &gt;7 gg</th>
          <th className="px-3 py-2">Senza presa in carico</th>
        </tr>
      </thead>
      <tbody>
        <tr className={`cursor-pointer border-t border-slate-100 hover:bg-sky-50 ${!storeId ? "bg-sky-50" : ""}`} onClick={() => onSelect("")} data-testid="negozio-row-tutti">
          <td className="px-3 py-2 font-bold text-slate-900">Tutti i negozi</td>
          <Cell v={totali.da_lavorare} cls="text-sky-700" testid="tot-da-lavorare" />
          <Cell v={totali.lavorate} cls="text-emerald-700" testid="tot-lavorate" />
          <Cell v={totali.da_reinserire} cls="text-rose-700" testid="tot-da-reinserire" />
          <Cell v={totali.ferme} cls="text-red-600" testid="tot-ferme" />
          <Cell v={negozi.reduce((a, n) => a + n.senza_presa, 0)} cls="text-amber-700" />
        </tr>
        {negozi.map((n) => (
          <tr key={n.store_id} className={`cursor-pointer border-t border-slate-100 hover:bg-sky-50 ${storeId === n.store_id ? "bg-sky-50" : ""}`}
              onClick={() => onSelect(storeId === n.store_id ? "" : n.store_id)} data-testid={`negozio-row-${n.nome}`}>
            <td className="px-3 py-2 font-medium text-slate-800">{n.nome}</td>
            <Cell v={n.da_lavorare} cls="text-sky-700" />
            <Cell v={n.lavorate} cls="text-emerald-700" />
            <Cell v={n.da_reinserire} cls="text-rose-700" />
            <Cell v={n.ferme} cls="text-red-600" />
            <Cell v={n.senza_presa} cls="text-amber-700" />
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
