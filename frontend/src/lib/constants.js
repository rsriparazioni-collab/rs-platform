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

export const RUOLI = { admin: "Amministratore", operatore: "Operatore", negozio: "Negozio", tecnico: "Tecnico" };

export const SECTIONS = [
  { id: "energia", label: "Energia" },
  { id: "riparazioni", label: "Riparazioni" },
  { id: "telefonia", label: "Telefonia" },
];

export const RIP_STATI = [
  { id: "ingresso", label: "Ingresso", badge: "bg-sky-500/15 text-sky-700 border-sky-300" },
  { id: "attesa_ricambio_cliente", label: "Attesa ricambio (disp. col cliente)", badge: "bg-amber-500/15 text-amber-700 border-amber-300" },
  { id: "attesa_ricambio_carico", label: "Attesa ricambio (disp. in carico)", badge: "bg-orange-500/15 text-orange-700 border-orange-300" },
  { id: "in_attesa_cliente", label: "In attesa cliente", badge: "bg-yellow-500/15 text-yellow-700 border-yellow-300" },
  { id: "preventivo", label: "Preventivo", badge: "bg-violet-500/15 text-violet-700 border-violet-300" },
  { id: "in_lavorazione", label: "In lavorazione", badge: "bg-cyan-500/15 text-cyan-700 border-cyan-300" },
  { id: "pronto", label: "Pronto (in laboratorio)", badge: "bg-emerald-500/15 text-emerald-700 border-emerald-300" },
  { id: "pronto_ritiro", label: "Pronto da ritirare (in negozio)", badge: "bg-teal-500/15 text-teal-700 border-teal-300" },
  { id: "consegnato", label: "Consegnato", badge: "bg-green-600/15 text-green-800 border-green-300" },
  { id: "non_riparabile", label: "Non riparabile", badge: "bg-rose-500/15 text-rose-700 border-rose-300" },
];

export const ripStatoLabel = (id) => RIP_STATI.find((s) => s.id === id)?.label || id || "-";
export const ripStatoBadge = (id) => RIP_STATI.find((s) => s.id === id)?.badge || "bg-slate-500/15 text-slate-700 border-slate-300";

export const SERVIZIO_TIPI = [
  { id: "riparazione", label: "Riparazione", section: "riparazioni" },
  { id: "accessori", label: "Accessori", section: "telefonia" },
  { id: "vendita", label: "Vendita", section: "telefonia" },
  { id: "sim", label: "Mobile (SIM)", section: "telefonia" },
  { id: "internet", label: "Fisso / Internet", section: "telefonia" },
  { id: "fisso", label: "Fisso (voce)", section: "telefonia" },
];

export const servizioTipoLabel = (id) => SERVIZIO_TIPI.find((t) => t.id === id)?.label || id || "-";

export const TEL_OPERATORS = {
  sim: ["WINDTRE", "VERY", "TIM", "KENA", "FASTWEB", "HO", "ILIAD", "LYCA", "DIGI", "ENEL"],
  internet: ["EOLO", "WINDTRE", "FASTWEB", "ILIAD", "ENEL"],
  fisso: ["EOLO", "WINDTRE", "FASTWEB", "ILIAD", "ENEL"],
};


export const SBLOCCO_TIPI = [
  { id: "nessuno", label: "Nessun blocco" },
  { id: "simbolo", label: "Simbolo (sequenza)" },
  { id: "pin", label: "PIN numerico" },
  { id: "password", label: "Password" },
];

export const MAGAZZINO_CATEGORIE = [
  { id: "display", label: "Display" },
  { id: "ricambi", label: "Ricambi" },
  { id: "accessori", label: "Accessori" },
  { id: "sim", label: "SIM" },
  { id: "rigenerati", label: "Rigenerati / Usati" },
  { id: "altro", label: "Altro" },
];

export const magazzinoCategoriaLabel = (id) =>
  MAGAZZINO_CATEGORIE.find((c) => c.id === id)?.label || id || "-";
export const ENEL_OPERAZIONI = [
  { id: "swa", label: "SWA – Switch da altro operatore" },
  { id: "voltura", label: "Voltura" },
  { id: "voltura_swa", label: "Voltura con switch (VSA/SWA)" },
  { id: "subentro", label: "Subentro" },
  { id: "allaccio", label: "Allaccio" },
  { id: "prima_attivazione", label: "Prima attivazione" },
  { id: "altro", label: "Altro" },
];
export const enelOperazioneLabel = (id) => ENEL_OPERAZIONI.find((o) => o.id === id)?.label || id || "";



export const TIPO_CLIENTE = {
  privato: { label: "Privato", badge: "bg-slate-500/10 text-slate-600 border-slate-300" },
  ditta_individuale: { label: "Ditta individuale", badge: "bg-orange-500/15 text-orange-700 border-orange-300" },
  societa: { label: "Società", badge: "bg-indigo-500/15 text-indigo-700 border-indigo-300" },
};
export const tipoClienteInfo = (t) => TIPO_CLIENTE[t === "business" ? "societa" : (t || "privato")];
export const isBusinessCliente = (t) => !!t && t !== "privato";


export const PREMIUM_STEPS = {
  1: { label: "Step 1", badge: "bg-slate-500/15 text-slate-700 border-slate-300" },
  2: { label: "Step 2", badge: "bg-sky-500/15 text-sky-700 border-sky-300" },
  3: { label: "Premium", badge: "bg-amber-500/20 text-amber-800 border-amber-400" },
};

export const fmtDateTime = (iso) => {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("it-IT", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
};
