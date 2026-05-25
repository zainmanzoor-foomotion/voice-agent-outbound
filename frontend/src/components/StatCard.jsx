// Reusable stat card used on the dashboard.
export default function StatCard({ label, value, accent = "brand" }) {
  const accentMap = {
    brand: "text-brand-600",
    green: "text-emerald-600",
    yellow: "text-amber-600",
    red: "text-red-600",
    slate: "text-slate-700",
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${accentMap[accent] || accentMap.brand}`}>
        {value}
      </p>
    </div>
  );
}
