import { useEffect, useState } from "react";
import { fetchStats, startCalls } from "../services/api";
import StatCard from "../components/StatCard";

// Landing page: shows aggregate counters and a "Start AI Calls" button.
export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [callStatus, setCallStatus] = useState(null);
  const [calling, setCalling] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const data = await fetchStats();
      setStats(data);
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleStartCalls = async () => {
    setCalling(true);
    setCallStatus(null);
    try {
      const result = await startCalls();
      setCallStatus(result);
      load();
    } catch (err) {
      setCallStatus({
        success: false,
        error: err?.response?.data?.error || err.message,
      });
    } finally {
      setCalling(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Dashboard</h2>
          <p className="text-slate-500">
            Overview of clients, calls, and AI conversations.
          </p>
        </div>
        <button
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-400 text-white rounded-lg font-medium shadow-sm transition"
          onClick={handleStartCalls}
          disabled={calling}
        >
          {calling ? "Starting calls…" : "Start AI Calls"}
        </button>
      </div>

      {callStatus && (
        <div
          className={`rounded-lg p-3 text-sm border ${
            callStatus.success
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          {callStatus.success
            ? `Started ${callStatus.started ?? 0} call(s)${
                callStatus.failed ? `, ${callStatus.failed} failed.` : "."
              } ${callStatus.message || ""}`
            : `Failed: ${callStatus.error || "Unknown error."}`}
        </div>
      )}

      {loading && <p className="text-slate-500">Loading stats…</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard label="Total Clients" value={stats.total_clients} />
          <StatCard label="Total Calls" value={stats.total_calls} />
          <StatCard
            label="Completed"
            value={stats.completed_calls}
            accent="green"
          />
          <StatCard
            label="Pending"
            value={stats.pending_calls}
            accent="yellow"
          />
          <StatCard label="Failed" value={stats.failed_calls} accent="red" />
          <StatCard
            label="Highly Interested"
            value={stats.highly_interested_clients}
            accent="brand"
          />
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="font-semibold text-slate-800 mb-2">How it works</h3>
        <ol className="list-decimal list-inside text-sm text-slate-600 space-y-1">
          <li>
            Upload a CSV/XLSX of clients (must include a{" "}
            <code className="bg-slate-100 px-1 rounded">phone_number</code>{" "}
            column).
          </li>
          <li>
            Click <strong>Start AI Calls</strong> — Twilio places outbound calls
            to each client.
          </li>
          <li>The AI agent speaks, listens, and extracts useful info.</li>
          <li>
            Review every transcript and call status on the{" "}
            <strong>Calls</strong> page.
          </li>
        </ol>
      </div>
    </div>
  );
}
