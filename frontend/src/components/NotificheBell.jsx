import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check, CheckCheck, Package } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDateTime } from "../lib/constants";
import { Button } from "./ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

export default function NotificheBell() {
  const [data, setData] = useState({ non_lette: 0, items: [] });
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(() => api.get("/notifiche").then((r) => setData(r.data)).catch(() => {}), []);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const leggi = async (n) => {
    try { await api.post(`/notifiche/${n.id}/letta`); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const leggiTutte = async () => {
    try { await api.post("/notifiche/leggi-tutte"); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const apri = (n) => {
    if (!n.letta) leggi(n);
    setOpen(false);
    if (n.servizio_id) navigate(`/riparazioni?apri=${n.servizio_id}`);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" className="relative flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-100" data-testid="notifiche-bell" aria-label="Avvisi">
          <Bell className="h-4 w-4" />
          {data.non_lette > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white" data-testid="notifiche-badge">{data.non_lette > 99 ? "99+" : data.non_lette}</span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0" data-testid="notifiche-popover">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
          <p className="text-sm font-semibold text-slate-900">Avvisi {data.non_lette > 0 && <span className="text-rose-600">({data.non_lette} nuovi)</span>}</p>
          {data.non_lette > 0 && <Button size="sm" variant="ghost" className="h-7 gap-1 text-xs" onClick={leggiTutte} data-testid="notifiche-leggi-tutte"><CheckCheck className="h-3.5 w-3.5" /> Segna tutti letti</Button>}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {data.items.length === 0 && <p className="px-4 py-8 text-center text-sm text-slate-500" data-testid="notifiche-vuoto">Nessun avviso</p>}
          {data.items.map((n, i) => (
            <div key={n.id} className={`flex gap-3 border-b border-slate-100 px-4 py-3 text-sm ${n.letta ? "bg-white" : "bg-amber-50/70"}`} data-testid={`notifica-${i}`}>
              <Package className={`mt-0.5 h-4 w-4 shrink-0 ${n.letta ? "text-slate-400" : "text-amber-600"}`} />
              <button type="button" className="flex-1 text-left" onClick={() => apri(n)} data-testid={`notifica-apri-${i}`}>
                <p className={`text-xs ${n.letta ? "text-slate-500" : "font-semibold text-slate-800"}`}>{n.titolo || "Avviso"} · <span className="font-normal text-slate-500">{n.store_name}</span></p>
                <p className="mt-0.5 text-[13px] leading-snug text-slate-700">{n.testo}</p>
                <p className="mt-1 text-[11px] text-slate-400">{fmtDateTime(n.at)}{n.letta && n.letta_da ? ` · letto da ${n.letta_da}` : ""}</p>
              </button>
              {!n.letta && (
                <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" title="Segna come letto" onClick={() => leggi(n)} data-testid={`notifica-letta-${i}`}>
                  <Check className="h-4 w-4 text-emerald-600" />
                </Button>
              )}
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
