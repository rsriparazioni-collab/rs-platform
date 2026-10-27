import { useCallback, useEffect, useState } from "react";
import { ClipboardList, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import ClientDetail from "../components/ClientDetail";
import { RiepilogoNegozi } from "../components/lavorazioni/RiepilogoNegozi";
import { ColonnaPratiche } from "../components/lavorazioni/ColonnaPratiche";
import { AgendaGiorno, AgendaNuovo } from "../components/lavorazioni/AgendaGiorno";
import { AddettiDialog } from "../components/lavorazioni/AddettiDialog";

export default function RiepilogoLavorazioni() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [storeId, setStoreId] = useState("");
  const [detail, setDetail] = useState(null);
  const [agendaFor, setAgendaFor] = useState(null);
  const [denied, setDenied] = useState(false);

  const load = useCallback(() => {
    api.get("/lavorazioni/riepilogo", { params: { store_id: storeId } })
      .then((r) => { setData(r.data); setDenied(false); })
      .catch((e) => { if (e?.response?.status === 403) setDenied(true); else toast.error(apiError(e)); });
  }, [storeId]);
  useEffect(() => { load(); }, [load]);

  if (denied) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-sm text-amber-800" data-testid="lavorazioni-denied">
        <ShieldAlert className="mb-2 h-5 w-5" /> Sezione riservata agli addetti lavorazioni. Chiedi all'amministratore di abilitarti dal tasto "Addetti".
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="lavorazioni-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2"><ClipboardList className="h-7 w-7 text-sky-600" /> Riepilogo Lavorazioni</h1>
          <p className="mt-1 text-sm text-slate-500">Pratiche energia (ENEL + CambiaOra) di tutti i negozi: da lavorare, lavorate, da reinserire. Nessuna pratica si perde.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load} data-testid="lavorazioni-refresh"><RefreshCw className="h-4 w-4" /></Button>
          {user.role === "admin" && <AddettiDialog />}
        </div>
      </div>

      {data && (
        <>
          <RiepilogoNegozi negozi={data.negozi} totali={data.totali} storeId={storeId} onSelect={setStoreId} />
          <AgendaGiorno scadute={data.agenda_scadute} oggi={data.oggi} onChanged={load} />
          <div className="grid gap-4 lg:grid-cols-3">
            <ColonnaPratiche titolo="Da lavorare" colore="sky" righe={data.da_lavorare} testid="col-da-lavorare"
                             onOpen={setDetail} onChanged={load} onAgenda={setAgendaFor} />
            <ColonnaPratiche titolo="Lavorate (ultimi 60 gg)" colore="emerald" righe={data.lavorate} testid="col-lavorate"
                             onOpen={setDetail} onChanged={load} onAgenda={setAgendaFor} lavorate />
            <ColonnaPratiche titolo="Da reinserire" colore="rose" righe={data.da_reinserire} testid="col-da-reinserire"
                             onOpen={setDetail} onChanged={load} onAgenda={setAgendaFor} reinserire />
          </div>
        </>
      )}

      <ClientDetail client={detail} onClose={() => setDetail(null)} onChanged={load} isAdmin={user.role === "admin"} />
      {agendaFor && <AgendaNuovo riga={agendaFor} onClose={() => setAgendaFor(null)} onSaved={() => { setAgendaFor(null); load(); }} />}
    </div>
  );
}
