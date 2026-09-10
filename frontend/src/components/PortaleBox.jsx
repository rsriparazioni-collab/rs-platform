import { useEffect, useState } from "react";
import { ExternalLink, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { fmtDate } from "../lib/constants";

const SEZ_BY_TIPO = { sim: "mobile", internet: "fisso", fisso: "fisso", riparazione: "riparazioni" };

export function usePortale(sezione, operatore) {
  const [portale, setPortale] = useState(null);
  useEffect(() => {
    if (!sezione || !operatore) { setPortale(null); return; }
    api.get("/portali").then((r) => {
      setPortale(r.data.find((p) => p.sezione === sezione && p.operatore === String(operatore).trim().toUpperCase()) || null);
    }).catch(() => setPortale(null));
  }, [sezione, operatore]);
  return portale;
}

export function apriPortaleDopoSalvataggio(portali, sezione, operatore) {
  const p = portali.find((x) => x.sezione === sezione && x.operatore === String(operatore || "").trim().toUpperCase());
  if (!p) return;
  toast.success(`Prossimo passo: inserisci su ${p.nome || p.operatore}`, {
    duration: 15000,
    action: { label: "Apri portale", onClick: () => window.open(p.url, "_blank", "noopener") },
  });
}

export default function PortaleBox({ kind, id, tipo, sezione: sezioneProp, operatore, insertedAt, insertedBy, onChanged }) {
  const sezione = sezioneProp || SEZ_BY_TIPO[tipo];
  const portale = usePortale(sezione, operatore);
  const [busy, setBusy] = useState(false);
  if (!portale) return null;

  const toggle = async () => {
    setBusy(true);
    try {
      await api.post(`/${kind === "cliente" ? "clients" : "servizi"}/${id}/portale-inserito`, { inserito: !insertedAt });
      onChanged?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <div className={`rounded-xl border p-3 ${insertedAt ? "border-emerald-200 bg-emerald-50/50" : "border-sky-200 bg-sky-50/50"}`} data-testid="portale-box">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 text-sm">
          <p className="font-semibold text-slate-800">Portale {portale.nome || portale.operatore} <span className="text-xs font-normal text-slate-500">({portale.operatore})</span></p>
          <p className="text-xs text-slate-500">
            {insertedAt ? <><CheckCircle2 className="mr-1 inline h-3 w-3 text-emerald-600" />Inserito sul portale il {fmtDate(insertedAt)}{insertedBy ? ` da ${insertedBy}` : ""}</> : (portale.note || "Da inserire sul portale dell'operatore")}
          </p>
        </div>
        <Button size="sm" className="gap-1 bg-sky-700 hover:bg-sky-800" onClick={() => window.open(portale.url, "_blank", "noopener")} data-testid="portale-open-button">
          <ExternalLink className="h-3.5 w-3.5" /> Apri portale
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={toggle} data-testid="portale-flag-button">
          {insertedAt ? "Segna da inserire" : "Segna inserito"}
        </Button>
      </div>
    </div>
  );
}
