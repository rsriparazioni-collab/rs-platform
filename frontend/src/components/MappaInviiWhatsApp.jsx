import { useEffect, useState } from "react";
import { Map } from "lucide-react";
import api from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";

export default function MappaInviiWhatsApp() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [negozio, setNegozio] = useState(null);
  const [aperta, setAperta] = useState(null);
  useEffect(() => { if (open && !data) api.get("/whatsapp/mappa-invii").then((r) => { setData(r.data); setNegozio(r.data.negozi[0]?.store_id || null); }).catch(() => {}); }, [open, data]);
  const n = data?.negozi.find((x) => x.store_id === negozio);

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)} className="gap-1.5 text-slate-600" data-testid="mappa-invii-button"><Map className="h-4 w-4" /> Chi invia cosa</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl" data-testid="mappa-invii-dialog">
          <DialogHeader><DialogTitle className="font-heading">Mappa invii WhatsApp – da quale numero parte ogni messaggio</DialogTitle></DialogHeader>
          {data && (
            <div className="flex flex-wrap gap-1.5">
              {data.negozi.map((x) => (
                <button key={x.store_id} type="button" onClick={() => setNegozio(x.store_id)} className={`rounded-full border px-3 py-1 text-sm ${negozio === x.store_id ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`} data-testid={`mappa-negozio-${x.store_id}`}>
                  {x.negozio}{x.problemi.length > 0 && <span className="ml-1 text-rose-400">●</span>}
                </button>
              ))}
            </div>
          )}
          {n && (
            <div className="space-y-2">
              {(!n.review_link || !n.telefono_avvisi) && (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800" data-testid="mappa-avvisi">
                  {!n.review_link && "Link recensione mancante in Gestione Negozi: le recensioni riparazioni/telefonia non partono. "}
                  {!n.telefono_avvisi && "Telefono avvisi mancante: gli avvisi al negozio usano il numero WhatsApp collegato."}
                </p>
              )}
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-2 py-1.5">Messaggio</th><th className="px-2 py-1.5">Parte da</th><th className="px-2 py-1.5">Verso</th><th className="px-2 py-1.5"></th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {n.righe.map((r) => (
                    <tr key={r.flusso} className="align-top">
                      <td className="px-2 py-1.5 font-medium text-slate-800">{r.flusso}</td>
                      <td className="px-2 py-1.5">
                        <span className={`inline-block h-2 w-2 rounded-full ${r.da.connessa === true ? "bg-emerald-500" : r.da.connessa === false ? "bg-rose-500" : "bg-slate-300"}`} /> {r.da.nome}
                        <p className="text-xs text-slate-500">{r.da.numero ? `+${r.da.numero}` : "non collegato"}</p>
                      </td>
                      <td className="px-2 py-1.5 text-slate-600">{r.a}</td>
                      <td className="px-2 py-1.5"><button type="button" className="text-xs text-indigo-700 hover:underline" onClick={() => setAperta(aperta === r.flusso ? null : r.flusso)}>{aperta === r.flusso ? "Nascondi" : "Testo"}</button>
                        {aperta === r.flusso && <pre className="mt-1 max-w-md whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-700">{r.testo}</pre>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
