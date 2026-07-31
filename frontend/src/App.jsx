import { Navigate, Route, Routes, Link } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Login from "./auth/Login";
import Register from "./auth/Register";
import Dashboard from "./projects/Dashboard";
import ProjectDetail from "./projects/ProjectDetail";
import UserStoryDetail from "./userStories/UserStoryDetail";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page"><p className="muted">Loading…</p></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function PublicOnlyRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page"><p className="muted">Loading…</p></div>;
  if (user) return <Navigate to="/" replace />;
  return children;
}

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="app-header">
      <Link to="/" className="brand">
        Multi-Agent Test Framework
      </Link>
      {user && (
        <div className="header-right">
          <span className="muted">{user.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      )}
    </header>
  );
}

export default function App() {
  return (
    <>
      <Header />
      <main>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicOnlyRoute>
                <Login />
              </PublicOnlyRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicOnlyRoute>
                <Register />
              </PublicOnlyRoute>
            }
          />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:projectId"
            element={
              <ProtectedRoute>
                <ProjectDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:projectId/user-stories/:storyId"
            element={
              <ProtectedRoute>
                <UserStoryDetail />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
