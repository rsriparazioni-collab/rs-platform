import { useEffect, useState } from "react";
import axios from "axios";
import SlideViewer from "../components/SlideViewer";

const API = process.env.REACT_APP_BACKEND_URL;

export default function Presentazione() {
  const [slides, setSlides] = useState(null);
  useEffect(() => { axios.get(`${API}/api/public/formazione/presentazione`).then((r) => setSlides(r.data)).catch(() => setSlides([])); }, []);
  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 sm:px-8" data-testid="presentazione-page">
      <div className="mx-auto mb-6 flex max-w-5xl items-center justify-between">
        <img src="/rs-logo.png" alt="RS Group" className="h-10 w-auto" />
        <a href="/login" className="text-xs text-slate-400 hover:text-white" data-testid="presentazione-login-link">Accedi al gestionale →</a>
      </div>
      {slides === null ? <p className="text-center text-slate-400">Caricamento...</p> : <SlideViewer slides={slides} pdfUrl={`${API}/api/public/formazione/presentazione.pdf`} />}
    </div>
  );
}
