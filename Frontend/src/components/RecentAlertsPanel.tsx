import React, { useState, useMemo } from "react";
import type { DetailData } from "./DetailCard";

export interface RecentAlertsPanelProps {
  isVisible: boolean;
  onClose: () => void;
  alerts: DetailData[];
  loading: boolean;
  error: string | null;
  onAlertClick: (alert: DetailData) => void;
  onRefresh: () => void;
}

export const RecentAlertsPanel: React.FC<RecentAlertsPanelProps> = ({
  isVisible,
  onClose,
  alerts,
  loading,
  error,
  onAlertClick,
  onRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const getSeverityColor = (severity?: string): string => {
    switch (severity?.toLowerCase()) {
      case "extreme":
        return "text-red-400";
      case "severe":
        return "text-orange-400";
      case "moderate":
        return "text-yellow-400";
      case "minor":
        return "text-green-400";
      default:
        return "text-gray-400";
    }
  };

  const getSeverityNumber = (severity?: string): number => {
    switch (severity?.toLowerCase()) {
      case "extreme":
        return 5;
      case "severe":
        return 4;
      case "moderate":
        return 3;
      case "minor":
        return 2;
      default:
        return 1;
    }
  };

  // Filter alerts based on search term
  const filteredAlerts = useMemo(() => {
    if (!searchTerm.trim()) {
      return alerts;
    }
    return alerts.filter((alert) =>
      alert.location?.toLowerCase().includes(searchTerm.toLowerCase().trim())
    );
  }, [alerts, searchTerm]);

  const handleRefresh = () => {
    setSearchTerm(""); // Clear search when refreshing
    onRefresh();
  };

  return (
    <div
      className={`fixed 
        bottom-4 left-4 right-4 h-80 
        sm:left-22 sm:right-4
        md:right-[416px]
        lg:right-[416px]
        frosted-glass transform transition-all duration-300 ease-in-out z-40 
        ${
          isVisible ? "translate-y-0 opacity-100" : "translate-y-full opacity-0"
        }
      `}
    >
      <div className="p-4 h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-medium text-white">Recent Alerts</h3>
            {loading && (
              <div className="animate-spin h-4 w-4 border-2 border-caribbean-green border-t-transparent rounded-full"></div>
            )}
          </div>
          <div className="flex items-center space-x-1">
            <span className="text-xs text-gray-400">
              {searchTerm
                ? `${filteredAlerts.length}/${alerts.length}`
                : `Count: ${alerts.length}`}
            </span>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="p-1 hover:bg-bangladesh-green rounded-full transition-colors ml-2 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh alerts"
            >
              <svg
                className={`w-4 h-4 text-gray-400 ${
                  loading ? "animate-spin" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
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
        </div>

        {/* Vertical line separator */}
        <div className="w-full h-px bg-stone mb-4"></div>

        {/* Search Bar */}
        <div className="mb-3">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg
                className="h-4 w-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input w-full pl-10 pr-4 py-1.5 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-mountain-meadow focus:ring-opacity-50"
              placeholder="Search by location..."
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                <svg
                  className="h-4 w-4 text-gray-400 hover:text-white transition-colors"
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
            )}
          </div>
        </div>

        {/* Table Header */}
        <div className="grid grid-cols-12 gap-2 mb-3 px-2 py-1">
          <div className="col-span-3 text-xs text-gray-400 font-medium">
            Location
          </div>
          <div className="col-span-1 text-xs text-gray-400 font-medium text-center">
            Level
          </div>
          <div className="col-span-5 text-xs text-gray-400 font-medium">
            Description
          </div>
          <div className="col-span-3 text-xs text-gray-400 font-medium text-right">
            Time
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-4 p-3 bg-red-900 bg-opacity-50 border border-red-700 rounded-lg">
            <p className="text-sm text-red-200">
              Error loading alerts: {error}
            </p>
          </div>
        )}

        {/* Alerts List */}
        <div className="flex-1 overflow-y-auto dark-scrollbar">
          {filteredAlerts.length === 0 && !loading && !error ? (
            <div className="text-center text-gray-400 py-8">
              <p className="text-sm">
                {searchTerm
                  ? `No alerts found for "${searchTerm}"`
                  : "No alerts found"}
              </p>
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm("")}
                  className="text-xs text-bangladesh-green hover:text-mountain-meadow mt-2 underline"
                >
                  Clear search
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              {filteredAlerts.map((alert, index) => (
                <div
                  key={alert.id || index}
                  onClick={() => onAlertClick(alert)}
                  className={`grid grid-cols-12 gap-2 px-2 py-2 cursor-pointer transition-colors hover:bg-dark-green hover:bg-opacity-60 ${
                    index % 2 === 1 ? "bg-rich-black bg-opacity-30" : ""
                  }`}
                >
                  {/* Location */}
                  <div className="col-span-3 text-xs text-gray-300">
                    <div className="line-clamp-2">
                      {alert.location || "Unknown Location"}
                    </div>
                  </div>

                  {/* Severity Level */}
                  <div className="col-span-1 text-center">
                    <span
                      className={`text-sm font-bold ${getSeverityColor(
                        alert.severity
                      )}`}
                    >
                      {getSeverityNumber(alert.severity)}
                    </span>
                  </div>

                  {/* Description */}
                  <div className="col-span-5 text-xs text-gray-300">
                    <div className="line-clamp-2">
                      {alert.description.length > 100
                        ? `${alert.description.substring(0, 100)}...`
                        : alert.description}
                    </div>
                  </div>

                  {/* Time */}
                  <div className="col-span-3 text-xs text-gray-400 text-right">
                    {alert.date
                      ? new Date(alert.date).toLocaleString("en-US", {
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false,
                        })
                      : "--"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
