import { useEffect, useState } from "react";
import { fetchCall } from "../services/api";

// Modal that loads and shows the full transcript for a call.
export default function TranscriptModal({ callId, onClose }) {
  const [call, setCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!callId) return;
    setLoading(true);
    fetchCall(callId)
      .then((data) => {
        setCall(data);
        setError(null);
      })
      .catch((err) => setError(err?.response?.data?.error || err.message))
      .finally(() => setLoading(false));
  }, [callId]);

  if (!callId) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-800">
              Call Transcript
            </h3>
            {call && (
              <p className="text-sm text-slate-500">
                {call.client_name || "Unknown"} · {call.client_phone}
              </p>
            )}
          </div>
          <button
            className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-4 overflow-y-auto flex-1">
          {loading && <p className="text-slate-500">Loading…</p>}
          {error && <p className="text-red-600">Error: {error}</p>}

          {!loading && !error && call && (
            <>
              {call.summary && (
                <div className="mb-4 p-3 rounded-lg bg-brand-50 border border-brand-100 text-sm text-slate-700">
                  <p className="font-semibold text-brand-700 mb-1">Summary</p>
                  <p>{call.summary}</p>
                </div>
              )}

              {call.messages?.length ? (
                <div className="space-y-3">
                  {call.messages.map((m) => (
                    <div
                      key={m.id}
                      className={`flex ${
                        m.speaker === "assistant"
                          ? "justify-start"
                          : "justify-end"
                      }`}
                    >
                      <div
                        className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                          m.speaker === "assistant"
                            ? "bg-slate-100 text-slate-800"
                            : "bg-brand-500 text-white"
                        }`}
                      >
                        <p className="text-[10px] uppercase tracking-wide opacity-70 mb-0.5">
                          {m.speaker}
                        </p>
                        <p>{m.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500">No transcript yet.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
