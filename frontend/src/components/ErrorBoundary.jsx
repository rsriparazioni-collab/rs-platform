import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    const msg = String(error?.message || error);
    if (/ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module/i.test(msg)
        && !sessionStorage.getItem("chunk_reloaded")) {
      sessionStorage.setItem("chunk_reloaded", "1");
      window.location.reload();
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 p-6 text-center" data-testid="error-boundary">
        <h1 className="font-heading text-2xl font-bold text-slate-900">Si è verificato un errore</h1>
        <p className="max-w-md text-sm text-slate-500">{String(this.state.error?.message || this.state.error)}</p>
        <button onClick={() => { sessionStorage.removeItem("chunk_reloaded"); window.location.reload(); }}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
                data-testid="error-boundary-reload">
          Ricarica la pagina
        </button>
      </div>
    );
  }
}
