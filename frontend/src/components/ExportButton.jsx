import { useState } from "react";
import { Download, Loader2, ChevronDown, FileText, FileType, User, Briefcase } from "lucide-react";

async function downloadBlob(promise, filename) {
  const r = await promise;
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * ExportButton with format + audience selectors.
 * `apiCall(format, audience)` is invoked when user picks a combination.
 * For Compare report (no audience switch needed) pass `supportsAudience={false}`.
 */
export default function ExportButton({
  apiCall,
  filenameBase,
  label = "Export",
  disabled = false,
  supportsAudience = true,
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [audience, setAudience] = useState("client");

  const handle = async (format) => {
    setOpen(false);
    setBusy(true);
    setErr(null);
    try {
      await downloadBlob(
        apiCall(format, audience),
        `${filenameBase}_${audience}.${format}`,
      );
    } catch (e) {
      const msg =
        e?.response?.status === 503
          ? "PDF service unavailable. Try Word format."
          : "Export failed. Please try again.";
      setErr(msg);
      setTimeout(() => setErr(null), 4000);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition"
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Download className="h-4 w-4" />
        )}
        {busy ? "Preparing..." : label}
        {!busy && <ChevronDown className="h-3.5 w-3.5 opacity-60" />}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-64 bg-white border border-slate-200 rounded-lg shadow-lg z-10 overflow-hidden">
          {supportsAudience && (
            <div className="border-b border-slate-100 p-2">
              <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1 px-1">
                Audience
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => setAudience("client")}
                  className={`flex-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded text-xs font-medium ${
                    audience === "client"
                      ? "bg-brand-700 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  <User className="h-3 w-3" />
                  For client
                </button>
                <button
                  onClick={() => setAudience("advisor")}
                  className={`flex-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded text-xs font-medium ${
                    audience === "advisor"
                      ? "bg-brand-700 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  <Briefcase className="h-3 w-3" />
                  For advisor
                </button>
              </div>
            </div>
          )}
          <button
            onClick={() => handle("docx")}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 text-left"
          >
            <FileText className="h-4 w-4 text-brand-700" />
            Word (.docx)
          </button>
          <button
            onClick={() => handle("pdf")}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 text-left"
          >
            <FileType className="h-4 w-4 text-rose-600" />
            PDF
          </button>
        </div>
      )}

      {err && (
        <div className="absolute right-0 mt-1 w-64 bg-rose-50 border border-rose-200 rounded-lg p-2 text-xs text-rose-700 z-10">
          {err}
        </div>
      )}
    </div>
  );
}
