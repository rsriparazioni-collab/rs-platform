import { useMemo, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, Users, Building2, UserCog, ShieldCheck, LogOut, Zap, Menu, MessageCircle, Wrench, Smartphone } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { RUOLI } from "../lib/constants";
import { Sheet, SheetContent, SheetTrigger } from "./ui/sheet";
import { Button } from "./ui/button";

const ALL_SECTIONS_DEFAULT = ["energia", "riparazioni", "telefonia"];

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "operatore", "negozio", "tecnico"], testid: "nav-dashboard" },
  { to: "/clienti", label: "Clienti", icon: Users, roles: ["admin", "operatore", "negozio", "tecnico"], section: "energia", testid: "nav-clienti" },
  { to: "/riparazioni", label: "Riparazioni", icon: Wrench, roles: ["admin", "operatore", "negozio", "tecnico"], section: "riparazioni", testid: "nav-riparazioni" },
  { to: "/telefonia", label: "Telefonia", icon: Smartphone, roles: ["admin", "operatore", "negozio", "tecnico"], section: "telefonia", testid: "nav-telefonia" },
  { to: "/negozi", label: "Negozi", icon: Building2, roles: ["admin", "operatore"], testid: "nav-negozi" },
  { to: "/operatori", label: "Operatori", icon: UserCog, roles: ["admin", "operatore"], testid: "nav-operatori" },
  { to: "/whatsapp", label: "WhatsApp", icon: MessageCircle, roles: ["admin"], testid: "nav-whatsapp" },
  { to: "/utenti", label: "Utenti", icon: ShieldCheck, roles: ["admin", "operatore", "negozio", "tecnico"], testid: "nav-utenti" },
];

function NavItems({ onNavigate, mobile }) {
  const { user } = useAuth();
  const suffix = mobile ? "-mobile" : "";
  const sections = user.sections || ALL_SECTIONS_DEFAULT;
  const items = useMemo(
    () => NAV.filter((n) => n.roles.includes(user.role) && (!n.section || sections.includes(n.section))),
    [user.role, sections]
  );
  return (
    <nav className="flex-1 space-y-1 px-3 py-4">
      {items.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === "/"}
          onClick={onNavigate}
          data-testid={`${n.testid}${suffix}`}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
              isActive ? "bg-sky-600/10 text-sky-700" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            }`
          }
        >
          <n.icon className="h-4 w-4" />
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

function SidebarContent({ onNavigate, mobile }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const suffix = mobile ? "-mobile" : "";
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 border-b border-slate-200 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900">
          <Zap className="h-5 w-5 text-amber-400" />
        </div>
        <div>
          <p className="font-heading text-sm font-bold leading-tight text-slate-900">Gestionale Utenze</p>
          <p className="text-xs text-slate-500">Luce & Gas</p>
        </div>
      </div>
      <NavItems onNavigate={onNavigate} mobile={mobile} />
      <div className="border-t border-slate-200 p-4">
        <div className="mb-3 rounded-lg bg-slate-50 p-3">
          <p className="text-sm font-semibold text-slate-900" data-testid={`sidebar-user-name${suffix}`}>{user.name}</p>
          <p className="text-xs text-slate-500" data-testid={`sidebar-user-role${suffix}`}>{RUOLI[user.role] || user.role}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          data-testid={`logout-button${suffix}`}
          className="w-full justify-start gap-2 text-slate-500 hover:text-rose-600"
          onClick={() => { logout(); navigate("/login"); }}
        >
          <LogOut className="h-4 w-4" /> Esci
        </Button>
      </div>
    </div>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-slate-50" data-testid="app-layout">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white lg:block">
        <SidebarContent />
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur-md lg:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" data-testid="mobile-menu-button"><Menu className="h-5 w-5" /></Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SidebarContent mobile onNavigate={() => setOpen(false)} />
            </SheetContent>
          </Sheet>
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-amber-500" />
            <span className="font-heading text-sm font-bold">Gestionale Utenze</span>
          </div>
        </header>
        <main className="p-6 sm:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
