import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "./components/ui/sonner";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Clienti from "./pages/Clienti";
import Negozi from "./pages/Negozi";
import Operatori from "./pages/Operatori";
import Utenti from "./pages/Utenti";
import WhatsApp from "./pages/WhatsApp";
import Riparazioni from "./pages/Riparazioni";
import Telefonia from "./pages/Telefonia";
import Magazzino from "./pages/Magazzino";
import Ritiri from "./pages/Ritiri";
import ErrorBoundary from "./components/ErrorBoundary";

function Protected({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50" data-testid="loading-screen">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-600 border-t-transparent" />
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

function RequireRole({ roles, section, children }) {
  const { user } = useAuth();
  if (!roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  const sections = user.sections || ["energia", "riparazioni", "telefonia"];
  if (section && !sections.includes(section)) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function App() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Layout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="clienti" element={<RequireRole roles={["admin", "operatore", "negozio", "tecnico"]} section="energia"><Clienti /></RequireRole>} />
            <Route path="riparazioni" element={<RequireRole roles={["admin", "operatore", "negozio", "tecnico"]} section="riparazioni"><Riparazioni /></RequireRole>} />
            <Route path="telefonia" element={<RequireRole roles={["admin", "operatore", "negozio", "tecnico"]} section="telefonia"><Telefonia /></RequireRole>} />
            <Route path="magazzino" element={<RequireRole roles={["admin", "operatore", "negozio", "tecnico"]}><Magazzino /></RequireRole>} />
            <Route path="ritiri" element={<RequireRole roles={["admin", "operatore", "negozio", "tecnico"]} section="riparazioni"><Ritiri /></RequireRole>} />
            <Route path="negozi" element={<RequireRole roles={["admin", "operatore"]}><Negozi /></RequireRole>} />
            <Route path="operatori" element={<RequireRole roles={["admin", "operatore"]}><Operatori /></RequireRole>} />
            <Route path="whatsapp" element={<RequireRole roles={["admin"]}><WhatsApp /></RequireRole>} />
            <Route path="utenti" element={<Utenti />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
