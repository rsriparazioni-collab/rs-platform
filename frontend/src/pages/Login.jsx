import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { apiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(apiError(err, "Accesso fallito"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen" data-testid="login-page">
      <div className="hidden w-1/2 flex-col justify-between bg-gradient-to-br from-fuchsia-700 via-violet-700 to-blue-800 p-12 lg:flex">
        <img src="/cambiaora-logo.jpg" alt="CambiaOra - Risparmia su energia e servizi"
             className="w-72 rounded-2xl bg-white p-4 shadow-2xl" data-testid="login-logo" />
        <div>
          <h1 className="font-heading text-4xl font-bold leading-tight text-white lg:text-5xl">
            Rinnovi luce & gas,<br />sotto controllo.
          </h1>
          <p className="mt-4 max-w-md text-base text-fuchsia-100">
            Il gestionale CambiaOra: clienti, contratti, rinnovi a 10 mesi e compensi dei negozi da un'unica postazione di comando.
          </p>
        </div>
        <p className="text-xs text-fuchsia-200">Accesso riservato al team autorizzato</p>
      </div>
      <div className="flex flex-1 items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden flex justify-center">
            <img src="/cambiaora-logo.jpg" alt="CambiaOra" className="w-56 rounded-xl bg-white p-3 shadow-lg" data-testid="login-logo-mobile" />
          </div>
          <h2 className="font-heading text-2xl font-bold text-slate-900">Accedi</h2>
          <p className="mt-1 text-sm text-slate-500">Inserisci le tue credenziali per continuare</p>
          <form onSubmit={submit} className="mt-8 space-y-5" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} data-testid="login-email-input"
                     onChange={(e) => setEmail(e.target.value)} placeholder="nome@esempio.it" className="h-11" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" required value={password} data-testid="login-password-input"
                     onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="h-11" />
            </div>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid="login-error">
                {error}
              </div>
            )}
            <Button type="submit" disabled={loading} data-testid="login-submit-button"
                    className="h-11 w-full bg-gradient-to-r from-fuchsia-600 to-blue-700 text-white hover:opacity-90">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Accedi"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
