import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import api from "../lib/api";

const COLORS = ["#0f766e", "#0369a1", "#b45309", "#7c3aed", "#be123c", "#4d7c0f", "#c026d3", "#475569"];

export default function MarginiChart() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard/margini-12-mesi").then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="margini-chart-panel">
      <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
        <BarChart3 className="h-4 w-4 text-slate-500" />
        <h2 className="font-heading text-lg font-semibold text-slate-800">Margine riparazioni · ultimi 12 mesi per negozio</h2>
        <span className="ml-auto text-xs text-slate-500">€ netti IVA, dopo costi</span>
      </div>
      <div className="h-72 p-4" data-testid="margini-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.dati} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#64748b" }} />
            <YAxis tick={{ fontSize: 12, fill: "#64748b" }} tickFormatter={(v) => `€${v}`} width={64} />
            <Tooltip formatter={(v, n) => [`€ ${Number(v).toFixed(2)}`, n]} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {data.negozi.map((n, i) => <Bar key={n} dataKey={n} stackId="m" fill={COLORS[i % COLORS.length]} radius={i === data.negozi.length - 1 ? [4, 4, 0, 0] : 0} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
