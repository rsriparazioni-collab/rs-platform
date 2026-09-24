import { useEffect, useState } from "react";
import { ExternalLink, CheckCircle2, Info } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { fmtDate } from "../lib/constants";
import CopiaDatiButton from "./CopiaDatiButton";

const SEZ_BY_TIPO = { sim: "mobile", internet: "fisso", fisso: "fisso", riparazione: "riparazioni" };
const norm = (v) => String(v || "").trim().toUpperCase();

function matchPortali(portali, sezione, operatore) {
  return portali.filter((p) => p.sezione === sezione && (p.operatore === "*" || p.operatore === norm(operatore)))
    .sort((a, b) => (a.operatore === "*") - (b.operatore === "*"));
}

export function apriPortaleDopoSalvataggio(portali, sezione, operatore) {
  const list = matchPortali(portali, sezione, operatore);
  const p = list.find((x) => x.operatore !== "*") || list[0];
  if (!p) return;
  toast.success(`Prossimo passo: ${p.url ? `inserisci su ${p.nome || p.operatore}` : p.note || p.nome}`, {
    duration: 15000,
    action: p.url ? { label: "Apri portale", onClick: () => window.open(p.url, "_blank", "noopener") } : undefined,
  });
}

export default function PortaleBox({ kind, id, tipo, sezione: sezioneProp, operatore, insertedAt, insertedBy, extraAt, extraBy, onChanged, cliente }) {
  const sezione = sezioneProp || SEZ_BY_TIPO[tipo];
  const [portali, setPortali] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/portali").then((r) => setPortali(r.data)).catch(() => {}); }, []);

  const list = matchPortali(portali, sezione, operatore);
  if (list.length === 0) return null;
  const principale = list.find((p) => p.operatore !== "*");
  const generici = list.filter((p) => p.operatore === "*");

  const flag = async (campo, value) => {
    setBusy(true);
    try {
      await api.post(`/${kind === "cliente" ? "clients" : "servizi"}/${id}/portale-inserito`, { inserito: value, campo });
      onChanged?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-2" data-testid="portale-box">
      {principale && (
        <div className={`rounded-xl border p-3 ${insertedAt ? "border-emerald-200 bg-emerald-50/50" : "border-sky-200 bg-sky-50/50"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex-1 text-sm">
              <p className="font-semibold text-slate-800">{principale.nome || principale.operatore} <span className="text-xs font-normal text-slate-500">({principale.operatore})</span></p>
              <p className="text-xs text-slate-500">
                {insertedAt ? <><CheckCircle2 className="mr-1 inline h-3 w-3 text-emerald-600" />Inserito il {fmtDate(insertedAt)}{insertedBy ? ` da ${insertedBy}` : ""}</> : (principale.note || "Da inserire sul portale dell'operatore")}
              </p>
            </div>
            {principale.url
              ? <Button size="sm" className="gap-1 bg-sky-700 hover:bg-sky-800" onClick={() => window.open(principale.url, "_blank", "noopener")} data-testid="portale-open-button"><ExternalLink className="h-3.5 w-3.5" /> Apri portale</Button>
              : <span className="inline-flex items-center gap-1 rounded-md bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800" data-testid="portale-info"><Info className="h-3.5 w-3.5" /> {principale.note || "Apri app"}</span>}
            <CopiaDatiButton cliente={cliente} />
            <Button size="sm" variant="outline" disabled={busy} onClick={() => flag("inserito", !insertedAt)} data-testid="portale-flag-button">
              {insertedAt ? "Segna da inserire" : "Segna inserito"}
            </Button>
          </div>
          {principale.flag_label && (
            <div className={`mt-2 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-xs ${extraAt ? "border-emerald-200 bg-white" : "border-amber-300 bg-amber-50"}`} data-testid="portale-extra">
              <label className="flex flex-1 items-center gap-2 font-semibold text-slate-800">
                <input type="checkbox" checked={Boolean(extraAt)} disabled={busy} onChange={(e) => flag("extra", e.target.checked)} data-testid="portale-extra-checkbox" />
                {principale.flag_label}
                {extraAt && <span className="font-normal text-slate-500">· {fmtDate(extraAt)}{extraBy ? ` da ${extraBy}` : ""}</span>}
              </label>
              {principale.flag_url && <Button size="sm" variant="outline" className="h-7 gap-1 text-xs" onClick={() => window.open(principale.flag_url, "_blank", "noopener")} data-testid="portale-extra-open"><ExternalLink className="h-3 w-3" /> Apri JOY</Button>}
            </div>
          )}
        </div>
      )}
      {generici.length > 0 && (
        <div className="rounded-xl border border-slate-200 p-3" data-testid="portale-generici">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">{sezione === "riparazioni" ? "Fornitori ricambi e telefoni" : "Passaggi / portali della sezione"}</p>
          <div className="flex flex-wrap gap-1.5">
            {generici.map((p) => (
              <Button key={p.id} size="sm" variant="outline" className="h-7 gap-1 text-xs" title={p.note} onClick={() => window.open(p.url, "_blank", "noopener")} data-testid={`portale-generico-${p.id}`}>
                <ExternalLink className="h-3 w-3" /> {p.nome}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
