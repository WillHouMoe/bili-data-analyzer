import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import VideoDetailPage from "./pages/VideoDetail";
import Settings from "./pages/Settings";

/**
 * Each creator and each video gets its own instance. Remounting on the id is
 * how a page drops the previous sheet's state — no reset effects, no stale
 * figures from the previous creator flashing under the new masthead.
 */
function KeyedDashboard() {
  const { uid } = useParams<{ uid?: string }>();
  return <Dashboard key={uid ?? "none"} />;
}

function KeyedVideoDetail() {
  const { bvid } = useParams<{ bvid: string }>();
  return <VideoDetailPage key={bvid} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<KeyedDashboard />} />
          <Route path="/dashboard/:uid" element={<KeyedDashboard />} />
          <Route path="/video/:bvid" element={<KeyedVideoDetail />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
