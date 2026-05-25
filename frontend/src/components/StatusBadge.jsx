// Color-coded badge for a call status.
const STYLES = {
  pending: "bg-slate-100 text-slate-700",
  initiated: "bg-blue-100 text-blue-700",
  answered: "bg-indigo-100 text-indigo-700",
  "in-progress": "bg-indigo-100 text-indigo-700",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  no_answer: "bg-amber-100 text-amber-700",
};

export default function StatusBadge({ status }) {
  const cls = STYLES[status] || "bg-slate-100 text-slate-700";
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}
    >
      {status}
    </span>
  );
}
