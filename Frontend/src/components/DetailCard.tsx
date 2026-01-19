import React from "react";

export interface DetailData {
  id?: string;
  title: string;
  description: string;
  location?: string;
  date?: Date;
  postedDate?: Date;
  category?: string;
  severity?: string;
  urgency?: string;
  instruction?: string;
  source?: string;
  documentUrl?: string;
  additionalInfo?: Record<string, any>;
}

export interface DetailCardProps {
  isVisible: boolean;
  data: DetailData | null;
  onClose: () => void;
  onActionClick?: (action: string, data: DetailData) => void;
  width: number;
  onWidthChange: (width: number) => void;
}

export const DetailCard: React.FC<DetailCardProps> = ({
  isVisible,
  data,
  onClose,
  onActionClick,
  width,
  onWidthChange,
}) => {
  const [isResizing, setIsResizing] = React.useState(false);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const newWidth = window.innerWidth - moveEvent.clientX - 16; // 16 for right-4
      if (newWidth > 200 && newWidth < window.innerWidth - 300) {
        onWidthChange(newWidth);
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

  const formatDate = (date: Date) => {
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getSeverityColor = (severity?: string) => {
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

  const getUrgencyColor = (urgency?: string) => {
    switch (urgency?.toLowerCase()) {
      case "immediate":
        return "text-red-400";
      case "expected":
        return "text-orange-400";
      case "future":
        return "text-blue-400";
      default:
        return "text-gray-400";
    }
  };

  const getCategoryFullName = (category?: string): string => {
    switch (category) {
      case "Geo":
        return "Geological";
      case "Met":
        return "Meteorological";
      case "Safety":
        return "Safety";
      case "Security":
        return "Security";
      case "Rescue":
        return "Rescue";
      case "Fire":
        return "Fire";
      case "Health":
        return "Health";
      case "Env":
        return "Environmental";
      case "Transport":
        return "Transportation";
      case "Infra":
        return "Infrastructure";
      case "CBRNE":
        return "CBRNE";
      case "Other":
        return "Other";
      default:
        return category || "Unknown";
    }
  };

  const handleViewMore = () => {
    if (data && onActionClick) {
      onActionClick("view-more", data);
    }
  };

  const handleShare = () => {
    if (data && onActionClick) {
      onActionClick("share", data);
    }
  };

  const [isAreasExpanded, setIsAreasExpanded] = React.useState(false);
  const [areaSearchQuery, setAreaSearchQuery] = React.useState("");

  const renderInstructionList = (text: string) => {
    return (
      <ul className="list-none space-y-2">
        {text.split('\n').filter(line => line.trim() !== "").map((line, index) => (
          <li key={index} className="text-sm text-gray-300 leading-relaxed">
            {line.trim()}
          </li>
        ))}
      </ul>
    );
  };

  const renderContent = () => {
    if (!data) {
      return (
        <div className="text-center text-gray-400 py-8">
          <svg
            className="w-12 h-12 mx-auto mb-4 text-gray-500"
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
          <p className="text-white">Click on an alert to view details</p>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        {/* Title and Effective Dates - Centered */}
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold text-white leading-tight">
            {data.title || "Alert"}
          </h1>
          {data.date && data.additionalInfo?.effectiveUntil && (
            <div className="text-sm text-gray-500 font-medium">
              {data.date.toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
              {" - "}
              {data.additionalInfo.effectiveUntil.toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="w-full h-px bg-white/10"></div>

        {/* Source Button */}
        {data.source && (
          <div className="flex justify-center">
            <button
              onClick={() => {
                if (data.documentUrl) {
                  window.open(data.documentUrl, "_blank", "noopener,noreferrer");
                }
              }}
              className={`
                px-4 py-2 rounded-full font-semibold text-white text-sm
                bg-bangladesh-green transition-all duration-200 border-2 border-transparent
                ${
                  data.documentUrl
                    ? "hover:bg-mountain-meadow hover:border-white/20 shadow-lg hover:shadow-bangladesh-green/40 cursor-pointer"
                    : "cursor-default opacity-90"
                }
              `}
            >
              Source: {data.source}
            </button>
          </div>
        )}

        {/* Details Pills (Category, Severity, Urgency) */}
        <div className="flex flex-wrap justify-center gap-2">
          {data.category && (
            <div className="px-3 py-1 rounded-md bg-rich-black/50 border border-white/10 text-xs text-gray-300 flex items-center gap-1">
              <span className="text-gray-500 font-medium">Category:</span>
              <span className="text-white font-medium">{getCategoryFullName(data.category)}</span>
            </div>
          )}
          {data.severity && (
            <div className="px-3 py-1 rounded-md bg-rich-black/50 border border-white/10 text-xs text-gray-300 flex items-center gap-1">
              <span className="text-gray-500 font-medium">Severity:</span>
              <span className={`font-medium ${getSeverityColor(data.severity)}`}>
                {data.severity}
              </span>
            </div>
          )}
          {data.urgency && (
            <div className="px-3 py-1 rounded-md bg-rich-black/50 border border-white/10 text-xs text-gray-300 flex items-center gap-1">
              <span className="text-gray-500 font-medium">Urgency:</span>
              <span className={`font-medium ${getUrgencyColor(data.urgency)}`}>
                {data.urgency}
              </span>
            </div>
          )}
        </div>

        {/* Description Section */}
        {data.description && (
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <svg
                className="w-5 h-5 text-caribbean-green"
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
              Description
            </h2>
            <p className="text-sm text-gray-300 leading-relaxed">
              {data.description}
            </p>
          </div>
        )}

        {/* Instructions Section */}
        {data.instruction && (
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <svg
                className="w-5 h-5 text-caribbean-green"
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
              Instructions
            </h2>
            <div className="bg-bangladesh-green/10 border-l-2 border-bangladesh-green p-3 rounded-r-lg">
              {renderInstructionList(data.instruction)}
            </div>
          </div>
        )}

        {/* Affected Areas Section */}
        {data.additionalInfo?.places && data.additionalInfo.places.length > 0 && (
          <div className="space-y-3">
             <button
              onClick={() => setIsAreasExpanded(!isAreasExpanded)}
              className="w-full flex items-center justify-between group"
            >
              <h2 className="text-lg font-semibold text-white flex items-center gap-2 group-hover:text-caribbean-green transition-colors">
                <svg
                  className="w-5 h-5 text-caribbean-green"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                Affected Areas
              </h2>
              <svg
                className={`w-5 h-5 text-gray-400 transform transition-transform duration-200 ${
                  isAreasExpanded ? "rotate-180" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {isAreasExpanded && (
              <div className="space-y-3 animate-fadeIn">
                {/* Search Bar */}
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search areas..."
                    value={areaSearchQuery}
                    onChange={(e) => setAreaSearchQuery(e.target.value)}
                    className="w-full bg-rich-black/50 border border-white/10 rounded-lg px-3 py-2 pl-9 text-sm text-white focus:outline-none focus:border-caribbean-green transition-colors"
                  />
                  <svg
                    className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2"
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

                {/* Areas List */}
                <div className="flex flex-wrap gap-1.5 p-2 bg-rich-black/30 rounded-lg max-h-40 overflow-y-auto dark-scrollbar">
                  {data.additionalInfo.places
                    .filter((p: string) => !areaSearchQuery || p.toLowerCase().includes(areaSearchQuery.toLowerCase()))
                    .map((place: string, idx: number) => {
                      const isMatch = areaSearchQuery && place.toLowerCase().includes(areaSearchQuery.toLowerCase());
                      return (
                        <span
                          key={idx}
                          className={`text-sm px-2 py-0.5 rounded transition-colors ${
                            isMatch
                              ? "bg-caribbean-green/30 text-white font-medium border border-caribbean-green/50"
                              : "text-gray-400 bg-white/5"
                          }`}
                        >
                          {place}
                        </span>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      {/* Detail card */}
      <div
        className={`fixed 
          bottom-4 left-4 right-4 h-80 
          sm:top-4 sm:bottom-4 sm:h-auto sm:right-4 sm:left-auto
          frosted-glass transform transition-all duration-300 ease-in-out z-40 overflow-y-auto dark-scrollbar
          ${
            isVisible
              ? "translate-y-0 opacity-100"
              : "translate-y-full opacity-0"
          }
          ${isResizing ? "transition-none" : ""}
        `}
        style={{
          width: window.innerWidth < 640 ? 'auto' : `${width}px`,
          maxWidth: window.innerWidth < 640 ? 'none' : `${width}px`
        }}
      >
        {/* Resize Handle - Left */}
        <div 
          className="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-caribbean-green/50 transition-colors z-50 hidden sm:block"
          onMouseDown={handleMouseDown}
        />

        <div className="p-4 h-full flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-end mb-3">
            <button
              onClick={onClose}
              className="p-1 hover:bg-bangladesh-green rounded-full transition-colors"
              title="Close alert details"
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

          {/* Content */}
          <div className="flex-1 overflow-y-auto dark-scrollbar">
            {renderContent()}
          </div>
        </div>
      </div>
    </>
  );
};
