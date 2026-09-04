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

function RequireRole({ roles, children }) {
  const { user } = useAuth();
  if (!roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Layout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="clienti" element={<Clienti />} />
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
  );
}

export default App;
