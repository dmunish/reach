import React from "react";

export interface NavbarProps {
  onToggleFilter: () => void;
  onToggleAlerts: () => void;
  onToggleDetails: () => void;
  onToggleSettings: () => void;
  isFilterOpen: boolean;
  isAlertsOpen: boolean;
  isDetailsOpen: boolean;
  isSettingsOpen: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  onToggleFilter,
  onToggleAlerts,
  onToggleDetails,
  onToggleSettings,
  isFilterOpen,
  isAlertsOpen,
  isDetailsOpen,
  isSettingsOpen,
}) => {
  return (
    <div
      className="fixed left-0 top-0 
      w-full h-16 
      sm:w-18 sm:h-full 
      bg-rich-black z-50 
      flex flex-row sm:flex-col items-center justify-center sm:justify-start 
      px-4 py-2 sm:px-0 sm:py-6
    "
    >
      {/* REACH Logo - Responsive */}
      <div className="mr-auto sm:mr-0 sm:mb-12">
        <div
          className="text-white font-bold text-lg tracking-wider opacity-60
          sm:transform sm:rotate-180
          hidden sm:block"
          style={{
            writingMode: "vertical-rl",
            textOrientation: "mixed",
          }}
        >
          REACH
        </div>
        <div className="text-white font-bold text-lg tracking-wider opacity-60 sm:hidden">
          REACH
        </div>
      </div>

      {/* Navigation Buttons - Responsive */}
      <div className="flex flex-row space-x-4 sm:space-x-0 sm:space-y-6 sm:flex-col sm:flex-1 sm:justify-center">
        {/* Filter Panel Toggle */}
        <button
          onClick={onToggleFilter}
          className={`nav-button w-12 h-12 flex items-center justify-center transition-all duration-200 ${
            isFilterOpen
              ? "nav-button-active text-white"
              : "text-white opacity-60 hover:opacity-100"
          }`}
          title="Toggle Filter Panel"
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M3 7V5a2 2 0 012-2h14a2 2 0 012 2v2l-8 8v6l-4-2v-4L3 7z" />
          </svg>
        </button>

        {/* Recent Alerts Toggle */}
        <button
          onClick={onToggleAlerts}
          className={`nav-button w-12 h-12 flex items-center justify-center transition-all duration-200 ${
            isAlertsOpen
              ? "nav-button-active text-white"
              : "text-white opacity-60 hover:opacity-100"
          }`}
          title="Toggle Recent Alerts"
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C13.1 2 14 2.9 14 4V8L15.5 9.5C15.8 9.8 16 10.2 16 10.6V19C16 20.1 15.1 21 14 21H6C4.9 21 4 20.1 4 19V10.6C4 10.2 4.2 9.8 4.5 9.5L6 8V4C6 2.9 6.9 2 8 2H12M10 4V7.5L8.5 9H11.5L10 7.5V4M12 11V13H8V11H12M12 15V17H8V15H12M18 14L16.5 12.5L18 11L22 15L18 19L16.5 17.5L18 16H18V14Z" />
          </svg>
        </button>

        {/* Details Panel Toggle */}
        <button
          onClick={onToggleDetails}
          className={`nav-button w-12 h-12 flex items-center justify-center transition-all duration-200 ${
            isDetailsOpen
              ? "nav-button-active text-white"
              : "text-white opacity-60 hover:opacity-100"
          }`}
          title="Toggle Details Panel"
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2M18 20H6V4H13V9H18V20M8 12V14H16V12H8M8 16V18H13V16H8Z" />
          </svg>
        </button>

        {/* Settings Toggle */}
        <button
          onClick={onToggleSettings}
          className={`nav-button w-12 h-12 flex items-center justify-center transition-all duration-200 ${
            isSettingsOpen
              ? "nav-button-active text-white"
              : "text-white opacity-60 hover:opacity-100"
          }`}
          title="Settings"
        >
          <svg
            className="w-6 h-6"
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
        </button>
      </div>

      {/* Copyright Text - Hidden on Mobile */}
      <div className="mt-auto hidden sm:block">
        <div
          className="text-white text-xs opacity-40 tracking-wide"
          style={{
            writingMode: "vertical-rl",
            textOrientation: "mixed",
            transform: "rotate(180deg)",
          }}
        >
          Team REACH © 2025
        </div>
      </div>
    </div>
  );
};
