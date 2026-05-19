import { useState } from "react";
import { Download, Loader2, ChevronDown, FileText, FileType } from "lucide-react";

/* Triggers an axios blob download and saves it to disk under `filename`. */
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

/* Used by FundDetail (apiCall expects format arg) and Compare. */
export default function ExportButton({
  apiCall,
  filenameBase,
  label = "Export",
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handle = async (format) => {
    setOpen(false);
    setBusy(true);
    setErr(null);
    try {
      await downloadBlob(apiCall(format), `${filenameBase}.${format}`);
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
        <div className="absolute right-0 mt-1 w-44 bg-white border border-slate-200 rounded-lg shadow-lg z-10 overflow-hidden">
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
