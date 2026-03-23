import React from "react";

export interface NavbarProps {
  onToggleFilter: () => void;
  onToggleAgent: () => void;
  onToggleSettings: () => void;
  onTeamClick?: () => void; // Optional to avoid breaking build before parent update
  isFilterOpen: boolean;
  isAgentOpen: boolean;
  isSettingsOpen: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  onToggleFilter,
  onToggleAgent,
  onToggleSettings,
  onTeamClick,
  isFilterOpen,
  isAgentOpen,
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
      <div className="mr-auto sm:mr-0 sm:mb-12 select-none">
        <div
          className="text-white font-bold text-lg tracking-wider
          sm:transform sm:rotate-180
          hidden sm:block text-shine-vertical"
          style={{
            writingMode: "vertical-rl",
            textOrientation: "mixed",
          }}
        >
          REACH
        </div>
        <div className="text-white font-bold text-lg tracking-wider sm:hidden text-shine">
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
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>

        {/* Agent Chat Toggle */}
        <button
          onClick={onToggleAgent}
          className={`nav-button w-12 h-12 flex items-center justify-center transition-all duration-200 ${
            isAgentOpen
              ? "nav-button-active text-white"
              : "text-white opacity-60 hover:opacity-100"
          }`}
          title="Analytics & QA Agent"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
            <polyline points="12 3 20 7.5 20 16.5 12 21 4 16.5 4 7.5 12 3"></polyline>
            <polyline points="12 12 20 7.5"></polyline>
            <polyline points="12 12 12 21"></polyline>
            <polyline points="12 12 4 7.5"></polyline>
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
        <button
          onClick={onTeamClick}
          className="text-white text-xs tracking-wide text-shine-vertical cursor-pointer hover:opacity-80 transition-opacity focus:outline-none"
          style={{
            writingMode: "vertical-rl",
            textOrientation: "mixed",
            transform: "rotate(180deg)",
          }}
        >
          Team REACH © 2026
        </button>
      </div>
    </div>
  );
};
