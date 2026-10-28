import { useCallback, useEffect, useState } from "react";
import { MessageSquareWarning, ClipboardPaste, Settings2, Check, Send, Link2, UserSearch, Paperclip, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { Input } from "../ui/input";
import { Badge } from "../ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { SwitchoConfigDialog } from "./SwitchoConfigDialog";

const CAT_CLS = {
  annullata_ip: "bg-rose-100 text-rose-800 border-rose-300", annullata_firma: "bg-rose-50 text-rose-700 border-rose-200",
  conferma_link: "bg-sky-100 text-sky-800 border-sky-300", documenti: "bg-amber-100 text-amber-900 border-amber-300",
  verifica: "bg-violet-100 text-violet-800 border-violet-300", altro: "bg-slate-100 text-slate-700 border-slate-300",
};
const CATEGORIE = ["annullata_ip", "annullata_firma", "conferma_link", "documenti", "verifica", "altro"];
const LABEL = { annullata_ip: "Annullata (IP mandato)", annullata_firma: "Annullata (mancata firma)", conferma_link: "Conferma link/plico", documenti: "Servono documenti", verifica: "Domanda", altro: "Altro" };
const fmt = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${iso.slice(11, 16)}` : "");

const AbbinaDialog = ({ seg, onClose, onDone }) => {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (q.trim().length < 2) return;
    const t = setTimeout(() => api.get("/clients", { params: { q } }).then((r) => setRes((Array.isArray(r.data) ? r.data : r.data.items || []).slice(0, 20))).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [q]);
  const pick = async (c) => {
    try { await api.post(`/switcho/segnalazioni/${seg.id}/abbina`, { client_id: c.id }); toast.success("Pratica abbinata e aggiornata"); onDone(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="switcho-abbina-dialog">
        <DialogHeader><DialogTitle>Abbina a una pratica</DialogTitle></DialogHeader>
        <p className="text-xs text-slate-500 line-clamp-3">{seg.testo}</p>
        <Input autoFocus placeholder="Cerca cliente per cognome…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="switcho-abbina-search" />
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {res.map((c) => (
            <button key={c.id} className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:bg-sky-50" onClick={() => pick(c)} data-testid={`switcho-abbina-${c.id}`}>
              <span><b>{c.cognome} {c.nome}</b> <span className="text-xs text-slate-500">{c.telefono}</span></span>
              <span className="text-xs text-slate-500">{c.lavorazione}</span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

const RispondiDialog = ({ seg, onClose, onDone }) => {
  const [testo, setTesto] = useState("");
  const [sel, setSel] = useState((seg.documenti_disponibili || []).map((d) => d.id));
  const send = async () => {
    try { const r = await api.post(`/switcho/segnalazioni/${seg.id}/rispondi`, { testo, attachment_ids: sel }); toast.success(`Inviato nel gruppo Switcho (${r.data.allegati} allegati)`); onDone(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="switcho-rispondi-dialog">
        <DialogHeader><DialogTitle>Rispondi a Switcho (dal numero di Sondrio)</DialogTitle></DialogHeader>
        <Textarea rows={3} value={testo} onChange={(e) => setTesto(e.target.value)} placeholder={`Es. Buongiorno, in allegato la bolletta di ${seg.client_name || "…"}`} data-testid="switcho-rispondi-testo" />
        {(seg.documenti_disponibili || []).length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-semibold text-slate-500">Documenti del cliente da allegare</p>
            {seg.documenti_disponibili.map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sel.includes(d.id)} onChange={(e) => setSel((s) => (e.target.checked ? [...s, d.id] : s.filter((x) => x !== d.id)))} /> <Paperclip className="h-3 w-3" /> {d.original_filename} <span className="text-xs text-slate-400">{d.tipo}</span></label>
            ))}
          </div>
        )}
        <Button onClick={send} disabled={!testo.trim() && !sel.length} data-testid="switcho-rispondi-send"><Send className="mr-1 h-4 w-4" /> Invia nel gruppo</Button>
      </DialogContent>
    </Dialog>
  );
};

const Segnalazione = ({ s, onChanged, onOpen }) => {
  const [dlg, setDlg] = useState(null);
  const act = async (path, ok) => { try { await api.post(`/switcho/segnalazioni/${s.id}/${path}`); toast.success(ok); onChanged(); } catch (e) { toast.error(apiError(e)); } };
  const cat = async (c) => { try { await api.post(`/switcho/segnalazioni/${s.id}/categoria`, { categoria: c }); onChanged(); } catch (e) { toast.error(apiError(e)); } };
  const docs = s.documenti_disponibili || [];
  return (
    <div className={`rounded-lg border bg-white p-2.5 text-sm shadow-sm ${!s.client_id ? "border-amber-400" : "border-slate-200"}`} data-testid={`switcho-seg-${s.id}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <select value={s.categoria} onChange={(e) => cat(e.target.value)} className={`rounded border px-1.5 py-0.5 text-[11px] font-semibold ${CAT_CLS[s.categoria]}`} data-testid={`switcho-cat-${s.id}`}>
          {CATEGORIE.map((c) => <option key={c} value={c}>{LABEL[c]}</option>)}
        </select>
        {s.fornitore && <Badge variant="outline" className="text-[10px]">{s.fornitore}</Badge>}
        {s.ai && <span title={`AI ${Math.round((s.confidenza || 0) * 100)}%`} className="text-[10px] text-slate-400 flex items-center gap-0.5"><Sparkles className="h-3 w-3" />{Math.round((s.confidenza || 0) * 100)}%</span>}
        <span className="ml-auto text-[11px] text-slate-400">{fmt(s.at)} · {s.origine === "incolla" ? "incollato" : "gruppo"}</span>
      </div>
      <p className="mt-1 text-slate-700">{s.testo}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
        {s.client_id ? (
          <button className="font-semibold text-sky-700 hover:underline" onClick={() => onOpen({ id: s.client_id })} data-testid={`switcho-client-${s.id}`}>{s.client_name} <span className="font-normal text-slate-500">· {s.negozio} · {s.lavorazione}</span></button>
        ) : <span className="font-semibold text-amber-700">Cliente non riconosciuto</span>}
        {(s.azioni || []).map((a, i) => <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{a}</span>)}
        {s.categoria === "documenti" && s.client_id && (docs.length
          ? <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-800">{docs.length} documenti a sistema</span>
          : <span className="rounded bg-rose-100 px-1.5 py-0.5 font-semibold text-rose-800" data-testid={`switcho-alert-doc-${s.id}`}>⚠ Mandare documenti a Switcho: nessun allegato sul cliente</span>)}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {!s.client_id && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setDlg("abbina")} data-testid={`switcho-abbina-btn-${s.id}`}><UserSearch className="mr-1 h-3 w-3" /> Abbina pratica</Button>}
        {s.client_id && s.categoria === "conferma_link" && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => act("avvisa-cliente", "Avviso inviato al cliente dal suo negozio")} data-testid={`switcho-avvisa-${s.id}`}><Link2 className="mr-1 h-3 w-3" /> {s.avviso_cliente?.ok ? "Rimanda avviso al cliente" : "Avvisa cliente"}</Button>}
        {s.client_id && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setDlg("rispondi")} data-testid={`switcho-rispondi-btn-${s.id}`}><Send className="mr-1 h-3 w-3" /> {s.categoria === "documenti" && docs.length ? "Invia documenti a Switcho" : "Rispondi a Switcho"}</Button>}
        <Button size="sm" variant="ghost" className="h-7 text-xs text-emerald-700" onClick={() => act("chiudi", "Segnalazione chiusa")} data-testid={`switcho-chiudi-${s.id}`}><Check className="mr-1 h-3 w-3" /> Fatto</Button>
      </div>
      {dlg === "abbina" && <AbbinaDialog seg={s} onClose={() => setDlg(null)} onDone={() => { setDlg(null); onChanged(); }} />}
      {dlg === "rispondi" && <RispondiDialog seg={s} onClose={() => setDlg(null)} onDone={() => { setDlg(null); onChanged(); }} />}
    </div>
  );
};

export const SwitchoBox = ({ onOpen, onChanged }) => {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [incolla, setIncolla] = useState(false);
  const [testo, setTesto] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get("/switcho/segnalazioni").then((r) => setItems(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const changed = () => { load(); onChanged?.(); };
  const invia = async () => {
    setBusy(true);
    try { const r = await api.post("/switcho/incolla", { testo }); toast.success(`${r.data.messaggi} messaggi letti, ${r.data.segnalazioni.length} segnalazioni`); setTesto(""); setIncolla(false); changed(); } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <section className="rounded-xl border border-orange-200 bg-orange-50/60 p-3" data-testid="switcho-box">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-slate-800"><MessageSquareWarning className="h-4 w-4 text-orange-600" /> Da Switcho (gruppo CambiaOra) <span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-600" data-testid="switcho-count">{items.length}</span></h2>
        <div className="flex gap-1.5">
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setIncolla((v) => !v)} data-testid="switcho-incolla-btn"><ClipboardPaste className="mr-1 h-3 w-3" /> Incolla messaggi</Button>
          {user.role === "admin" && <SwitchoConfigDialog trigger={<Button size="sm" variant="ghost" className="h-7 text-xs" data-testid="switcho-config-btn"><Settings2 className="h-3.5 w-3.5" /></Button>} />}
        </div>
      </div>
      {incolla && (
        <div className="mb-2 space-y-1.5">
          <Textarea rows={4} value={testo} onChange={(e) => setTesto(e.target.value)} className="bg-white text-sm" placeholder={"Incolla qui i messaggi copiati dal gruppo Switcho (anche più messaggi, con o senza [ora, data] +39…)"} data-testid="switcho-incolla-testo" />
          <Button size="sm" className="h-7 text-xs" onClick={invia} disabled={busy || !testo.trim()} data-testid="switcho-incolla-send">Leggi e abbina</Button>
        </div>
      )}
      {items.length === 0 ? <p className="text-xs text-slate-400">Nessuna segnalazione aperta da Switcho.</p> : (
        <div className="grid gap-2 lg:grid-cols-2">{items.map((s) => <Segnalazione key={s.id} s={s} onChanged={changed} onOpen={onOpen} />)}</div>
      )}
    </section>
  );
};
