import { useState, useEffect, useCallback, useMemo } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { getSession, signOut, onAuthStateChange } from "../../services/supabase";
import { isSupabaseConfigured, fullSync } from "../../services/syncEngine";
import { isAdmin } from "../../services/adminAuth";
import "./Sidebar.css";

const baseNavItems = [
  { path: "/", label: "Import" },
  { path: "/results", label: "Report Explanation" },
  { path: "/letters", label: "Letters" },
  { path: "/history", label: "History" },
  { path: "/teaching-points", label: "Teaching Points" },
  { path: "/templates", label: "Templates" },
  { path: "/settings", label: "Settings" },
];

function getNavItems(userEmail: string | null) {
  if (isAdmin(userEmail)) {
    return [...baseNavItems, { path: "/admin", label: "Admin" }];
  }
  return baseNavItems;
}

interface UpdateInfo {
  version: string;
  available: boolean;
}

export function Sidebar() {
  const navigate = useNavigate();
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [isInstalling, setIsInstalling] = useState(false);
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    getSession().then((session) => {
      setIsSignedIn(!!session);
      setUserEmail(session?.user?.email ?? null);
      if (session) fullSync().catch(() => {});
    });
    const unsub = onAuthStateChange((session) => {
      setIsSignedIn(!!session);
      setUserEmail(session?.user?.email ?? null);
      if (session) fullSync().catch(() => {});
    });
    return unsub;
  }, []);

  const handleSignOut = useCallback(async () => {
    await signOut();
    setIsSignedIn(false);
    setUserEmail(null);
  }, []);

  useEffect(() => {
    // Check for updates on mount
    let cancelled = false;
    const checkUpdate = async () => {
      try {
        const { check } = await import("@tauri-apps/plugin-updater");
        const update = await check();
        if (update && !cancelled) {
          setUpdateInfo({ version: update.version, available: true });
        }
      } catch {
        // Updater not available or failed silently
      }
    };
    checkUpdate();
    return () => { cancelled = true; };
  }, []);

  const handleInstall = useCallback(async () => {
    setIsInstalling(true);
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (update) {
        await update.downloadAndInstall();
        const { relaunch } = await import("@tauri-apps/plugin-process");
        await relaunch();
      }
    } catch {
      setIsInstalling(false);
    }
  }, []);

  const navItems = useMemo(() => getNavItems(userEmail), [userEmail]);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1 className="sidebar-title">Explify</h1>
        <span className="sidebar-descriptor">Explain Better</span>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "sidebar-link--active" : ""}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      {isSupabaseConfigured() && (
        <div className="sidebar-auth">
          {isSignedIn ? (
            <>
              <span className="auth-user-email">{userEmail}</span>
              <button className="auth-signout-btn" onClick={handleSignOut}>
                Sign Out
              </button>
            </>
          ) : (
            <button
              className="auth-signin-btn"
              onClick={() => navigate("/auth")}
            >
              Sign In
            </button>
          )}
        </div>
      )}
      {updateInfo?.available && (
        <div className="sidebar-update-banner">
          <span className="update-text">Update available: v{updateInfo.version}</span>
          <button
            className="update-install-btn"
            onClick={handleInstall}
            disabled={isInstalling}
          >
            {isInstalling ? "Installing..." : "Install"}
          </button>
        </div>
      )}
    </aside>
  );
}
