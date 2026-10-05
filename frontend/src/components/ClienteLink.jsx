import { useNavigate } from "react-router-dom";
import { UserRound } from "lucide-react";

export const ClienteLink = ({ clientId, children, className = "", testid }) => {
  const navigate = useNavigate();
  if (!clientId) return <span className={className}>{children || "-"}</span>;
  return (
    <button type="button" title="Apri la scheda cliente completa (Aggiungi al cliente, utenze, documenti)"
            onClick={(e) => { e.stopPropagation(); navigate(`/clienti?apri=${clientId}`); }}
            className={`inline-flex items-center gap-1 text-left font-medium text-slate-900 underline-offset-2 hover:text-sky-700 hover:underline ${className}`}
            data-testid={testid || `cliente-link-${clientId}`}>
      <UserRound className="h-3.5 w-3.5 text-slate-400" /> {children || "-"}
    </button>
  );
};
