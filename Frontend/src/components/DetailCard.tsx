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
      <div className="space-y-4">
        {/* Alert Summary Section */}
        <div>
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center gap-2">
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
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
              <span className="text-sm text-gray-400 font-medium">
                Alert Information
              </span>
            </div>
            {data.severity && (
              <span
                className={`text-sm font-bold ${getSeverityColor(
                  data.severity
                )}`}
              >
                Level {getSeverityNumber(data.severity)}
              </span>
            )}
          </div>
        </div>

        {/* Vertical line separator */}
        <div className="w-full h-px bg-stone"></div>

        {/* Basic Information Table */}
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
            <div className="text-xs text-gray-400 font-medium">Alert ID</div>
            <div className="col-span-2 text-xs text-gray-300 font-mono">
              {data.id?.slice(0, 20) || "N/A"}...
            </div>
          </div>

          {data.date && (
            <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
              <div className="text-xs text-gray-400 font-medium">Date</div>
              <div className="col-span-2 text-xs text-gray-300">
                {new Date(data.date).toLocaleString("en-US", {
                  month: "2-digit",
                  day: "2-digit",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                })}
              </div>
            </div>
          )}

          {data.location && (
            <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
              <div className="text-xs text-gray-400 font-medium">Location</div>
              <div className="col-span-2 text-xs text-gray-300">
                {data.location}
              </div>
            </div>
          )}

          {data.category && (
            <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
              <div className="text-xs text-gray-400 font-medium">Category</div>
              <div className="col-span-2 text-xs text-gray-300">
                {data.category}
              </div>
            </div>
          )}

          {data.severity && (
            <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
              <div className="text-xs text-gray-400 font-medium">Severity</div>
              <div className="col-span-2">
                <span
                  className={`text-xs font-medium ${getSeverityColor(
                    data.severity
                  )}`}
                >
                  {data.severity}
                </span>
              </div>
            </div>
          )}

          {data.urgency && (
            <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
              <div className="text-xs text-gray-400 font-medium">Urgency</div>
              <div className="col-span-2">
                <span
                  className={`text-xs font-medium ${getUrgencyColor(
                    data.urgency
                  )}`}
                >
                  {data.urgency}
                </span>
              </div>
            </div>
          )}

          {data.source && (
            <div className="grid grid-cols-3 gap-2 py-1 px-2 hover:bg-rich-black hover:bg-opacity-30">
              <div className="text-xs text-gray-400 font-medium">Source</div>
              <div className="col-span-2 text-xs text-gray-300">
                {data.source}
              </div>
            </div>
          )}
        </div>

        {/* Description Section */}
        {data.description && (
          <div className="space-y-2">
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
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span className="text-sm text-gray-400 font-medium">
                Description
              </span>
            </div>
            <div className="bg-rich-black bg-opacity-30 p-3 rounded-lg">
              <p className="text-xs text-gray-300 leading-relaxed">
                {data.description}
              </p>
            </div>
          </div>
        )}

        {/* Instructions Section */}
        {data.instruction && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-caribbean-green"
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
              <span className="text-sm text-caribbean-green font-medium">
                Emergency Instructions
              </span>
            </div>
            <div className="bg-bangladesh-green bg-opacity-20 border border-bangladesh-green border-opacity-30 p-3 rounded-lg">
              <p className="text-xs text-gray-300 leading-relaxed">
                {data.instruction}
              </p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          <button
            onClick={handleViewMore}
            className="flex-2 px-3 py-2 bg-bangladesh-green hover:bg-mountain-meadow text-white hover:text-dark-green rounded-md transition-colors text-xs font-medium cursor-pointer"
          >
            View Full Report
          </button>
          <button
            onClick={handleShare}
            className="flex-1 px-3 py-2 border border-bangladesh-green text-bangladesh-green hover:bg-bangladesh-green hover:text-white rounded-md transition-colors text-xs font-medium cursor-pointer"
          >
            Share Alert
          </button>
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
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-medium text-white">Alert Details</h2>
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
