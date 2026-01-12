import React, { useState, useEffect } from "react";
import { supabase } from "../lib/supabase";
import { Session } from "@supabase/supabase-js";
import { LoginPage } from "./LoginPage";

export interface SettingsPanelProps {
  isVisible: boolean;
  onClose: () => void;
  onSettingsChange?: (settings: UserSettings) => void;
}

// Export UserSettings type
export type { UserSettings };

interface UserSettings {
  emailAlerts: boolean;
  pushNotifications: boolean;
  autoRefresh: boolean;
  showPolygons: boolean;
  mapTheme: string;
  minSeverity: string;
  defaultTimeRange: string;
}

const DEFAULT_SETTINGS: UserSettings = {
  emailAlerts: false,
  pushNotifications: false,
  autoRefresh: true,
  showPolygons: true,
  mapTheme: "custom",
  minSeverity: "all",
  defaultTimeRange: "all",
};

export const SettingsPanel: React.FC<SettingsPanelProps> = ({
  isVisible,
  onClose,
  onSettingsChange,
}) => {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLoginPage, setShowLoginPage] = useState(false);
  const [showChangelog, setShowChangelog] = useState(false);
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);

  // Load settings from localStorage when user session changes
  useEffect(() => {
    if (session?.user?.email) {
      const storageKey = `reach_settings_${session.user.email}`;
      const savedSettings = localStorage.getItem(storageKey);
      if (savedSettings) {
        try {
          setSettings(JSON.parse(savedSettings));
        } catch (error) {
          console.error("Failed to load settings:", error);
          setSettings(DEFAULT_SETTINGS);
        }
      } else {
        setSettings(DEFAULT_SETTINGS);
      }
    }
  }, [session]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session) {
        setShowLoginPage(false);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Save settings to localStorage
  const saveSettings = (newSettings: UserSettings) => {
    if (session?.user?.email) {
      const storageKey = `reach_settings_${session.user.email}`;
      localStorage.setItem(storageKey, JSON.stringify(newSettings));
      setSettings(newSettings);
      // Notify parent component of settings change
      onSettingsChange?.(newSettings);
    }
  };

  const updateSetting = <K extends keyof UserSettings>(
    key: K,
    value: UserSettings[K]
  ) => {
    // Intercept push notifications to request permission
    if (key === "pushNotifications" && value === true) {
      if (!("Notification" in window)) {
        alert("This browser does not support desktop notification");
        return;
      }

      if (Notification.permission !== "granted") {
        Notification.requestPermission().then((permission) => {
          if (permission === "granted") {
            const newSettings = { ...settings, [key]: true };
            saveSettings(newSettings);
            new Notification("Notifications Enabled", {
              body: "You will now receive alerts from Reach.",
            });
          } else {
            const newSettings = { ...settings, [key]: false };
            saveSettings(newSettings);
            alert(
              "Permission denied. Please enable notifications in your browser settings."
            );
          }
        });
        return;
      }
    }

    // Intercept email alerts to show confirmation
    if (key === "emailAlerts") {
      if (value === true) {
        alert(`Email alerts enabled for ${session?.user?.email}`);
      } else {
        alert(`Email alerts disabled for ${session?.user?.email}`);
      }
    }

    const newSettings = { ...settings, [key]: value };
    saveSettings(newSettings);
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
  };

  const handleLoginSuccess = () => {
    setShowLoginPage(false);
  };

  return (
    <>
      <div
        className={`fixed 
          bottom-4 left-4 right-4
          sm:left-22 sm:right-4
          top-20 sm:top-4
          frosted-glass 
          transform transition-all duration-300 ease-in-out z-40 
          overflow-hidden
          flex flex-col
          ${
            isVisible
              ? "translate-y-0 opacity-100"
              : "translate-y-full opacity-0 pointer-events-none"
          }
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-stone/20">
          <div className="flex items-center gap-3">
            <svg
              className="w-5 h-5 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            <h3 className="text-base font-medium text-white">Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-bangladesh-green rounded-full transition-colors"
          >
            <svg
              className="w-4 h-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div className="w-full h-px bg-stone mb-4"></div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto dark-scrollbar p-4">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin h-6 w-6 border-2 border-caribbean-green border-t-transparent rounded-full"></div>
            </div>
          ) : !session ? (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto py-8">
              <div className="w-16 h-16 bg-bangladesh-green/20 flex items-center justify-center mb-4">
                <svg
                  className="w-8 h-8 text-bangladesh-green"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">
                Uh oh, it seems you are not signed in yet.
              </h3>
              <p className="text-stone text-sm mb-6">
                You can make an account here and get notifications, it's free!
              </p>

              <button
                onClick={() => setShowLoginPage(true)}
                className="px-6 py-2.5 bg-bangladesh-green hover:bg-mountain-meadow rounded-lg text-white hover:text-dark-green font-semibold transition-colors"
              >
                Sign In / Sign Up
              </button>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto space-y-4">
              {/* Account Info */}
              <div className="flex items-center gap-3 p-3 bg-white/5">
                <div className="w-10 h-10 bg-bangladesh-green flex items-center justify-center text-white font-bold text-lg">
                  {session.user.email?.[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-white font-medium text-sm truncate">
                    {session.user.email}
                  </h4>
                  <p className="text-stone text-xs">Account Active</p>
                </div>
                <button
                  onClick={handleSignOut}
                  className="text-xs text-red-400 hover:text-red-300 font-medium px-2 py-1"
                >
                  Sign Out
                </button>
              </div>

              {/* Notifications Section */}
              <div className="bg-white/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                    />
                  </svg>
                  <span className="text-sm text-gray-400 font-medium">
                    Notifications
                  </span>
                </div>
                <div className="space-y-3">
                  <label className="flex items-center justify-between cursor-pointer hover:bg-rich-black/30 p-2 rounded">
                    <span className="text-sm text-gray-300">Email Alerts</span>
                    <input
                      type="checkbox"
                      className="filter-checkbox"
                      checked={settings.emailAlerts}
                      onChange={(e) =>
                        updateSetting("emailAlerts", e.target.checked)
                      }
                    />
                  </label>
                  <label className="flex items-center justify-between cursor-pointer hover:bg-rich-black/30 p-2 rounded">
                    <span className="text-sm text-gray-300">
                      Push Notifications
                    </span>
                    <input
                      type="checkbox"
                      className="filter-checkbox"
                      checked={settings.pushNotifications}
                      onChange={(e) =>
                        updateSetting("pushNotifications", e.target.checked)
                      }
                    />
                  </label>
                </div>
              </div>

              {/* Preferences Section */}
              <div className="bg-white/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
                    />
                  </svg>
                  <span className="text-sm text-gray-400 font-medium">
                    Preferences
                  </span>
                </div>
                <div className="space-y-3">
                  <div className="relative group">
                    <label className="flex items-center justify-between cursor-not-allowed hover:bg-rich-black/30 p-2 rounded opacity-60">
                      <span className="text-sm text-gray-300">Dark Mode</span>
                      <input
                        type="checkbox"
                        className="filter-checkbox"
                        checked={true}
                        disabled
                      />
                    </label>
                    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 px-3 py-1.5 bg-rich-black border border-bangladesh-green rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap text-xs text-white shadow-lg">
                      No light mode for you
                    </div>
                  </div>
                  <label className="flex items-center justify-between cursor-pointer hover:bg-rich-black/30 p-2 rounded">
                    <span className="text-sm text-gray-300">
                      Auto-refresh Alerts
                    </span>
                    <input
                      type="checkbox"
                      className="filter-checkbox"
                      checked={settings.autoRefresh}
                      onChange={(e) =>
                        updateSetting("autoRefresh", e.target.checked)
                      }
                    />
                  </label>
                </div>
              </div>

              {/* Map Settings Section */}
              <div className="bg-white/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                    />
                  </svg>
                  <span className="text-sm text-gray-400 font-medium">
                    Map Settings
                  </span>
                </div>
                <div className="space-y-3">
                  <label className="flex items-center justify-between cursor-pointer hover:bg-rich-black/30 p-2 rounded">
                    <span className="text-sm text-gray-300">Show Polygons</span>
                    <input
                      type="checkbox"
                      className="filter-checkbox"
                      checked={settings.showPolygons}
                      onChange={(e) =>
                        updateSetting("showPolygons", e.target.checked)
                      }
                    />
                  </label>
                  <div>
                    <label className="text-xs text-gray-400 mb-1.5 block">
                      Map Theme
                    </label>
                    <select
                      className="w-full search-input px-3 py-2 text-sm text-white rounded-md focus:outline-none transition-all"
                      value={settings.mapTheme}
                      onChange={(e) =>
                        updateSetting("mapTheme", e.target.value)
                      }
                    >
                      <option value="custom">Custom Dark</option>
                      <option value="dark-v11">Mapbox Dark</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Alert Preferences Section */}
              <div className="bg-white/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <span className="text-sm text-gray-400 font-medium">
                    Filter Defaults
                  </span>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-gray-400 mb-1.5 block">
                      Default Minimum Severity
                    </label>
                    <select
                      className="w-full search-input px-3 py-2 text-sm text-white rounded-md focus:outline-none transition-all"
                      value={settings.minSeverity}
                      onChange={(e) =>
                        updateSetting("minSeverity", e.target.value)
                      }
                    >
                      <option value="all">All Severities</option>
                      <option value="minor">Minor and above</option>
                      <option value="moderate">Moderate and above</option>
                      <option value="severe">Severe and above</option>
                      <option value="extreme">Extreme only</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Sets initial filter when you open the app
                    </p>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 mb-1.5 block">
                      Default Time Range
                    </label>
                    <select
                      className="w-full search-input px-3 py-2 text-sm text-white rounded-md focus:outline-none transition-all"
                      value={settings.defaultTimeRange}
                      onChange={(e) =>
                        updateSetting("defaultTimeRange", e.target.value)
                      }
                    >
                      <option value="24h">Last 24 hours</option>
                      <option value="7d">Last 7 days</option>
                      <option value="30d">Last 30 days</option>
                      <option value="90d">Last 90 days</option>
                      <option value="all">All time</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Sets initial date range when you open the app
                    </p>
                  </div>
                </div>
              </div>

              {/* About Section */}
              <div className="bg-white/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <span className="text-sm text-gray-400 font-medium">
                    About
                  </span>
                </div>
                <div className="space-y-2 text-xs text-gray-400">
                  <div className="flex justify-between">
                    <span>Version</span>
                    <span className="text-white">1.0.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Last Updated</span>
                    <span className="text-white">Dec 2025</span>
                  </div>
                  <button
                    onClick={() => setShowChangelog(true)}
                    className="text-bangladesh-green hover:text-mountain-meadow transition-colors text-left"
                  >
                    View Changelog
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Login Page Modal */}
      <LoginPage
        isVisible={showLoginPage}
        onClose={() => setShowLoginPage(false)}
        onSuccess={handleLoginSuccess}
      />

      {/* Changelog Modal */}
      <div
        className={`fixed inset-0 z-[60] flex items-center justify-center p-4
          transform transition-all duration-300 ease-in-out
          ${showChangelog ? "opacity-100" : "opacity-0 pointer-events-none"}
        `}
      >
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-rich-black/80"
          onClick={() => setShowChangelog(false)}
        />

        {/* Modal */}
        <div
          className={`relative bg-dark-green  max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col shadow-2xl
            transform transition-all duration-300 ease-in-out
            ${
              showChangelog
                ? "scale-100 translate-y-0"
                : "scale-95 translate-y-4"
            }
          `}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <svg
                className="w-5 h-5 text-bangladesh-green"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <h3 className="text-base font-medium text-white">Changelog</h3>
            </div>
            <button
              onClick={() => setShowChangelog(false)}
              className="p-1 hover:bg-bangladesh-green rounded-full transition-colors"
            >
              <svg
                className="w-4 h-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Separator line */}
          <div className="w-full h-px bg-stone mx-4"></div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto dark-scrollbar p-4 space-y-4">
            {/* Version v1.0.0 */}
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-bangladesh-green text-white text-xs font-bold rounded">
                  v1.0.0
                </span>
                <span className="text-xs text-gray-400">December 14, 2025</span>
              </div>
              <div className="space-y-2 text-sm">
                <h4 className="text-white font-semibold flex items-center gap-2">
                  <span className="text-caribbean-green">✨</span> New Features
                </h4>
                <ul className="space-y-1 text-gray-300 pl-6">
                  <li className="list-disc">
                    Customizable settings with persistent storage
                  </li>
                  <li className="list-disc">
                    Updated filtering options for alerts
                  </li>
                </ul>
                <h4 className="text-white font-semibold flex items-center gap-2">
                  <span className="text-blue-400">🔧</span> Improvements
                </h4>
                <ul className="space-y-1 text-gray-300 pl-6">
                  <li className="list-disc">
                    Enhanced map theme and user interface
                  </li>
                  <li className="list-disc">
                    Improved alert scraping and processing logic
                  </li>
                  <li className="list-disc">
                    Minor bug fixes and and user experience enhancements
                  </li>
                </ul>
              </div>
            </div>

            {/* Version 0.8.0 */}
            <div className="space-y-3 pt-4 border-t border-stone">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-stone/30 text-white text-xs font-bold rounded">
                  v0.8.0
                </span>
                <span className="text-xs text-gray-400">November 30, 2025</span>
              </div>
              <div className="space-y-2 text-sm">
                <h4 className="text-white font-semibold flex items-center gap-2">
                  <span className="text-caribbean-green">✨</span> New Features
                </h4>
                <ul className="space-y-1 text-gray-300 pl-6">
                  <li className="list-disc">
                    Polygon visualization for affected areas
                  </li>
                  <li className="list-disc">
                    Advanced filtering by category and severity
                  </li>
                  <li className="list-disc">
                    User authentication with Supabase
                  </li>
                  <li className="list-disc">
                    Customizable settings with persistent storage
                  </li>
                  <li className="list-disc">
                    Updated recent alerts panel with detailed information
                  </li>
                  <li className="list-disc">
                    Date range selector for historical data
                  </li>
                </ul>
              </div>
            </div>

            {/* Version 0.7.0 */}
            <div className="space-y-3 pt-4 border-t border-stone">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-stone/30 text-white text-xs font-bold rounded">
                  v0.7.0
                </span>
                <span className="text-xs text-gray-400">November 11, 2025</span>
              </div>
              <div className="space-y-2 text-sm">
                <h4 className="text-white font-semibold flex items-center gap-2">
                  <span className="text-blue-400">🔧</span> Improvements
                </h4>
                <ul className="space-y-1 text-gray-300 pl-6">
                  <li className="list-disc">
                    Enhanced map performance with better rendering
                  </li>
                  <li className="list-disc">
                    Improved data scraping from NDMA and PDMA sources
                  </li>
                  <li className="list-disc">Better mobile responsiveness</li>
                  <li className="list-disc">
                    Optimized database queries for faster loading
                  </li>
                </ul>
                <h4 className="text-white font-semibold flex items-center gap-2 pt-2">
                  <span className="text-green-400">🐛</span> Bug Fixes
                </h4>
                <ul className="space-y-1 text-gray-300 pl-6">
                  <li className="list-disc">
                    Fixed polygon rendering issues on map
                  </li>
                  <li className="list-disc">
                    Resolved timezone inconsistencies in alert timestamps
                  </li>
                  <li className="list-disc">
                    Fixed filter panel not resetting properly
                  </li>
                </ul>
              </div>
            </div>

            {/* Version 0.5.0 */}
            <div className="space-y-3 pt-4 border-t border-stone">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-stone/30 text-white text-xs font-bold rounded">
                  v0.5.0
                </span>
                <span className="text-xs text-gray-400">October 26, 2025</span>
              </div>
              <div className="space-y-2 text-sm">
                <h4 className="text-white font-semibold flex items-center gap-2">
                  <span className="text-caribbean-green">✨</span> New Features
                </h4>
                <ul className="space-y-1 text-gray-300 pl-6">
                  <li className="list-disc">
                    Initial map integration with Mapbox
                  </li>
                  <li className="list-disc">
                    Basic alert display and filtering
                  </li>
                  <li className="list-disc">Database schema design</li>
                  <li className="list-disc">
                    Backend scraper for NDMA documents
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
