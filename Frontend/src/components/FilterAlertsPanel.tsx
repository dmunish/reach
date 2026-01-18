import React, { useState } from "react";
import { DateRangeSelector } from "./DateRangeSelector";
import type { 
  AlertSeverity, 
  AlertCategory, 
  AlertUrgency,
  AlertFromRPC
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
    status: 'active' | 'archived' | 'all';
    severity?: AlertSeverity;
    urgency?: AlertUrgency;
    category?: AlertCategory;
    startDate?: Date;
    endDate?: Date;
    sortBy: 'effective_from' | 'severity' | 'urgency';
    sortOrder: 'asc' | 'desc';
  };
  // Handlers
  onFilterChange: (key: string, value: any) => void;
  onClearSearch: () => void;
  onResetFilters: () => void;
  onRefresh: () => void;
  onAlertClick: (alert: DetailData) => void;
  onAlertHover?: (alert: DetailData) => void;
}

const CATEGORIES: AlertCategory[] = [
  "Geo", "Met", "Safety", "Security", "Rescue", "Fire", 
  "Health", "Env", "Transport", "Infra", "CBRNE", "Other"
];

const SEVERITIES: AlertSeverity[] = [
  "Extreme", "Severe", "Moderate", "Minor", "Unknown"
];

const URGENCIES: AlertUrgency[] = [
  "Immediate", "Expected", "Future", "Past", "Unknown"
];

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
  onAlertHover
}) => {
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [isResizing, setIsResizing] = useState(false);

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

  const getSeverityColor = (severity?: string): string => {
    switch (severity?.toLowerCase()) {
      case "extreme": return "text-red-400";
      case "severe": return "text-orange-400";
      case "moderate": return "text-yellow-400";
      case "minor": return "text-green-400";
      default: return "text-gray-400";
    }
  };

  const activeFilterCount = [
    filters.category, 
    filters.severity, 
    filters.urgency, 
    filters.startDate,
    filters.endDate,
    filters.searchQuery,
    filters.status !== 'active' ? 'status' : null,
    filters.sortBy !== 'effective_from' ? 'sort' : null,
    filters.sortOrder !== 'desc' ? 'order' : null
  ].filter(Boolean).length;

  return (
    <div
      className={`fixed 
        bottom-4 left-4 right-4 
        sm:left-22
        frosted-glass transform transition-all duration-300 ease-in-out z-40 flex flex-col
        ${isVisible ? "translate-y-0 opacity-100" : "translate-y-full opacity-0"}
        ${isResizing ? "transition-none" : ""}
      `}
      style={{
        height: `${height}px`,
        right: `calc(${sidePanelWidth}px + 2rem)`, // sidePanelWidth + 32px (margins)
      }}
    >
      {/* Resize Handle */}
      <div 
        className="absolute top-0 left-0 right-0 h-1 cursor-ns-resize hover:bg-caribbean-green/50 transition-colors z-50"
        onMouseDown={handleMouseDown}
      />

      <div className="p-4 border-b border-white/10 bg-rich-black/30 backdrop-blur-md">
        {/* Top Bar: Title, Search, Status, Sort, Actions */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-medium text-white">Alerts</h3>
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
                  className="p-1.5 text-[10px] uppercase tracking-wider font-semibold text-gray-500 hover:text-red-400 transition-colors flex items-center gap-1"
                  title="Reset all filters"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                  Reset
                </button>
              )}
               <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className={`p-1.5 rounded-md transition-colors text-xs flex items-center gap-1 ${showAdvanced || activeFilterCount > 0 ? 'bg-caribbean-green/20 text-caribbean-green' : 'text-gray-400 hover:text-white'}`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
                Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
              </button>
              <div className="h-4 w-[1px] bg-white/10 mx-1"></div>
              <button
                onClick={onRefresh}
                disabled={loading}
                className="p-1.5 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors"
                title="Refresh"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>
              </button>
              <button
                onClick={onClose}
                className="p-1.5 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>
          </div>

          <div className="flex gap-2 items-center flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <input
                type="text"
                placeholder="Search alerts..."
                value={filters.searchQuery}
                onChange={(e) => onFilterChange("searchQuery", e.target.value)}
                className="w-full bg-rich-black/50 text-white text-sm border border-white/10 rounded-md py-1.5 pl-8 pr-8 focus:outline-none focus:border-caribbean-green/50 placeholder-gray-500"
              />
              <svg 
                className="absolute left-2.5 top-2 w-3.5 h-3.5 text-gray-500"
                xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              {filters.searchQuery && (
                <button
                  onClick={onClearSearch}
                  className="absolute right-2 top-2 p-0.5 hover:text-white text-gray-500"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              )}
            </div>

            <select 
              value={filters.status}
              onChange={(e) => onFilterChange("status", e.target.value)}
              className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-2 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all"
            >
              <option value="active" className="bg-rich-black text-white">Active</option>
              <option value="archived" className="bg-rich-black text-white">Archived</option>
              <option value="all" className="bg-rich-black text-white">All Status</option>
            </select>

             <select 
              value={filters.sortBy}
              onChange={(e) => onFilterChange("sortBy", e.target.value)}
              className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1.5 px-2 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all"
            >
              <option value="effective_from" className="bg-rich-black text-white">Date</option>
              <option value="severity" className="bg-rich-black text-white">Severity</option>
              <option value="urgency" className="bg-rich-black text-white">Urgency</option>
            </select>

            <button
              onClick={() => onFilterChange("sortOrder", filters.sortOrder === 'asc' ? 'desc' : 'asc')}
              className="p-1.5 bg-rich-black/50 border border-white/10 rounded-md text-gray-400 hover:text-white hover:border-white/30"
              title={filters.sortOrder === 'asc' ? "Sort Ascending" : "Sort Descending"}
            >
              {filters.sortOrder === 'asc' ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>
              )}
            </button>
          </div>
        </div>

        {/* Advanced Filters (Collapsible) */}
        <div className={`
          overflow-hidden transition-all duration-300 ease-in-out border-t border-white/5 mt-3
          ${showAdvanced ? "max-h-40 opacity-100 pt-3 pb-1" : "max-h-0 opacity-0"}
        `}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
             <div className="flex flex-col gap-1">
              <label className="text-[10px] text-gray-400 uppercase tracking-wider">Date Range</label>
              <DateRangeSelector
                initialStartDate={filters.startDate}
                initialEndDate={filters.endDate}
                onDateRangeChange={(start, end) => {
                  onFilterChange("startDate", start);
                  onFilterChange("endDate", end);
                }}
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-gray-400 uppercase tracking-wider">Category</label>
              <select 
                value={filters.category || ""}
                onChange={(e) => onFilterChange("category", e.target.value || undefined)}
                className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1 px-2 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all"
              >
                <option value="" className="bg-rich-black text-white">All Categories</option>
                {CATEGORIES.map(c => <option key={c} value={c} className="bg-rich-black text-white">{c}</option>)}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-gray-400 uppercase tracking-wider">Severity</label>
              <select 
                value={filters.severity || ""}
                onChange={(e) => onFilterChange("severity", e.target.value || undefined)}
                className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1 px-2 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all"
              >
                <option value="" className="bg-rich-black text-white">All Severities</option>
                {SEVERITIES.map(s => <option key={s} value={s} className="bg-rich-black text-white">{s}</option>)}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-gray-400 uppercase tracking-wider">Urgency</label>
              <select 
                value={filters.urgency || ""}
                onChange={(e) => onFilterChange("urgency", e.target.value || undefined)}
                className="bg-rich-black/50 backdrop-blur-md text-white text-xs border border-white/10 rounded-md py-1 px-2 focus:outline-none focus:border-caribbean-green/50 hover:bg-white/5 transition-all"
              >
                <option value="" className="bg-rich-black text-white">All Urgencies</option>
                {URGENCIES.map(u => <option key={u} value={u} className="bg-rich-black text-white">{u}</option>)}
              </select>
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
          <div className="divide-y divide-white/10">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => onAlertClick(alert)}
                onMouseEnter={() => onAlertHover?.(alert)}
                className="p-3 hover:bg-white/5 cursor-pointer transition-colors group border-l-2 border-transparent hover:border-caribbean-green"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/5 uppercase ${getSeverityColor(alert.severity)}`}>
                        {alert.severity || "Unknown"}
                      </span>
                      <span className="text-[10px] text-gray-400">
                        {alert.date.toLocaleDateString()}
                      </span>
                    </div>
                    <h4 className="text-sm font-medium text-white truncate group-hover:text-caribbean-green transition-colors">
                      {alert.title}
                    </h4>
                    <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">
                      {alert.description}
                    </p>
                  </div>
                  {/* Arrow Icon */}
                  <svg 
                    className="w-4 h-4 text-gray-600 group-hover:text-white transition-colors" 
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            ))}
            
             {/* Simple footer since we have page_size=100 default and rpc handles pagination but UI doesn't requested explicit pagination controls yet. 
                 If the user scrolls we might want to load more, but for now just showing what we have. 
             */}
             <div className="p-2 text-center text-xs text-gray-500 border-t border-white/5">
                Showing {alerts.length} alerts
             </div>
          </div>
        )}
      </div>
    </div>
  );
};
