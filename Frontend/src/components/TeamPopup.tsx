import React from "react";

export interface TeamPopupProps {
  isVisible: boolean;
  onClose: () => void;
}

const developers = [
  {
    role: "Backend",
    name: "Danish Munib",
    image:
      "https://danishmunib.weebly.com/uploads/1/4/6/2/146277355/1x1_orig.jpg",
    description: "I'm REACHing for your balls, visitor.",
  },
  {
    role: "Frontend",
    name: "Rafay Ahmad",
    image: "https://bonevane.vercel.app/me.webp",
    description: "Ah. This looks clean.",
  },
  {
    role: "Geocoding",
    name: "Ahmad Shahmeer",
    image:
      "https://ui-avatars.com/api/?name=Ahmad+Shahmeer&background=007b81&color=fff&size=128",
    description: "When life gives you lemons, fuck the lemons.",
  },
];

export const TeamPopup: React.FC<TeamPopupProps> = ({ isVisible, onClose }) => {
  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-rich-black/80 backdrop-blur-sm z-50 transition-opacity duration-300
          ${isVisible ? "opacity-100" : "opacity-0 pointer-events-none"}
        `}
        onClick={onClose}
      />

      {/* Modal Window using frosted-glass theme */}
      <div
        className={`fixed
          left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
          w-[95%] max-w-5xl max-h-[90vh]
          frosted-glass
          transform transition-all duration-300 ease-out z-50
          overflow-y-auto dark-scrollbar
          flex flex-col
          ${
            isVisible
              ? "scale-100 opacity-100"
              : "scale-95 opacity-0 pointer-events-none"
          }
        `}
      >
        {/* Header - Consistent with UserGuide and FilterPanel */}
        <div className="flex items-center justify-between p-5 border-b border-white/10 bg-rich-black/40 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="p-2">
              <svg
                className="w-6 h-6 text-mountain-meadow"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-medium text-white tracking-wide">
              Team REACH
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors"
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 sm:p-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {developers.map((dev, index) => (
              <div
                key={index}
                className="flex flex-col items-center text-center p-6 rounded-lg bg-rich-black/40 hover:border-mountain-meadow/30 transition-all duration-300"
              >
                {/* Image */}
                <div className="relative mb-5">
                  <img
                    src={dev.image}
                    alt={dev.role}
                    className="w-36 h-36 rounded-full border-2 border-white/10 object-cover shadow-lg"
                  />
                  <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 bg-white/20 text-white text-xs backdrop-blur-lg font-semibold px-3 py-1 rounded-full border border-mountain-meadow/30 shadow-sm">
                    {dev.role}
                  </div>
                </div>

                {/* Details */}
                <h3 className="text-lg font-semibold text-white mt-2 mb-2">
                  {dev.name}
                </h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  "{dev.description}"
                </p>
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <span className="text-xs text-stone uppercase tracking-widest">
              Built with love for a better Pakistan
            </span>
          </div>
        </div>
      </div>
    </>
  );
};
