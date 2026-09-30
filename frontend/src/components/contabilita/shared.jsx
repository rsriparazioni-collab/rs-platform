export const MESI = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];

export const eur = (v) => `€ ${(Number(v) || 0).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const PeriodoPicker = ({ anno, mese, setAnno, setMese, soloAnno }) => (
  <div className="flex items-center gap-2" data-testid="periodo-picker">
    {!soloAnno && (
      <select value={mese} onChange={(e) => setMese(Number(e.target.value))} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="periodo-mese">
        {MESI.slice(1).map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
      </select>
    )}
    <input type="number" value={anno} onChange={(e) => setAnno(Number(e.target.value))} className="h-9 w-24 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="periodo-anno" />
  </div>
);

export const Num = ({ value, onChange, testid, className = "" }) => (
  <input type="number" step="0.01" inputMode="decimal" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
    className={`h-8 w-full rounded border border-slate-200 px-2 text-right text-sm tabular-nums focus:border-sky-400 focus:outline-none ${className}`} data-testid={testid} />
);
