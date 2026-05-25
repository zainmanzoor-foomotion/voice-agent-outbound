import { NavLink } from "react-router-dom";

// Top navigation bar shared across every page.
const links = [
  { to: "/", label: "Dashboard" },
  { to: "/upload", label: "Upload" },
  { to: "/clients", label: "Clients" },
  { to: "/calls", label: "Calls" },
  { to: "/web-call", label: "Web Test" },
];

export default function Navbar() {
  return (
    <header className="bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-500 text-white flex items-center justify-center font-bold">
            AI
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-800">
              AI Voice Call Agent
            </h1>
            <p className="text-xs text-slate-500">
              Outbound sales & support demo
            </p>
          </div>
        </div>
        <nav className="flex items-center gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
