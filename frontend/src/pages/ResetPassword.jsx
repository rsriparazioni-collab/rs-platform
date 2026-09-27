import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { KeyRound, Loader2, ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { apiError } from "../lib/api";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const richiedi = async (e) => {
    e.preventDefault(); setLoading(true); setError(""); setMsg("");
    try { const r = await axios.post(`${API}/auth/forgot-password`, { email }); setMsg(r.data.message); }
    catch (err) { setError(apiError(err)); } finally { setLoading(false); }
  };
  const reimposta = async (e) => {
    e.preventDefault(); setError("");
    if (pw !== pw2) { setError("Le due password non coincidono"); return; }
    setLoading(true);
    try { const r = await axios.post(`${API}/auth/reset-password`, { token, password: pw }); setMsg(r.data.message); setTimeout(() => navigate("/login"), 2500); }
    catch (err) { setError(apiError(err)); } finally { setLoading(false); }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4" data-testid="reset-password-page">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-3"><KeyRound className="h-6 w-6 text-fuchsia-600" /><h2 className="font-heading text-2xl font-bold text-slate-900">{token ? "Nuova password" : "Password dimenticata"}</h2></div>
        {msg ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800" data-testid="reset-msg">{msg}</p> : (
          <form onSubmit={token ? reimposta : richiedi} className="space-y-4">
            {!token ? (
              <div className="space-y-1.5"><Label>Email dell'account</Label><Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nome@esempio.it" data-testid="forgot-email" /></div>
            ) : (
              <>
                <div className="space-y-1.5"><Label>Nuova password (min. 8 caratteri)</Label><Input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} data-testid="reset-password" /></div>
                <div className="space-y-1.5"><Label>Ripeti password</Label><Input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} data-testid="reset-password2" /></div>
              </>
            )}
            {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid="reset-error">{error}</div>}
            <Button type="submit" disabled={loading} className="h-11 w-full bg-gradient-to-r from-fuchsia-600 to-blue-700 text-white hover:opacity-90" data-testid="reset-submit">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : token ? "Salva nuova password" : "Inviami il link"}
            </Button>
          </form>
        )}
        <Link to="/login" className="mt-5 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800" data-testid="reset-back-login"><ArrowLeft className="h-4 w-4" /> Torna al login</Link>
      </div>
    </div>
  );
}
