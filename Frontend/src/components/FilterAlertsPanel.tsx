import React, { useState, useRef, useEffect } from "react";
import { format } from "date-fns";
import type {
  AlertSeverity,
  AlertCategory,
  AlertUrgency,
  AlertFromRPC,
} from "../types/database";
import type { DetailData } from "./DetailCard";

export interface FilterAlertsPanelProps {
  isVisible: boolean;
  onClose: () => void;
  height: number;
  onHeightChange: (height: number) => void;
  sidePanelWidth: number;
  // Data props
  alerts: DetailData[];
  loading: boolean;
  error: string | null;
  // Filter state props
  filters: {
    searchQuery: string;
    status: "active" | "all";
    severity?: AlertSeverity;
    urgency?: AlertUrgency;
    category?: AlertCategory;
    startDate?: Date;
    endDate?: Date;
    sortBy: "effective_from" | "posted_date" | "severity" | "urgency";
    sortOrder: "asc" | "desc";
    scope: "nationwide" | "local";
  };
  // Handlers
  onFilterChange: (key: string, value: any) => void;
  onClearSearch: () => void;
  onResetFilters: () => void;
  onRefresh: () => void;
  onAlertClick: (alert: DetailData) => void;
  onAlertHover?: (alert: DetailData) => void;
}

const CategoryIcon: React.FC<{ category?: string }> = ({ category }) => {
  const size = "w-5 h-5";
  const props = {
    className: `${size} text-white`,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round" as "round",
    strokeLinejoin: "round" as "round",
  };

  switch (category?.toLowerCase()) {
    case "geo":
      return (
        <svg {...props}>
          <path d="M21 12h-4l-3 9L7 3l-3 9H2" />
        </svg>
      );
    case "met":
      return (
        <svg {...props}>
          <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
          <path d="M16 14v6" />
          <path d="M8 14v6" />
          <path d="M12 16v6" />
        </svg>
      );
    case "safety":
      return (
        <svg {...props}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      );
    case "security":
      return (
        <svg {...props}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    case "rescue":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="4" />
          <line x1="4.93" y1="4.93" x2="9.17" y2="9.17" />
          <line x1="14.83" y1="14.83" x2="19.07" y2="19.07" />
          <line x1="14.83" y1="9.17" x2="19.07" y2="4.93" />
          <line x1="4.93" y1="19.07" x2="9.17" y2="14.83" />
        </svg>
      );
    case "fire":
      return (
        <svg {...props}>
          <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
        </svg>
      );
    case "health":
      return (
        <svg {...props}>
          <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.505 4.046 3 5.5L12 21l7-7Z" />
        </svg>
      );
    case "env":
      return (
        <svg {...props}>
          <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
          <path d="M2 21c0-3 1.85-5.36 5.08-6C10.9 14.51 12 13 13 12" />
        </svg>
      );
    case "transport":
      return (
        <svg {...props}>
          <rect x="1" y="3" width="15" height="13" />
          <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
          <circle cx="5.5" cy="18.5" r="2.5" />
          <circle cx="18.5" cy="18.5" r="2.5" />
        </svg>
      );
    case "infra":
      return (
        <svg {...props}>
          <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
          <path d="M9 22v-4h6v4" />
          <path d="M8 6h.01" />
          <path d="M16 6h.01" />
          <path d="M8 10h.01" />
          <path d="M16 10h.01" />
          <path d="M8 14h.01" />
          <path d="M16 14h.01" />
        </svg>
      );
    case "cbrne":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="10" />
          <path d="m11 12 1-1 3 3" />
          <path d="m7 12 1-1 3 3" />
          <path d="m15 12 1-1 3 3" />
        </svg>
      );
    default:
      return (
        <svg {...props}>
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
      );
  }
};

const CATEGORIES: AlertCategory[] = [
  "Geo",
  "Met",
  "Safety",
  "Security",
  "Rescue",
  "Fire",
  "Health",
  "Env",
  "Transport",
  "Infra",
  "CBRNE",
  "Other",
];

const CATEGORY_LABELS: Record<string, string> = {
  Geo: "Geological",
  Met: "Meteorological",
  Safety: "Safety",
  Security: "Security",
  Rescue: "Rescue",
  Fire: "Fire",
  Health: "Health",
  Env: "Environmental",
  Transport: "Transportation",
  Infra: "Infrastructure",
  CBRNE: "CBRNE",
  Other: "Other",
};

const SEVERITIES: AlertSeverity[] = [
  "Extreme",
  "Severe",
  "Moderate",
  "Minor",
  "Unknown",
];

const URGENCIES: AlertUrgency[] = [
  "Immediate",
  "Expected",
  "Future",
  "Past",
  "Unknown",
];

const DateButton: React.FC<{
  value?: Date;
  label: string;
  onChange: (date: Date | null) => void;
}> = ({ value, label, onChange }) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleContainerClick = () => {
    if (inputRef.current) {
      if ("showPicker" in HTMLInputElement.prototype) {
        try {
          inputRef.current.showPicker();
        } catch (e) {
          inputRef.current.focus();
        }
      } else {
        inputRef.current.focus();
      }
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    if (val) {
      const [year, month, day] = val.split("-").map(Number);
      onChange(new Date(year, month - 1, day));
    } else {
      onChange(null);
    }
  };

  const formattedDate = value ? format(value, "MM/dd/yy") : label;

  return (
    <div
      onClick={handleContainerClick}
      className="relative flex items-center justify-between bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-3 hover:bg-white/5 transition-all cursor-pointer h-[34px] flex-1 group"
    >
      <span className={value ? "text-white" : "text-gray-500"}>
        {formattedDate}
      </span>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-gray-500 group-hover:text-caribbean-green transition-colors"
      >
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="16" y1="2" x2="16" y2="6"></line>
        <line x1="8" y1="2" x2="8" y2="6"></line>
        <line x1="3" y1="10" x2="21" y2="10"></line>
      </svg>
      <input
        ref={inputRef}
        type="date"
        value={value ? format(value, "yyyy-MM-dd") : ""}
        onChange={handleInputChange}
        className="absolute inset-0 opacity-0 pointer-events-none"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
};

export const FilterAlertsPanel: React.FC<FilterAlertsPanelProps> = ({
  isVisible,
  onClose,
  height,
  onHeightChange,
  sidePanelWidth,
  alerts,
  loading,
  error,
  filters,
  onFilterChange,
  onClearSearch,
  onResetFilters,
  onRefresh,
  onAlertClick,
  onAlertHover,
}) => {
  const [showFilters, setShowFilters] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 640);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const newHeight = window.innerHeight - moveEvent.clientY - 16; // 16 for bottom-4
      if (newHeight > 100 && newHeight < window.innerHeight - 100) {
        onHeightChange(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    setIsResizing(true);

    const handleTouchMove = (moveEvent: TouchEvent) => {
      const touch = moveEvent.touches[0];
      const newHeight = window.innerHeight - touch.clientY - 16;
      if (newHeight > 100 && newHeight < window.innerHeight - 100) {
        onHeightChange(newHeight);
      }
    };

    const handleTouchEnd = () => {
      setIsResizing(false);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleTouchEnd);
    };

    window.addEventListener("touchmove", handleTouchMove);
    window.addEventListener("touchend", handleTouchEnd);
  };

  const getSeverityColorRGBA = (
    severity?: string,
    alpha: number = 1
  ): string => {
    switch (severity?.toLowerCase()) {
      case "extreme":
        return `rgba(180, 0, 255, ${alpha})`;
      case "severe":
        return `rgba(220, 20, 60, ${alpha})`;
      case "moderate":
        return `rgba(255, 140, 0, ${alpha})`;
      case "minor":
        return `rgba(255, 215, 0, ${alpha})`;
      default:
        return `rgba(30, 144, 255, ${alpha})`;
    }
  };

  const activeFilterCount = [
    filters.category,
    filters.severity,
    filters.urgency,
    filters.startDate,
    filters.endDate,
    filters.searchQuery,
    filters.status !== "active" ? "status" : null,
    filters.sortBy !== "posted_date" ? "sort" : null,
    filters.sortOrder !== "desc" ? "order" : null,
    filters.scope !== "nationwide" ? "scope" : null,
  ].filter(Boolean).length;

  return (
    <div
      className={`fixed 
        bottom-4 left-4 right-4 
        sm:left-22
        frosted-glass transform transition-all duration-300 ease-in-out z-40 flex flex-col
        ${
          isVisible ? "translate-y-0 opacity-100" : "translate-y-full opacity-0"
        }
        ${isResizing ? "transition-none" : ""}
      `}
      style={{
        height: `${height}px`,
        right: isMobile ? "1rem" : `calc(${sidePanelWidth}px + 2rem)`, // On mobile: 1rem (right-4), Desktop: sidePanelWidth + 32px
      }}
    >
      {/* Resize Handle */}
      <div
        className="absolute top-0 left-0 right-0 h-8 cursor-ns-resize z-50 flex items-center justify-center -mt-4 touch-none group"
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
      >
        {/* Visual Grabber */}
        <div className="w-16 h-1.5 bg-white/20 rounded-full opacity-100 sm:opacity-0 group-hover:opacity-100 transition-opacity mx-auto mt-4" />
      </div>

      <div className="p-4 border-b border-white/10 bg-rich-black/30 backdrop-blur-md">
        {/* Header Row: Title, Global Actions */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <h3 className="text-xl font-semibold text-white">Alerts</h3>
            <span className="text-xs text-gray-400 bg-white/10 px-2 py-0.5 rounded-full">
              {alerts.length}
            </span>
            {loading && (
              <div className="animate-spin h-4 w-4 border-2 border-caribbean-green border-t-transparent rounded-full"></div>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {activeFilterCount > 0 && (
              <button
                onClick={onResetFilters}
                className="p-1.5 text-[10px] uppercase tracking-wider font-semibold text-gray-500 hover:text-red-400 transition-colors flex items-center gap-1 cursor-pointer"
                title="Reset all filters"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                  <path d="M3 3v5h5" />
                </svg>
                Reset
              </button>
            )}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 flex items-center gap-1.5 rounded-md transition-colors text-xs font-medium border border-white/10 cursor-pointer ${
                showFilters
                  ? "bg-caribbean-green/20 text-caribbean-green border-caribbean-green/30"
                  : "text-gray-400 hover:text-white hover:bg-white/5"
              }`}
              title="Toggle filter options"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
              </svg>
              <span>Filters</span>
              {activeFilterCount > 0 && (
                <span className="bg-caribbean-green text-rich-black text-[10px] px-1 rounded-full min-w-[14px] flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <button
              onClick={onRefresh}
              disabled={loading}
              className="p-2 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors cursor-pointer"
              title="Refresh"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3" />
              </svg>
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors cursor-pointer"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>

        {/* Filter Layout */}
        <div className="flex flex-col gap-3">
          {/* Row 1: Searchbar */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search titles, descriptions, places..."
              value={filters.searchQuery}
              onChange={(e) => onFilterChange("searchQuery", e.target.value)}
              className="w-full bg-white/10 text-white text-sm border border-white/10 rounded-none py-2 pl-9 pr-8 focus:outline-none focus:border-caribbean-green/50 placeholder-gray-500"
            />
            <svg
              className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-500"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            {filters.searchQuery && (
              <button
                onClick={onClearSearch}
                className="absolute right-2 top-2.5 p-0.5 hover:text-white text-gray-500 cursor-pointer"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            )}
          </div>

          <div
            className={`flex flex-col gap-3 transition-all duration-300 overflow-hidden ${
              showFilters
                ? "max-h-[500px] opacity-100 mt-1"
                : "max-h-0 opacity-0"
            }`}
          >
            {/* Row 2: Date Range, Status, Sort */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-500 uppercase tracking-widest font-medium">
                  Date Range
                </label>
                <div className="flex gap-2">
                  <DateButton
                    value={filters.startDate}
                    label="From"
                    onChange={(date) => onFilterChange("startDate", date)}
                  />
                  <DateButton
                    value={filters.endDate}
                    label="Until"
                    onChange={(date) => onFilterChange("endDate", date)}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-500 uppercase tracking-widest font-medium">
                  Status
                </label>
                <select
                  value={filters.status}
                  onChange={(e) => onFilterChange("status", e.target.value)}
                  className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-3 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all cursor-pointer"
                >
                  <option value="active" className="bg-rich-black text-white">
                    Active
                  </option>
                  <option value="all" className="bg-rich-black text-white">
                    All
                  </option>
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-500 uppercase tracking-widest font-medium">
                  Sort
                </label>
                <div className="flex gap-2">
                  <select
                    value={filters.sortBy}
                    onChange={(e) => onFilterChange("sortBy", e.target.value)}
                    className="flex-1 bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-3 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all cursor-pointer"
                  >
                    <option
                      value="posted_date"
                      className="bg-rich-black text-white"
                    >
                      Posted Date
                    </option>
                    <option
                      value="effective_from"
                      className="bg-rich-black text-white"
                    >
                      Event Date
                    </option>
                    <option
                      value="severity"
                      className="bg-rich-black text-white"
                    >
                      Severity
                    </option>
                    <option
                      value="urgency"
                      className="bg-rich-black text-white"
                    >
                      Urgency
                    </option>
                  </select>
                  <button
                    onClick={() =>
                      onFilterChange(
                        "sortOrder",
                        filters.sortOrder === "asc" ? "desc" : "asc"
                      )
                    }
                    className="p-1.5 bg-rich-black/50 border border-white/10 rounded-md text-gray-400 hover:text-white hover:border-white/30 transition-all flex items-center justify-center min-w-[34px] cursor-pointer"
                    title={
                      filters.sortOrder === "asc"
                        ? "Sort Ascending"
                        : "Sort Descending"
                    }
                  >
                    {filters.sortOrder === "asc" ? (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="m18 15-6-6-6 6" />
                      </svg>
                    ) : (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Row 3: Category, Severity, Scope */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-500 uppercase tracking-widest font-medium">
                  Category
                </label>
                <select
                  value={filters.category || ""}
                  onChange={(e) =>
                    onFilterChange("category", e.target.value || undefined)
                  }
                  className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-3 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all cursor-pointer"
                >
                  <option value="" className="bg-rich-black text-white">
                    All Categories
                  </option>
                  {CATEGORIES.map((c) => (
                    <option
                      key={c}
                      value={c}
                      className="bg-rich-black text-white"
                    >
                      {CATEGORY_LABELS[c] || c}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-500 uppercase tracking-widest font-medium">
                  Severity
                </label>
                <select
                  value={filters.severity || ""}
                  onChange={(e) =>
                    onFilterChange("severity", e.target.value || undefined)
                  }
                  className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-3 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all cursor-pointer"
                >
                  <option value="" className="bg-rich-black text-white">
                    All Severities
                  </option>
                  {SEVERITIES.map((s) => (
                    <option
                      key={s}
                      value={s}
                      className="bg-rich-black text-white"
                    >
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-500 uppercase tracking-widest font-medium">
                  Scope
                </label>
                <select
                  value={filters.scope}
                  onChange={(e) => onFilterChange("scope", e.target.value)}
                  className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-3 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all cursor-pointer"
                >
                  <option
                    value="nationwide"
                    className="bg-rich-black text-white"
                  >
                    Nationwide
                  </option>
                  <option value="local" className="bg-rich-black text-white">
                    Local
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Alert List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar bg-black/40">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <p className="text-red-400 mb-2">Error loading alerts</p>
            <p className="text-sm text-gray-400">{error}</p>
          </div>
        ) : alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4 text-gray-500">
            {loading ? "Loading..." : "No alerts found matching your filters."}
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => onAlertClick(alert)}
                onMouseEnter={() => onAlertHover?.(alert)}
                className="p-3.5 hover:bg-white/10 cursor-pointer transition-all duration-200 group border-l-4 border-transparent hover:border-caribbean-green relative"
              >
                <div className="flex items-center gap-4">
                  {/* Left Side: Android-style Notification Icon */}
                  <div
                    className="flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center shadow-lg ring-1 ring-white/10 transition-transform duration-200 group-hover:scale-105"
                    style={{
                      backgroundColor: getSeverityColorRGBA(
                        alert.severity,
                        0.25
                      ),
                    }}
                  >
                    <CategoryIcon category={alert.category} />
                  </div>

                  {/* Right Side: Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start gap-4">
                      <h4 className="text-base font-bold text-white truncate group-hover:text-caribbean-green transition-colors leading-tight">
                        {alert.title}
                      </h4>
                      <span className="text-sm text-gray-500 font-medium whitespace-nowrap pt-0.5 transition-colors group-hover:text-gray-400">
                        {(() => {
                          const d = alert.postedDate || alert.date;
                          if (!d) return "";
                          const day = String(d.getDate()).padStart(2, "0");
                          const month = String(d.getMonth() + 1).padStart(
                            2,
                            "0"
                          );
                          const year = String(d.getFullYear()).slice(-2);
                          return `${day}/${month}/${year}`;
                        })()}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 mt-1 line-clamp-1 leading-snug font-medium opacity-80 group-hover:opacity-100 transition-opacity">
                      {alert.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}

            {/* Simple footer since we have page_size=100 default and rpc handles pagination but UI doesn't requested explicit pagination controls yet. 
                 If the user scrolls we might want to load more, but for now just showing what we have. 
             */}
            <div className="p-3 text-center text-[10px] uppercase tracking-widest font-semibold text-gray-500 border-t border-white/5 bg-black/20">
              Showing {alerts.length} alerts
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
