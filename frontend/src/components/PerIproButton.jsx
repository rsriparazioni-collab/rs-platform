import { useState } from "react";
import { Handshake } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export const PerIproButton = ({ tipo, id, value, onChange }) => {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!(user.role === "admin" || user.can_assign_ipro)) {
    return value ? <span className="status-badge bg-orange-500/15 text-orange-700 border-orange-300" data-testid="per-ipro-badge">Per Ipro</span> : null;
  }
  const toggle = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/${tipo}/${id}/per-ipro`, { per_ipro: !value });
      onChange?.(r.data.per_ipro);
      toast.success(r.data.per_ipro ? "Compensi assegnati a Ipro" : "Assegnazione a Ipro rimossa");
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <button type="button" onClick={toggle} disabled={busy} data-testid="per-ipro-button"
      className={`status-badge cursor-pointer transition-colors ${value ? "bg-orange-500/15 text-orange-700 border-orange-300 hover:bg-orange-500/25" : "bg-slate-500/10 text-slate-600 border-slate-300 hover:bg-slate-500/20"}`}>
      <Handshake className="h-3 w-3" /> {value ? "Per Ipro ✓" : "Per Ipro"}
    </button>
  );
};
