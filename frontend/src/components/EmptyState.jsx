import { Inbox } from "lucide-react";

export default function EmptyState({ icon: Icon = Inbox, title, body, cta }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <div className="mx-auto w-12 h-12 rounded-full bg-brand-50 flex items-center justify-center text-brand-500">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
      {body && <p className="mt-1 text-sm text-slate-500 max-w-md mx-auto">{body}</p>}
      {cta && <div className="mt-4">{cta}</div>}
    </div>
  );
}
