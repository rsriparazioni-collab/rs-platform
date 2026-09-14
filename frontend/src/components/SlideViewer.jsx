import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Maximize2, Minimize2 } from "lucide-react";
import Markdown from "./Markdown";

export default function SlideViewer({ slides, pdfUrl, embedded = false }) {
  const [i, setI] = useState(0);
  const [full, setFull] = useState(false);
  const n = slides.length;
  const next = useCallback(() => setI((x) => Math.min(n - 1, x + 1)), [n]);
  const prev = useCallback(() => setI((x) => Math.max(0, x - 1)), []);

  useEffect(() => {
    const h = (e) => {
      if (["ArrowRight", " ", "PageDown"].includes(e.key)) { e.preventDefault(); next(); }
      if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); prev(); }
      if (e.key === "Escape") setFull(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [next, prev]);

  if (!n) return <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500" data-testid="slides-empty">Nessuna slide.</div>;
  const s = slides[i];

  return (
    <div className={full ? "fixed inset-0 z-50 flex flex-col bg-slate-950 p-6" : `relative ${embedded ? "" : "mx-auto max-w-5xl"}`} data-testid="slide-viewer">
      <div className={`relative flex flex-1 flex-col overflow-hidden rounded-2xl bg-slate-900 text-white shadow-2xl ${full ? "" : "min-h-[520px]"}`}>
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-emerald-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between px-8 pt-6 text-xs uppercase tracking-[0.2em] text-slate-400">
          <span>RS Group · Cambia Ora</span>
          <span data-testid="slide-counter">{i + 1} / {n}</span>
        </div>
        <div className="relative flex flex-1 flex-col justify-center px-8 py-8 sm:px-14" key={s.id}>
          <h2 className="font-heading text-3xl font-bold leading-tight sm:text-4xl lg:text-5xl" data-testid="slide-title">{s.titolo}</h2>
          {s.sottotitolo && <p className="mt-2 text-base text-emerald-300 sm:text-lg" data-testid="slide-subtitle">{s.sottotitolo}</p>}
          <div className="mt-6 max-w-3xl [&_*]:text-slate-200 [&_strong]:text-white [&_h2]:text-white [&_li]:text-slate-200 [&_p]:text-base [&_li]:text-base" data-testid="slide-content">
            <Markdown>{s.contenuto}</Markdown>
          </div>
        </div>
        <div className="relative flex items-center justify-between border-t border-white/10 px-6 py-3">
          <div className="flex gap-1">
            {slides.map((x, j) => <button key={x.id} onClick={() => setI(j)} className={`h-1.5 rounded-full transition-all ${j === i ? "w-6 bg-emerald-400" : "w-1.5 bg-white/30 hover:bg-white/60"}`} aria-label={`Slide ${j + 1}`} />)}
          </div>
          <div className="flex items-center gap-2">
            {pdfUrl && <a href={pdfUrl} className="rounded-full p-2 text-slate-300 hover:bg-white/10 hover:text-white" title="Scarica PDF" data-testid="slides-pdf"><Download className="h-4 w-4" /></a>}
            <button onClick={() => setFull((f) => !f)} className="rounded-full p-2 text-slate-300 hover:bg-white/10 hover:text-white" title="Schermo intero" data-testid="slides-fullscreen">{full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}</button>
            <button onClick={prev} disabled={i === 0} className="rounded-full bg-white/10 p-2 hover:bg-white/20 disabled:opacity-30" data-testid="slide-prev"><ChevronLeft className="h-5 w-5" /></button>
            <button onClick={next} disabled={i === n - 1} className="rounded-full bg-emerald-500 p-2 text-slate-950 hover:bg-emerald-400 disabled:opacity-30" data-testid="slide-next"><ChevronRight className="h-5 w-5" /></button>
          </div>
        </div>
      </div>
      {!full && <p className="mt-3 text-center text-xs text-slate-400">Usa le frecce ← → o la barra spaziatrice</p>}
    </div>
  );
}
