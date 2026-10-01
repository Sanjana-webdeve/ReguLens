import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Documents from "./pages/Documents.jsx";
import Assistant from "./pages/Assistant.jsx";
import Requirements from "./pages/Requirements.jsx";
import Compare from "./pages/Compare.jsx";
import ComparisonDetail from "./pages/ComparisonDetail.jsx";
import Versions from "./pages/Versions.jsx";
import Search from "./pages/Search.jsx";
import Reports from "./pages/Reports.jsx";
import Audit from "./pages/Audit.jsx";
import Admin from "./pages/Admin.jsx";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/requirements" element={<Requirements />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/compare/:id" element={<ComparisonDetail />} />
        <Route path="/versions" element={<Versions />} />
        <Route path="/search" element={<Search />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
