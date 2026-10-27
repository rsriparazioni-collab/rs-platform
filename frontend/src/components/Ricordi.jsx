import { useCallback, useEffect, useState } from "react";
import { Heart, X, Cake } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Input } from "./ui/input";
import { Button } from "./ui/button";

const notify = () => window.dispatchEvent(new Event("ricordi-changed"));
const fmtData = (iso) => (iso ? iso.split("-").reverse().join("/") : "");

export const RicordiBox = ({ clientId, onBirthdayLoaded }) => {
  const [data, setData] = useState(null);
  const [testo, setTesto] = useState("");
  const load = useCallback(() => {
    if (!clientId) return;
    api.get(`/clients/${clientId}/ricordi`).then((r) => { setData(r.data); onBirthdayLoaded?.(r.data.data_nascita); }).catch(() => setData({ ricordi: [] }));
  }, [clientId, onBirthdayLoaded]);
  useEffect(() => { load(); }, [load]);
  if (!data) return null;
  const add = async () => {
    if (!testo.trim()) return;
    try { await api.post(`/clients/${clientId}/ricordi`, { testo }); setTesto(""); load(); notify(); } catch (e) { toast.error(apiError(e)); }
  };
  const del = async (id) => { try { await api.delete(`/clients/${clientId}/ricordi/${id}`); load(); notify(); } catch (e) { toast.error(apiError(e)); } };
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-3" data-testid="ricordi-box">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-amber-800"><Heart className="h-3.5 w-3.5" /> Da ricordare</p>
        {data.data_nascita && (
          <span className="flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs text-amber-900" data-testid="ricordi-compleanno">
            <Cake className="h-3 w-3" /> Compleanno {fmtData(data.data_nascita)}{data.nascita_da_cf ? " (dal codice fiscale)" : ""}
          </span>
        )}
      </div>
      {data.ricordi.length === 0
        ? <p className="mt-1.5 text-xs italic text-amber-700" data-testid="ricordi-vuoto">Hai scoperto qualcosa di lui? Scrivilo qui: ti servirà la prossima volta che passa.</p>
        : (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {data.ricordi.map((r) => (
              <span key={r.id} className="group inline-flex items-center gap-1 rounded-md border border-amber-200 bg-white px-2 py-1 text-sm text-slate-800 shadow-sm" title={`${r.da} · ${fmtData(r.at.slice(0, 10))}`} data-testid={`ricordo-${r.id}`}>
                {r.testo}
                <button type="button" className="ml-0.5 text-slate-300 hover:text-rose-600" onClick={() => del(r.id)} data-testid={`ricordo-del-${r.id}`}><X className="h-3 w-3" /></button>
              </span>
            ))}
          </div>
        )}
      <div className="mt-2 flex gap-1.5">
        <Input value={testo} onChange={(e) => setTesto(e.target.value)} placeholder='es. "il figlio fa calcio", "appassionato di cani"' className="h-8 bg-white text-sm"
               onKeyDown={(e) => e.key === "Enter" && add()} data-testid="ricordi-input" />
        <Button size="sm" className="h-8" onClick={add} disabled={!testo.trim()} data-testid="ricordi-add">Aggiungi</Button>
      </div>
    </div>
  );
};

export const useRicordiPreview = (ids) => {
  const [map, setMap] = useState({});
  const [tick, setTick] = useState(0);
  const key = (ids || []).filter(Boolean).slice(0, 300).join(",");
  useEffect(() => {
    const h = () => setTick((t) => t + 1);
    window.addEventListener("ricordi-changed", h);
    return () => window.removeEventListener("ricordi-changed", h);
  }, []);
  useEffect(() => {
    if (!key) { setMap({}); return; }
    api.get("/ricordi/preview", { params: { ids: key } }).then((r) => setMap(r.data)).catch(() => {});
  }, [key, tick]);
  return map;
};

export const RicordiLine = ({ testi }) => {
  if (!testi?.length) return null;
  return (
    <p className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-amber-800" data-testid="ricordi-line">
      <Heart className="h-3 w-3 shrink-0 fill-amber-300 text-amber-500" /> {testi.slice(0, 3).join(" · ")}
    </p>
  );
};
