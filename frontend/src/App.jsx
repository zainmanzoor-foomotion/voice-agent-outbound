import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import Clients from "./pages/Clients";
import Calls from "./pages/Calls";
import WebCall from "./pages/WebCall";

// Root component: admin dashboard layout.
// (The public /talk/<token> landing page is served directly by FastAPI
// so customers tapping the WhatsApp link reach a single URL.)
export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/calls" element={<Calls />} />
          <Route path="/web-call" element={<WebCall />} />
          <Route
            path="*"
            element={
              <div className="text-center text-slate-600 py-16">
                <h2 className="text-xl font-semibold">Page not found</h2>
                <p className="text-sm">Use the navigation above.</p>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="text-center text-xs text-slate-500 py-4">
        AI Voice Call Agent · Demo build
      </footer>
    </div>
  );
}
