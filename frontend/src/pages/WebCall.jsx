import { useEffect, useRef, useState } from "react";
import Vapi from "@vapi-ai/web";
import {
  fetchClients,
  initWebCall,
  notifyWebCallStarted,
} from "../services/api";

/**
 * WebCall page
 * ------------
 * In-browser test of the AI agent using Vapi's Web SDK.
 *
 * Flow:
 *   1. POST /web-call/init  -> returns { public_key, assistant, local_call_id }
 *   2. new Vapi(public_key).start(assistant)
 *   3. On call-start, tell the backend Vapi's call.id so webhooks match.
 *   4. Mic audio streams to Vapi -> Groq -> Vapi TTS -> back to your speakers.
 *   5. Webhooks (transcripts, end-of-call-report) flow to /vapi-webhook,
 *      and the call shows up on the Calls page automatically.
 */

const STATUS_LABELS = {
  idle: "Idle",
  connecting: "Connecting…",
  connected: "Connected — speaking with AI",
  listening: "Listening to you",
  speaking: "AI is speaking",
  ending: "Ending call…",
  ended: "Call ended",
  error: "Error",
};

export default function WebCall() {
  const [clients, setClients] = useState([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [volume, setVolume] = useState(0);

  // Vapi SDK instance + the local Call row id, kept in refs so the
  // event handlers always see the latest values.
  const vapiRef = useRef(null);
  const localCallIdRef = useRef(null);

  // Load existing clients for the optional dropdown.
  useEffect(() => {
    fetchClients()
      .then((c) => setClients(c))
      .catch(() => {});
  }, []);

  // Cleanup if the user navigates away mid-call.
  useEffect(() => {
    return () => {
      try {
        vapiRef.current?.stop();
      } catch {}
    };
  }, []);

  const appendTranscript = (speaker, text) => {
    if (!text) return;
    setTranscript((prev) => {
      // Avoid duplicate consecutive lines.
      const last = prev[prev.length - 1];
      if (last && last.speaker === speaker && last.content === text) return prev;
      return [...prev, { speaker, content: text }];
    });
  };

  const handleStart = async () => {
    setError(null);
    setTranscript([]);
    setStatus("connecting");

    try {
      const { public_key, assistant, local_call_id } = await initWebCall(
        selectedClientId ? Number(selectedClientId) : null
      );
      localCallIdRef.current = local_call_id;

      const vapi = new Vapi(public_key);
      vapiRef.current = vapi;

      vapi.on("call-start", () => {
        setStatus("connected");
      });

      vapi.on("call-end", () => {
        setStatus("ended");
      });

      vapi.on("speech-start", () => setStatus("speaking"));
      vapi.on("speech-end", () => setStatus("listening"));

      vapi.on("volume-level", (v) => setVolume(v));

      vapi.on("message", (msg) => {
        // Final transcript chunks contain speaker + transcript text.
        if (msg?.type === "transcript" && msg?.transcriptType === "final") {
          const role = msg.role === "assistant" ? "assistant" : "user";
          appendTranscript(role, msg.transcript);
        }
      });

      vapi.on("error", (e) => {
        console.error("Vapi error", e);
        setError(e?.errorMsg || e?.message || "Vapi error");
        setStatus("error");
      });

      // Start the call — returns a Call object containing Vapi's call id.
      const call = await vapi.start(assistant);
      const vapiCallId = call?.id || call?.callId;
      if (vapiCallId && local_call_id) {
        try {
          await notifyWebCallStarted(local_call_id, vapiCallId);
        } catch (err) {
          console.warn("Failed to notify backend of vapi_call_id:", err);
        }
      }
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.error || err.message || "Failed to start.");
      setStatus("error");
    }
  };

  const handleEnd = () => {
    setStatus("ending");
    try {
      vapiRef.current?.stop();
    } catch (err) {
      console.warn("Stop error:", err);
    }
  };

  const inCall = ["connecting", "connected", "listening", "speaking"].includes(
    status
  );

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Web Test Call</h2>
        <p className="text-slate-500">
          Talk to the AI agent directly from your browser — no phone number
          needed. Free on any Vapi account.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
        <div>
          <label className="text-sm font-medium text-slate-700">
            (Optional) Pretend to be one of your uploaded clients
          </label>
          <select
            value={selectedClientId}
            onChange={(e) => setSelectedClientId(e.target.value)}
            disabled={inCall}
            className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-md text-sm bg-white"
          >
            <option value="">— Generic Web Visitor —</option>
            {clients
              .filter((c) => c.phone_number !== "+10000000000")
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name || "Unknown"} · {c.company || "—"} · {c.phone_number}
                </option>
              ))}
          </select>
          <p className="text-xs text-slate-500 mt-1">
            Selecting a client personalizes the AI's greeting and saves the
            transcript against that client's record.
          </p>
        </div>

        <div className="flex items-center gap-4">
          {!inCall ? (
            <button
              onClick={handleStart}
              className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg font-medium shadow-sm"
            >
              Start Web Call
            </button>
          ) : (
            <button
              onClick={handleEnd}
              className="px-5 py-2.5 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium shadow-sm"
            >
              End Call
            </button>
          )}

          <div className="flex items-center gap-2">
            <span
              className={`inline-block w-3 h-3 rounded-full ${
                inCall
                  ? "bg-emerald-500 animate-pulse"
                  : status === "error"
                  ? "bg-red-500"
                  : "bg-slate-300"
              }`}
            />
            <span className="text-sm text-slate-700">
              {STATUS_LABELS[status] || status}
            </span>
          </div>
        </div>

        {/* Volume meter when AI is speaking */}
        {inCall && (
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all"
              style={{ width: `${Math.min(100, Math.round(volume * 200))}%` }}
            />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-800">
            {error}
          </div>
        )}
      </div>

      {/* Live transcript */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
        <h3 className="font-semibold text-slate-800 mb-3">Live Transcript</h3>
        {transcript.length === 0 ? (
          <p className="text-sm text-slate-500">
            Once the call starts, what you say and what the AI says will appear
            here in real time. The full transcript is also saved to the{" "}
            <strong>Calls</strong> page.
          </p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {transcript.map((m, i) => (
              <div
                key={i}
                className={`flex ${
                  m.speaker === "assistant" ? "justify-start" : "justify-end"
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
        )}
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs text-slate-600 space-y-1">
        <p className="font-medium text-slate-700">Tips</p>
        <ul className="list-disc list-inside space-y-0.5">
          <li>
            Your browser will ask for microphone permission the first time —
            allow it.
          </li>
          <li>
            Use headphones for the cleanest test (avoids the AI hearing its own
            voice).
          </li>
          <li>
            After ending the call, refresh the <strong>Calls</strong> page to
            see the saved transcript and extracted info.
          </li>
        </ul>
      </div>
    </div>
  );
}
