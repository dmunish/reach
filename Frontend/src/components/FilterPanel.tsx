import React, { useState, useEffect } from "react";
import { DateRangeSelector } from "./DateRangeSelector";
import type { AlertSeverity, AlertCategory } from "../types/database";

export interface FilterPanelProps {
  isVisible: boolean;
  onClose: () => void;
  onDateRangeChange: (startDate: Date | null, endDate: Date | null) => void;
  onFiltersChange?: (filters: {
    severities: AlertSeverity[];
    categories: AlertCategory[];
  }) => void;
  defaultSeverity?: string;
  defaultTimeRange?: string;
  isLoading?: boolean;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  isVisible,
  onClose,
  onDateRangeChange,
  onFiltersChange,
  defaultSeverity = "all",
  defaultTimeRange = "all",
  isLoading = false,
}) => {
  // Helper function to get severities based on minimum severity setting
  const getSeveritiesFromDefault = (minSeverity: string): AlertSeverity[] => {
    const allSeverities: AlertSeverity[] = [
      "Extreme",
      "Severe",
      "Moderate",
      "Minor",
      "Unknown",
    ];

    if (minSeverity === "all" || !minSeverity) {
      return allSeverities;
    }

    const severityOrder: Record<string, number> = {
      unknown: -1,
      minor: 0,
      moderate: 1,
      severe: 2,
      extreme: 3,
    };

    const minLevel = severityOrder[minSeverity.toLowerCase()];
    if (minLevel === undefined) return allSeverities;

    return allSeverities.filter((sev) => {
      const level = severityOrder[sev.toLowerCase()];
      return level >= minLevel;
    });
  };

  const [selectedSeverities, setSelectedSeverities] = useState<AlertSeverity[]>(
    ["Extreme", "Severe", "Moderate", "Minor", "Unknown"]
  );

  const [selectedCategories, setSelectedCategories] = useState<AlertCategory[]>(
    [
      "Met",
      "Geo",
      "Security",
      "Health",
      "Env",
      "Infra",
      "Safety",
      "Rescue",
      "Fire",
      "Transport",
      "CBRNE",
      "Other",
    ]
  );

  const [initialDateRange, setInitialDateRange] = useState<{
    start: Date | null;
    end: Date | null;
  }>({ start: null, end: null });

  const [isInitialized, setIsInitialized] = useState(false);

  // Initialize severities and date range together to avoid multiple refetches
  useEffect(() => {
    if (isLoading) return;

    const newSeverities = getSeveritiesFromDefault(defaultSeverity);
    setSelectedSeverities(newSeverities);

    const now = new Date();
    let startDate: Date | null = null;
    let endDate: Date | null = null;

    switch (defaultTimeRange) {
      case "24h":
        startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        endDate = now;
        break;
      case "7d":
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        endDate = now;
        break;
      case "30d":
        startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        endDate = now;
        break;
      case "90d":
        startDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
        endDate = now;
        break;
      case "all":
      default:
        startDate = null;
        endDate = null;
        break;
    }

    setInitialDateRange({ start: startDate, end: endDate });

    // Only trigger callbacks after state updates are done
    setTimeout(() => {
      onDateRangeChange(startDate, endDate);
      onFiltersChange?.({
        severities: newSeverities,
        categories: selectedCategories,
      });
      setIsInitialized(true);
    }, 0);
  }, [defaultSeverity, defaultTimeRange, isLoading]);
  useEffect(() => {
    if (isInitialized && onFiltersChange) {
      onFiltersChange({
        severities: selectedSeverities,
        categories: selectedCategories,
      });
    }
  }, [selectedSeverities, selectedCategories, onFiltersChange, isInitialized]);

  const handleSeverityToggle = (severity: AlertSeverity) => {
    console.log("FilterPanel: Toggling severity:", severity);
    setSelectedSeverities((prev) => {
      const newSeverities = prev.includes(severity)
        ? prev.filter((s) => s !== severity)
        : [...prev, severity];
      console.log("FilterPanel: New severities:", newSeverities);
      return newSeverities;
    });
  };

  const handleCategoryToggle = (category: AlertCategory) => {
    console.log("FilterPanel: Toggling category:", category);
    setSelectedCategories((prev) => {
      const newCategories = prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category];
      console.log("FilterPanel: New categories:", newCategories);
      return newCategories;
    });
  };

  const handleApplyFilters = () => {
    onFiltersChange?.({
      severities: selectedSeverities,
      categories: selectedCategories,
    });
  };

  const handleResetAll = () => {
    const allCategories: AlertCategory[] = [
      "Met",
      "Geo",
      "Security",
      "Health",
      "Env",
      "Infra",
      "Safety",
      "Rescue",
      "Fire",
      "Transport",
      "CBRNE",
      "Other",
    ];

    // Reset to user's default severity settings
    const resetSeverities = getSeveritiesFromDefault(defaultSeverity);

    setSelectedSeverities(resetSeverities);
    setSelectedCategories(allCategories);

    // Reset to user's default time range
    if (initialDateRange.start && initialDateRange.end) {
      onDateRangeChange(initialDateRange.start, initialDateRange.end);
    } else {
      onDateRangeChange(null, null);
    }

    onFiltersChange?.({
      severities: resetSeverities,
      categories: allCategories,
    });
  };
  return (
    <div
      className={`fixed 
        top-20 right-4 left-4 
        h-[calc(50vh-3rem)]
        sm:top-4 sm:left-auto sm:w-96 sm:max-w-96 sm:h-auto
        md:bottom-[352px]
        sm:max-h-[calc(100vh-352px-2rem)]
        frosted-glass transform transition-all duration-300 ease-in-out z-40 overflow-hidden 
        ${
          isVisible
            ? "translate-y-0 opacity-100"
            : "-translate-y-full opacity-0"
        }
      `}
    >
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 pb-3">
          <div className="flex items-center gap-2">
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
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.707A1 1 0 013 7V4z"
              />
            </svg>
            <h3 className="text-base font-medium text-white">
              Filters & Search
            </h3>
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

        {/* Vertical line separator */}
        <div className="w-full h-px bg-stone mx-4"></div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto dark-scrollbar p-4 space-y-4">
          {/* Date Range Section */}
          <div>
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
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <span className="text-sm text-gray-400 font-medium">
                Date Range
              </span>
            </div>
            <DateRangeSelector
              onDateRangeChange={onDateRangeChange}
              initialStartDate={initialDateRange.start || undefined}
              initialEndDate={initialDateRange.end || undefined}
              className="!p-0 !shadow-none !bg-transparent"
            />
          </div>

          {/* Severity Filters */}
          <div>
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
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 13.5c-.77.833.192 2.5 1.732 2.5z"
                />
              </svg>
              <span className="text-sm text-gray-400 font-medium">
                Severity Levels
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                {
                  name: "Extreme" as AlertSeverity,
                  level: 5,
                  color: "text-red-400",
                },
                {
                  name: "Severe" as AlertSeverity,
                  level: 4,
                  color: "text-orange-400",
                },
                {
                  name: "Moderate" as AlertSeverity,
                  level: 3,
                  color: "text-yellow-400",
                },
                {
                  name: "Minor" as AlertSeverity,
                  level: 2,
                  color: "text-green-400",
                },
                {
                  name: "Unknown" as AlertSeverity,
                  level: 1,
                  color: "text-gray-400",
                },
              ].map((severity) => (
                <label
                  key={severity.name}
                  className="flex items-center gap-2 p-2 rounded-lg hover:bg-rich-black hover:bg-opacity-30 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="filter-checkbox"
                    checked={selectedSeverities.includes(severity.name)}
                    onChange={() => handleSeverityToggle(severity.name)}
                  />
                  <span className={`text-sm font-bold ${severity.color}`}>
                    {severity.level}
                  </span>
                  <span className="text-xs text-gray-300">{severity.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Category Filters */}
          <div>
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
                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
              <span className="text-sm text-gray-400 font-medium">
                Categories
              </span>
            </div>
            <div className="space-y-1">
              {[
                { display: "Weather", value: "Met" as AlertCategory },
                { display: "Geological", value: "Geo" as AlertCategory },
                { display: "Security", value: "Security" as AlertCategory },
                { display: "Health", value: "Health" as AlertCategory },
                { display: "Environmental", value: "Env" as AlertCategory },
                { display: "Infrastructure", value: "Infra" as AlertCategory },
                { display: "Safety", value: "Safety" as AlertCategory },
                { display: "Rescue", value: "Rescue" as AlertCategory },
                { display: "Fire", value: "Fire" as AlertCategory },
                { display: "Transport", value: "Transport" as AlertCategory },
                { display: "CBRNE", value: "CBRNE" as AlertCategory },
                { display: "Other", value: "Other" as AlertCategory },
              ].map((category) => (
                <label
                  key={category.value}
                  className="flex items-center gap-2 p-2 rounded-lg hover:bg-rich-black hover:bg-opacity-30 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="filter-checkbox"
                    checked={selectedCategories.includes(category.value)}
                    onChange={() => handleCategoryToggle(category.value)}
                  />
                  <span className="text-xs text-gray-300">
                    {category.display}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div>
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
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              <span className="text-sm text-gray-400 font-medium">
                Quick Actions
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleApplyFilters}
                className="flex-1 px-3 py-1.5 text-xs bg-bangladesh-green hover:bg-mountain-meadow text-white hover:text-dark-green rounded-md transition-colors font-medium"
              >
                Apply Filters
              </button>
              <button
                onClick={handleResetAll}
                className="flex-1 px-3 py-1.5 text-xs border border-stone text-stone hover:bg-stone hover:text-dark-green rounded-md transition-colors font-medium"
              >
                Reset All
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
