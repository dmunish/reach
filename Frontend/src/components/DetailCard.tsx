import React from "react";

export interface DetailData {
  id?: string;
  title: string;
  description: string;
  location?: string;
  date?: Date;
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
}

export const DetailCard: React.FC<DetailCardProps> = ({
  isVisible,
  data,
  onClose,
  onActionClick,
}) => {
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

  const [isMoreInfoExpanded, setIsMoreInfoExpanded] = React.useState(false);

  const renderInstructionWithNewlines = (text: string) => {
    return text.split('\n').map((line, index) => (
      <React.Fragment key={index}>
        {line}
        {index < text.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
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
      <div className="space-y-5">
        {/* Title and Effective Dates - Centered */}
        <div className="text-center space-y-2">
          <h1 className="text-lg font-bold text-white">
            {data.title || "Alert"}
          </h1>
          {data.date && data.additionalInfo?.effectiveUntil && (
            <div className="text-sm text-gray-400">
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
        <div className="w-full h-px bg-gray-700"></div>

        {/* Description Section */}
        {data.description && (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
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
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Description
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {data.description}
            </p>
          </div>
        )}

        {/* Areas Section */}
        {data.additionalInfo?.places && data.additionalInfo.places.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
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
            </h3>
            <p className="text-sm text-gray-300">
              {data.additionalInfo.places.join(", ")}
            </p>
          </div>
        )}

        {/* Instructions Section */}
        {data.instruction && (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-caribbean-green flex items-center gap-2">
              <svg
                className="w-4 h-4"
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
            </h3>
            <div className="bg-bangladesh-green bg-opacity-10 border border-bangladesh-green border-opacity-30 p-3 rounded-lg">
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                {renderInstructionWithNewlines(data.instruction)}
              </p>
            </div>
          </div>
        )}

        {/* More Info - Expandable */}
        <div className="space-y-2 pb-4">
          <button
            onClick={() => setIsMoreInfoExpanded(!isMoreInfoExpanded)}
            className="w-full flex items-center justify-between text-sm font-semibold text-gray-300 hover:text-white transition-colors"
          >
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
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              More Info
            </div>
            <svg
              className={`w-4 h-4 text-gray-400 transform transition-transform ${
                isMoreInfoExpanded ? "rotate-180" : ""
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

          {isMoreInfoExpanded && (
            <div className="space-y-2 pl-2">
              {/* Source */}
              {data.source && (
                <div className="flex items-start gap-2">
                  <span className="text-sm text-gray-500 font-medium min-w-[70px]">Source:</span>
                  {data.documentUrl ? (
                    <a
                      href={data.documentUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-caribbean-green hover:text-mountain-meadow underline"
                    >
                      {data.source}
                    </a>
                  ) : (
                    <span className="text-sm text-gray-300">{data.source}</span>
                  )}
                </div>
              )}

              {/* Category */}
              {data.category && (
                <div className="flex items-start gap-2">
                  <span className="text-sm text-gray-500 font-medium min-w-[70px]">Category:</span>
                  <span className="text-sm text-gray-300">{getCategoryFullName(data.category)}</span>
                </div>
              )}

              {/* Urgency */}
              {data.urgency && (
                <div className="flex items-start gap-2">
                  <span className="text-sm text-gray-500 font-medium min-w-[70px]">Urgency:</span>
                  <span className={`text-sm font-medium ${getUrgencyColor(data.urgency)}`}>
                    {data.urgency}
                  </span>
                </div>
              )}

              {/* Severity */}
              {data.severity && (
                <div className="flex items-start gap-2">
                  <span className="text-sm text-gray-500 font-medium min-w-[70px]">Severity:</span>
                  <span className={`text-sm font-medium ${getSeverityColor(data.severity)}`}>
                    {data.severity}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Detail card */}
      <div
        className={`fixed 
          bottom-4 left-4 right-4 h-80 
          sm:bottom-4 sm:right-4 sm:left-auto sm:w-96 sm:max-w-96
          frosted-glass transform transition-all duration-300 ease-in-out z-40 overflow-y-auto dark-scrollbar
          ${
            isVisible
              ? "translate-y-0 opacity-100"
              : "translate-y-full opacity-0"
          }
        `}
      >
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
