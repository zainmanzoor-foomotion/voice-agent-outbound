import { useEffect, useState } from "react";
import { fetchCalls } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import TranscriptModal from "../components/TranscriptModal";

const STATUS_OPTIONS = [
  "",
  "pending",
  "initiated",
  "answered",
  "in-progress",
  "completed",
  "failed",
  "no_answer",
];

function formatDuration(seconds) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

// Calls page: filter, view status, and open transcripts.
export default function Calls() {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [openCallId, setOpenCallId] = useState(null);

  const load = async () => {
    try {
      setLoading(true);
      const data = await fetchCalls(statusFilter ? { status: statusFilter } : {});
      setCalls(data);
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [statusFilter]);

  // Auto-refresh while calls are in flight so the dashboard stays live.
  useEffect(() => {
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Calls</h2>
          <p className="text-slate-500">
            All outbound AI calls. Click a row to view the transcript.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2 py-1.5 border border-slate-300 rounded-md text-sm"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s || "all"}
              </option>
            ))}
          </select>
          <button
            onClick={load}
            className="px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200 rounded-md text-slate-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading && <p className="text-slate-500">Loading…</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {!loading && !error && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Client</th>
                <th className="px-4 py-3 font-medium">Phone</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3 font-medium">Duration</th>
                <th className="px-4 py-3 font-medium">Messages</th>
                <th className="px-4 py-3 font-medium">Summary</th>
              </tr>
            </thead>
            <tbody>
              {calls.length === 0 && (
                <tr>
                  <td
                    colSpan="7"
                    className="px-4 py-6 text-center text-slate-500"
                  >
                    No calls yet.
                  </td>
                </tr>
              )}
              {calls.map((c) => (
                <tr
                  key={c.id}
                  className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => setOpenCallId(c.id)}
                >
                  <td className="px-4 py-3 font-medium text-slate-800">
                    {c.client_name || (
                      <span className="text-slate-400">Unknown</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{c.client_phone}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    {formatDate(c.started_at)}
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    {formatDuration(c.duration_seconds)}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{c.message_count}</td>
                  <td className="px-4 py-3 text-slate-600 max-w-md truncate">
                    {c.summary || (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <TranscriptModal
        callId={openCallId}
        onClose={() => setOpenCallId(null)}
      />
    </div>
  );
}
