import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const components = {
  h1: (p) => <h1 className="mt-4 font-heading text-2xl font-bold text-slate-900" {...p} />,
  h2: (p) => <h2 className="mt-5 font-heading text-lg font-semibold text-slate-900" {...p} />,
  h3: (p) => <h3 className="mt-4 text-base font-semibold text-slate-900" {...p} />,
  p: (p) => <p className="my-2 leading-relaxed text-slate-700" {...p} />,
  ul: (p) => <ul className="my-2 list-disc space-y-1 pl-5 text-slate-700" {...p} />,
  ol: (p) => <ol className="my-2 list-decimal space-y-1 pl-5 text-slate-700" {...p} />,
  strong: (p) => <strong className="font-semibold text-slate-900" {...p} />,
  a: (p) => <a className="text-sky-700 underline" target="_blank" rel="noreferrer" {...p} />,
  table: (p) => <div className="my-3 overflow-x-auto"><table className="w-full text-sm" {...p} /></div>,
  th: (p) => <th className="border-b border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500" {...p} />,
  td: (p) => <td className="border-b border-slate-100 px-3 py-1.5 text-slate-700" {...p} />,
  code: (p) => <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs" {...p} />,
};

export default function Markdown({ children, className = "" }) {
  return (
    <div className={`text-sm ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{children || ""}</ReactMarkdown>
    </div>
  );
}
