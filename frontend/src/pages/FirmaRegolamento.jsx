import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { CheckCircle2, Eraser, PenLine } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function FirmaRegolamento() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const [letto, setLetto] = useState(false);
  const [saving, setSaving] = useState(false);
  const canvasRef = useRef();
  const drawing = useRef(false);
  const hasInk = useRef(false);

  useEffect(() => { axios.get(`${API}/incentivi/public/firma-regolamento/${token}`).then((r) => { setInfo(r.data); if (r.data.stato === "firmata") setDone(true); }).catch((e) => setErr(e.response?.data?.detail || "Link non valido")); }, [token]);

  const pos = (e) => { const c = canvasRef.current; const r = c.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return { x: (p.clientX - r.left) * (c.width / r.width), y: (p.clientY - r.top) * (c.height / r.height) }; };
  const start = (e) => { e.preventDefault(); drawing.current = true; const ctx = canvasRef.current.getContext("2d"); const { x, y } = pos(e); ctx.beginPath(); ctx.moveTo(x, y); };
  const move = (e) => { if (!drawing.current) return; e.preventDefault(); const ctx = canvasRef.current.getContext("2d"); ctx.lineWidth = 3; ctx.lineCap = "round"; ctx.strokeStyle = "#0f172a"; const { x, y } = pos(e); ctx.lineTo(x, y); ctx.stroke(); hasInk.current = true; };
  const end = () => { drawing.current = false; };
  const clear = () => { const c = canvasRef.current; c.getContext("2d").clearRect(0, 0, c.width, c.height); hasInk.current = false; };
  const invia = async () => {
    if (!hasInk.current) return setErr("Firma prima nel riquadro");
    setSaving(true); setErr("");
    try { await axios.post(`${API}/incentivi/public/firma-regolamento/${token}`, { firma_png: canvasRef.current.toDataURL("image/png") }); setDone(true); }
    catch (e) { setErr(e.response?.data?.detail || "Invio non riuscito"); } finally { setSaving(false); }
  };

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-8" data-testid="firma-regolamento-page">
      <div className="mx-auto max-w-lg space-y-4 rounded-2xl bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2"><PenLine className="h-5 w-5 text-emerald-600" /><h1 className="text-lg font-semibold text-slate-900">Regolamento Incentivi RS</h1></div>
        {err && !info && <p className="text-sm text-rose-600" data-testid="firma-errore">{err}</p>}
        {info && <p className="text-sm text-slate-700">Ciao <b>{info.nome}</b>, leggi il regolamento e firma col dito per presa visione e accettazione.</p>}
        {info && <div className="max-h-80 space-y-3 overflow-auto rounded-lg bg-slate-50 p-3 text-sm text-slate-700" data-testid="firma-regole" onScroll={(e) => { const t = e.target; if (t.scrollTop + t.clientHeight >= t.scrollHeight - 10) setLetto(true); }}>
          {info.regole.map((s) => <div key={s.titolo}><p className="font-semibold">{s.titolo}</p><ul className="ml-4 list-disc text-xs">{s.righe.map((r, i) => <li key={i}>{r}</li>)}</ul></div>)}
        </div>}
        {done ? (
          <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 text-emerald-800" data-testid="firma-ok"><CheckCircle2 className="h-5 w-5" /> Firma acquisita, grazie! Puoi chiudere questa pagina.</div>
        ) : info && (
          <>
            {!info.versione_attuale && <p className="text-sm text-rose-600">Le regole sono cambiate dopo l'invio: chiedi un nuovo link.</p>}
            <label className="flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={letto} onChange={(e) => setLetto(e.target.checked)} data-testid="firma-letto" /> Ho letto e accetto il regolamento</label>
            <canvas ref={canvasRef} width={600} height={240} className="w-full touch-none rounded-lg border-2 border-dashed border-slate-300 bg-white" data-testid="firma-canvas"
              onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end} onTouchStart={start} onTouchMove={move} onTouchEnd={end} />
            {err && <p className="text-sm text-rose-600" data-testid="firma-errore">{err}</p>}
            <div className="flex gap-2">
              <button onClick={clear} className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid="firma-cancella"><Eraser className="h-4 w-4" /> Cancella</button>
              <button onClick={invia} disabled={saving || !letto || !info.versione_attuale} className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50" data-testid="firma-invia">{saving ? "Invio…" : "Conferma firma"}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
