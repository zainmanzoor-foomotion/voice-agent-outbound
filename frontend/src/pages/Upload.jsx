import { useState } from "react";
import { uploadClientsFile } from "../services/api";

// File upload page: pick a CSV/XLSX, send it to the backend, show the report.
export default function Upload() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const data = await uploadClientsFile(file);
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Upload Clients</h2>
        <p className="text-slate-500">
          Upload a CSV or XLSX with a list of leads to call.
        </p>
      </div>

      <form
        onSubmit={handleUpload}
        className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4"
      >
        <label className="block">
          <span className="text-sm font-medium text-slate-700">
            Select a CSV or XLSX file
          </span>
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-1 block w-full text-sm text-slate-600
                       file:mr-4 file:py-2 file:px-4
                       file:rounded-md file:border-0
                       file:text-sm file:font-medium
                       file:bg-brand-50 file:text-brand-700
                       hover:file:bg-brand-100"
          />
        </label>

        <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-md p-3">
          <p className="font-medium text-slate-700 mb-1">Required columns:</p>
          <code className="block">name, phone_number, company, email</code>
          <p className="mt-1">
            Only <code>phone_number</code> is strictly required; everything else
            is optional.
          </p>
        </div>

        <button
          type="submit"
          disabled={!file || busy}
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-400 text-white rounded-lg font-medium transition"
        >
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800 text-sm">
          {error}
        </div>
      )}

      {result && (() => {
        const r = result.report || {};
        const inserted = r.inserted ?? 0;
        const dup = r.skipped_duplicate ?? 0;
        const invalid = r.skipped_invalid_phone ?? 0;

        // If nothing was inserted, show a warning banner instead of success.
        const nothingInserted = inserted === 0 && (dup > 0 || invalid > 0);

        const palette = nothingInserted
          ? "bg-amber-50 border-amber-200 text-amber-900"
          : "bg-emerald-50 border-emerald-200 text-emerald-900";

        return (
          <div className={`border rounded-lg p-4 text-sm space-y-1 ${palette}`}>
            <p className="font-semibold">
              {nothingInserted
                ? `No new clients added — every row was skipped`
                : `Upload complete — ${inserted} client(s) added`}
            </p>
            <p>File: {result.filename}</p>
            <ul className="list-disc list-inside">
              <li>Total rows: {r.total_rows ?? 0}</li>
              <li>Inserted: {inserted}</li>
              <li>Skipped (invalid phone): {invalid}</li>
              <li>Skipped (already in database): {dup}</li>
            </ul>
            {nothingInserted && dup > 0 && (
              <p className="mt-2">
                Tip: these phone numbers already exist in the database. Either
                edit the CSV to use new numbers, or delete the existing client
                rows from the <strong>Clients</strong> page first.
              </p>
            )}
            {r.errors?.length ? (
              <p className="text-red-700">Errors: {r.errors.join("; ")}</p>
            ) : null}
          </div>
        );
      })()}
    </div>
  );
}
