export const LAVORAZIONI = [
  { id: "cambiare", label: "Da Cambiare", badge: "bg-amber-500/15 text-amber-700 border-amber-300" },
  { id: "non_cambiare", label: "Non Cambiare", badge: "bg-slate-500/15 text-slate-700 border-slate-300" },
  { id: "cambio_effettuato", label: "Cambio Effettuato", badge: "bg-emerald-500/15 text-emerald-700 border-emerald-300" },
  { id: "in_quotazione", label: "In Quotazione", badge: "bg-sky-500/15 text-sky-700 border-sky-300" },
  { id: "richieste_bollette", label: "Richieste Bollette", badge: "bg-violet-500/15 text-violet-700 border-violet-300" },
  { id: "in_attesa_ok", label: "In Attesa OK Cliente", badge: "bg-indigo-500/15 text-indigo-700 border-indigo-300" },
  { id: "problema_tecnico", label: "Problema Tecnico", badge: "bg-rose-500/15 text-rose-700 border-rose-300" },
  { id: "da_quotare", label: "Da Quotare", badge: "bg-cyan-500/15 text-cyan-700 border-cyan-300" },
  { id: "contattare_cliente", label: "Contattare Cliente", badge: "bg-yellow-500/15 text-yellow-700 border-yellow-300" },
  { id: "non_vuole_cambiare", label: "Non Vuole Cambiare", badge: "bg-zinc-500/15 text-zinc-700 border-zinc-300" },
  { id: "passa_in_negozio", label: "Passa in Negozio", badge: "bg-teal-500/15 text-teal-700 border-teal-300" },
  { id: "attesa_documenti", label: "Attesa Documenti", badge: "bg-orange-500/15 text-orange-700 border-orange-300" },
  { id: "rinnovato", label: "Rinnovato", badge: "bg-green-600/15 text-green-800 border-green-300" },
];

export const lavorazioneLabel = (id) =>
  LAVORAZIONI.find((l) => l.id === id)?.label || id || "-";

export const lavorazioneBadge = (id) =>
  LAVORAZIONI.find((l) => l.id === id)?.badge || "bg-slate-500/15 text-slate-700 border-slate-300";

export const fmtDate = (d) => {
  if (!d) return "-";
  try {
    return new Date(d).toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return d;
  }
};

export const RUOLI = { admin: "Amministratore", operatore: "Operatore", negozio: "Negozio" };
