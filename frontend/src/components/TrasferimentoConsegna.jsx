import { useState } from "react";
import { Truck, PackageCheck, User, Wallet } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

const STATO = { da_consegnare: ["Da consegnare", "bg-slate-500/10 text-slate-600 border-slate-300"], in_viaggio: ["In viaggio", "bg-sky-500/15 text-sky-700 border-sky-300"], arrivato: ["Arrivato", "bg-emerald-500/15 text-emerald-700 border-emerald-300"] };
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "");

export const TrasferimentoConsegna = ({ r, onChanged }) => {
  const [edit, setEdit] = useState(false);
  const [portato, setPortato] = useState(r.portato_da || "");
  const [busy, setBusy] = useState(false);
  const stato = r.stato_consegna || "da_consegnare";
  const salva = async (body) => {
    setBusy(true);
    try { await api.patch(`/magazzino/trasferimenti/${r.id}/consegna`, body); setEdit(false); onChanged(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs" data-testid={`trasferimento-consegna-${r.id}`}>
      <span className={`status-badge ${STATO[stato][1]}`} data-testid={`trasferimento-stato-${r.id}`}><Truck className="h-3 w-3" /> {STATO[stato][0]}</span>
      {r.portato_da ? <span className="text-slate-600" data-testid={`trasferimento-portato-${r.id}`}><User className="inline h-3 w-3" /> {r.portato_da}</span> : null}
      {stato === "in_viaggio" && r.partito_at && <span className="text-slate-400">partito {fmt(r.partito_at)}</span>}
      {stato === "arrivato" && r.consegnato_at && <span className="text-slate-400">arrivato {fmt(r.consegnato_at)}</span>}
      <button type="button" onClick={() => salva({ pagato: !r.pagato })} disabled={busy} className={`status-badge cursor-pointer ${r.pagato ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-amber-500/15 text-amber-700 border-amber-300"}`} data-testid={`trasferimento-pagato-${r.id}`}>
        <Wallet className="h-3 w-3" /> {r.pagato ? `Pagato${r.pagato_at ? ` ${fmt(r.pagato_at)}` : ""}` : "Non pagato"}
      </button>
      {!edit && stato !== "arrivato" && <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => setEdit(true)} data-testid={`trasferimento-consegna-edit-${r.id}`}>{stato === "da_consegnare" ? "Parte con…" : "Segna arrivato"}</Button>}
      {edit && (
        <span className="flex items-center gap-1">
          <input value={portato} onChange={(e) => setPortato(e.target.value)} placeholder="Chi lo porta" className="h-6 w-32 rounded border border-slate-300 px-1.5 text-[11px]" data-testid={`trasferimento-portato-input-${r.id}`} />
          {stato === "da_consegnare" && <Button type="button" size="sm" className="h-6 px-2 text-[11px]" disabled={busy || !portato.trim()} onClick={() => salva({ portato_da: portato, stato_consegna: "in_viaggio" })} data-testid={`trasferimento-parte-${r.id}`}><Truck className="h-3 w-3" /> Parte ora</Button>}
          <Button type="button" size="sm" className="h-6 bg-emerald-600 px-2 text-[11px] hover:bg-emerald-700" disabled={busy} onClick={() => salva({ portato_da: portato, stato_consegna: "arrivato" })} data-testid={`trasferimento-arrivato-${r.id}`}><PackageCheck className="h-3 w-3" /> Arrivato</Button>
          <button type="button" className="text-[11px] text-slate-400 hover:underline" onClick={() => setEdit(false)}>annulla</button>
        </span>
      )}
    </div>
  );
};
