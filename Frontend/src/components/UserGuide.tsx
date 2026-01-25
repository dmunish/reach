import React from "react";

export interface UserGuideProps {
  isVisible: boolean;
  onClose: () => void;
}

export const UserGuide: React.FC<UserGuideProps> = ({ isVisible, onClose }) => {
  return (
    <>
      <div 
        id="user-guide-window"
        className={`fixed
          inset-4
          sm:left-22 sm:right-4
          sm:top-4 sm:bottom-4
          frosted-glass 
          transform transition-all duration-300 ease-in-out z-50 
          overflow-hidden
          flex flex-col
          ${
            isVisible
              ? "translate-y-0 opacity-100 scale-100"
              : "translate-y-10 opacity-0 scale-95 pointer-events-none"
          }
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-stone/20">
          <div className="flex items-center gap-3">
            <svg
              className="w-6 h-6 text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.73 5.832 18.247 7.5 18.247s3.332.483 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.73 18.247 18.247 16.5 18.247s-3.332.483-4.5 1.253"
              />
            </svg>
            <h3 className="text-xl font-medium text-white">REACH User Guide</h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-bangladesh-green rounded-full transition-colors group"
          >
            <svg
              className="w-5 h-5 text-gray-300 group-hover:text-white"
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

        <div className="w-full h-px bg-stone/20"></div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-8 dark-scrollbar">
          <div className="max-w-4xl mx-auto space-y-16">
            
            {/* Section 1: Introduction */}
            <section className="space-y-6">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-base font-bold text-bangladesh-green px-2.5 py-1 bg-bangladesh-green/10 rounded">01</span>
                <span className="text-base text-gray-300 font-medium uppercase tracking-wider">Introduction</span>
              </div>
              <div className="bg-white/5 p-8 border border-white/5 rounded-sm">
                <p className="text-gray-300 leading-relaxed text-base">
                  REACH (Real-time Emergency Alert Collection Hub) is an automated system designed to help people in Pakistan stay informed about critical hazards. It gathers emergency bulletins from various official sources and organizes them into a single, interactive map and dashboard. By using AI to process complex reports, REACH provides clear, actionable information when you need it most.
                </p>
              </div>
            </section>

            {/* Section 2: Scope */}
            <section className="space-y-6">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-base font-bold text-bangladesh-green px-2.5 py-1 bg-bangladesh-green/10 rounded">02</span>
                <span className="text-base text-gray-300 font-medium uppercase tracking-wider">Scope</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Abilities */}
                <div className="p-6 bg-white/5 border border-white/5">
                  <h3 className="text-lg font-semibold text-green-400 mb-6 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    What REACH Can Do
                  </h3>
                  <ul className="space-y-4 text-base text-gray-300">
                    <li className="flex gap-3">
                      <span className="text-green-500 font-bold">•</span> 
                      <span><strong>Centralized Tracking</strong>: We frequently monitor official government bulletins so you don’t have to check multiple websites.</span>
                    </li>
                    <li className="flex gap-3">
                      <span className="text-green-500 font-bold">•</span> 
                      <span><strong>Processing</strong>: AI extracts key details such as the severity, type of hazard, affected locations automatically.</span>
                    </li>
                    <li className="flex gap-3">
                      <span className="text-green-500 font-bold">•</span> 
                      <span><strong>Mapping</strong>: We turn text-based location data into visual boundaries on a map to show you exactly which areas are affected.</span>
                    </li>
                  </ul>
                </div>

                {/* Limitations */}
                <div className="p-6 bg-white/5 border border-white/5">
                  <h3 className="text-lg font-semibold text-red-400 mb-6 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Current Limitations
                  </h3>
                  <ul className="space-y-4 text-base text-gray-300">
                    <li className="flex gap-3">
                      <span className="text-red-500 font-bold">•</span> 
                      <span><strong>Data Accuracy</strong>: AI-generated mapping and summaries should be cross-referenced with official sources.</span>
                    </li>
                    <li className="flex gap-3">
                      <span className="text-red-500 font-bold">•</span> 
                      <span><strong>Duplicates</strong>: You may see multiple entries for the same event if different agencies report on it at different times.</span>
                    </li>
                    <li className="flex gap-3">
                      <span className="text-red-500 font-bold">•</span> 
                      <span><strong>Performance</strong>: For the best experience, a stable internet connection and a desktop device are recommended.</span>
                    </li>
                  </ul>
                </div>
              </div>
            </section>

            {/* Section 3: How to Use the Dashboard */}
            <section className="space-y-12">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-base font-bold text-bangladesh-green px-2.5 py-1 bg-bangladesh-green/10 rounded">03</span>
                <span className="text-base text-gray-300 font-medium uppercase tracking-wider">How to Use the Dashboard</span>
              </div>
              
              {/* 3.1 Interactive Map - Layout Kept, Styling updated to Detail Card style */}
              <div className="bg-white/5 p-8 border border-white/5">
                <h4 className="text-white font-medium text-xl mb-4">Interactive Map</h4>
                <p className="text-gray-300 text-base mb-8">The map allows you to see the geographic reach of current hazards at a glance.</p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                  <div className="flex flex-col gap-4">
                      <div className="p-4 bg-rich-black/40 border border-white/5">
                          <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Markers</span>
                          <span className="text-gray-300 text-base">Each pin represents the center of an alert area. The color of the pin indicates the severity level.</span>
                      </div>
                      <div className="p-4 bg-rich-black/40 border border-white/5">
                          <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Interaction</span>
                          <span className="text-gray-300 text-base">Click any pin to highlight the affected region and open the <strong>Details Card</strong>.</span>
                      </div>
                  </div>
                  <div className="w-full bg-rich-black/50 rounded border border-white/5 overflow-hidden">
                    <img 
                      src="https://github.com/dmunish/reach/blob/main/Assets/Map-Highlighting.png?raw=true" 
                      alt="Interactive Map Interface" 
                      className="w-full h-auto object-contain block"
                    />
                  </div>
                </div>
              </div>

              {/* 3.2 Details Card */}
              <div className="bg-white/5 p-8 border border-white/5">
                <h4 className="text-white font-medium text-xl mb-4">Details Card</h4>
                <p className="text-gray-300 text-base mb-8">This panel provides a full breakdown of a specific alert:</p>
                
                <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
                  <div className="md:col-span-5 md:aspect-auto w-full overflow-hidden border border-white/5">
                    <img 
                      src="https://github.com/dmunish/reach/blob/main/Assets/Detail-Card.png?raw=true" 
                      alt="Alert Details Panel" 
                      className="max-w-full max-h-full object-contain"
                    />
                  </div>

                  <div className="md:col-span-7 flex flex-col gap-4">
                    <div className="p-4 bg-rich-black/40 border border-white/5">
                      <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Title, Dates and Description</span>
                      <span className="text-gray-300 text-base">A quick summary and the time window for which the alert is active.</span>
                    </div>
                    <div className="p-4 bg-rich-black/40 border border-white/5">
                      <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Source</span>
                      <span className="text-gray-300 text-base">The official agency that issued the alert. Use the "Source" button to view the original document.</span>
                    </div>
                    <div className="p-4 bg-rich-black/40 border border-white/5">
                      <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Instructions</span>
                      <span className="text-gray-300 text-base">A list of safety steps for citizens. Note that some instructions may be AI-generated to provide clarity if the original source was brief.</span>
                    </div>
                    <div className="p-4 bg-rich-black/40 border border-white/5">
                      <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Affected Areas</span>
                      <span className="text-gray-300 text-base">A list of specific regions mentioned in the alert. *Note: If a large region like "Punjab" is mentioned, smaller cities within it may not be listed individually.*</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 3.3 Filter Panel */}
              <div className="bg-white/5 p-8 border border-white/5">
                <h4 className="text-white font-medium text-xl mb-4">Filter Panel</h4>
                <p className="text-gray-300 text-base mb-6">Use the Filter Panel to find specific information within a large number of alerts. Click the <strong>"Filters"</strong> button at the top to show or hide these tools.</p>
                
                <div className="w-full overflow-hidden border border-white/5 mb-8">
                  <img 
                    src="https://github.com/dmunish/reach/blob/main/Assets/Filter-Alerts-Panel.png?raw=true" 
                    alt="Dashboard Filters" 
                    className="w-full h-auto object-contain"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 bg-rich-black/40 border border-white/5">
                    <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Search Bar</span>
                    <span className="text-gray-300 text-base">Search for specific keywords, locations, or types of emergencies. It is designed to handle small typos.</span>
                  </div>
                  <div className="p-4 bg-rich-black/40 border border-white/5">
                    <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Date Range & Status</span>
                    <span className="text-gray-300 text-base">Filter alerts by active status, all, or specific date ranges.</span>
                  </div>
                  <div className="p-4 bg-rich-black/40 border border-white/5">
                    <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Category & Severity</span>
                    <span className="text-gray-300 text-base">Narrow your view to specific types of hazards (like weather) or threat levels.</span>
                  </div>
                  <div className="p-4 bg-rich-black/40 border border-white/5">
                    <span className="text-bangladesh-green font-bold block mb-1 uppercase text-sm tracking-wider">Scope</span>
                    <span className="text-gray-300 text-base">Switch between "Nationwide" to see everything, or "Local" to see alerts near your current GPS location.</span>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* Backdrop */}
      {isVisible && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity duration-300"
          onClick={onClose}
        />
      )}
    </>
  );
};