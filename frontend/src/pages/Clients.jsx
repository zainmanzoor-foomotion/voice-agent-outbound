import { useEffect, useState } from "react";
import {
  fetchClients,
  callClient,
  fetchInvitation,
  deleteClient,
} from "../services/api";

// Clients page: searchable list + per-row "Call now" action.
export default function Clients() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);
  const [callingId, setCallingId] = useState(null);
  const [callMessage, setCallMessage] = useState(null);

  const load = async (q = "") => {
    try {
      setLoading(true);
      const data = await fetchClients(q);
      setClients(data);
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

  const handleSearch = (e) => {
    e.preventDefault();
    load(search.trim());
  };

  const handleCall = async (id) => {
    setCallingId(id);
    setCallMessage(null);
    try {
      const data = await callClient(id);
      const sid = data.result?.call_sid || data.result?.vapi_call_id;
      setCallMessage({
        success: data.success,
        text: data.success
          ? sid
            ? `Call started. Vapi ID: ${sid}. Status will update on the Calls page.`
            : "Call started. Watch the Calls page for updates."
          : `Failed: ${data.result?.error || "Unknown error."}`,
      });
    } catch (err) {
      setCallMessage({
        success: false,
        text: err?.response?.data?.error || err.message,
      });
    } finally {
      setCallingId(null);
    }
  };

  const handleDelete = async (client) => {
    const ok = window.confirm(
      `Delete ${client.name || client.phone_number}? This also deletes their calls and transcripts.`
    );
    if (!ok) return;
    try {
      await deleteClient(client.id);
      load(search.trim());
      setCallMessage({ success: true, text: "Client deleted." });
    } catch (err) {
      setCallMessage({
        success: false,
        text: err?.response?.data?.error || err.message,
      });
    }
  };

  const handleWhatsApp = async (id) => {
    setCallMessage(null);
    try {
      const data = await fetchInvitation(id);
      // Open WhatsApp Web (or the WhatsApp app if on mobile) with the
      // pre-filled message in a new tab.
      window.open(data.whatsapp_url, "_blank", "noopener");
      // Also copy the talk URL to the clipboard so the admin can paste
      // it elsewhere if WhatsApp doesn't open (e.g. blocked popups).
      try {
        await navigator.clipboard.writeText(data.talk_url);
      } catch {}
      setCallMessage({
        success: true,
        text: `WhatsApp opened with the invite for ${data.name || data.phone_number}. The talk link was also copied to your clipboard.`,
      });
    } catch (err) {
      setCallMessage({
        success: false,
        text: err?.response?.data?.error || err.message,
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Clients</h2>
          <p className="text-slate-500">All uploaded leads.</p>
        </div>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            placeholder="Search by name, phone, company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-md text-sm w-72 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            type="submit"
            className="px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-md text-sm"
          >
            Search
          </button>
        </form>
      </div>

      {callMessage && (
        <div
          className={`rounded-lg p-3 text-sm border ${
            callMessage.success
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          {callMessage.text}
        </div>
      )}

      {loading && <p className="text-slate-500">Loading clients…</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {!loading && !error && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Phone</th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Interest</th>
                <th className="px-4 py-3 font-medium">Extracted info</th>
                <th className="px-4 py-3 font-medium">Calls</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {clients.length === 0 && (
                <tr>
                  <td colSpan="7" className="px-4 py-6 text-center text-slate-500">
                    No clients yet. Upload a CSV/XLSX to get started.
                  </td>
                </tr>
              )}
              {clients.map((c) => (
                <tr key={c.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-medium text-slate-800">
                    {c.name || <span className="text-slate-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{c.phone_number}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {c.company || <span className="text-slate-400">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <InterestBadge level={c.interest_level} />
                  </td>
                  <td className="px-4 py-3 text-slate-600 max-w-xs">
                    <ExtractedInfo data={c.extracted_information} />
                  </td>
                  <td className="px-4 py-3 text-slate-700">{c.total_calls}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        className="px-3 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-md"
                        onClick={() => handleWhatsApp(c.id)}
                        title="Send a WhatsApp invite with a click-to-talk link"
                      >
                        WhatsApp
                      </button>
                      <button
                        className="px-3 py-1.5 text-xs bg-brand-500 hover:bg-brand-600 disabled:bg-slate-400 text-white rounded-md"
                        onClick={() => handleCall(c.id)}
                        disabled={callingId === c.id}
                        title="Place an outbound phone call via Vapi (requires a paid phone number for international)"
                      >
                        {callingId === c.id ? "Calling…" : "Phone"}
                      </button>
                      <button
                        className="px-3 py-1.5 text-xs bg-red-100 hover:bg-red-200 text-red-700 rounded-md"
                        onClick={() => handleDelete(c)}
                        title="Delete this client and all of their calls"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function InterestBadge({ level }) {
  const map = {
    high: "bg-emerald-100 text-emerald-700",
    medium: "bg-amber-100 text-amber-700",
    low: "bg-slate-100 text-slate-600",
    unknown: "bg-slate-100 text-slate-500",
  };
  const cls = map[level] || map.unknown;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${cls}`}>
      {level || "unknown"}
    </span>
  );
}

function ExtractedInfo({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return <span className="text-slate-400">—</span>;
  }
  const entries = Object.entries(data).filter(
    ([, v]) => v !== "" && v !== false && v !== null && v !== undefined && v !== "unknown"
  );
  if (entries.length === 0) {
    return <span className="text-slate-400">—</span>;
  }
  return (
    <ul className="text-xs space-y-0.5">
      {entries.map(([k, v]) => (
        <li key={k}>
          <span className="font-medium text-slate-700">{k}:</span>{" "}
          <span className="text-slate-600">{String(v)}</span>
        </li>
      ))}
    </ul>
  );
}
