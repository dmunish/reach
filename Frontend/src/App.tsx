import React, {
  useState,
  useRef,
  useMemo,
  useCallback,
  useEffect,
} from "react";
import { MapComponent, type MapRef } from "./components/MapComponent";
import { Navbar } from "./components/Navbar";
import { FilterPanel } from "./components/FilterPanel";
import { RecentAlertsPanel } from "./components/RecentAlertsPanel";
import { DetailCard, type DetailData } from "./components/DetailCard";
import { SettingsPanel, type UserSettings } from "./components/SettingsPanel";
import { useAlerts } from "./hooks/useAlerts";
import type { AlertWithLocation } from "./types/database";

// Function to calculate centroid of a polygon
function calculatePolygonCentroid(coordinates: number[][]): [number, number] {
  let totalLng = 0;
  let totalLat = 0;
  let pointCount = coordinates.length;

  coordinates.forEach(([lng, lat]) => {
    totalLng += lng;
    totalLat += lat;
  });

  return [totalLng / pointCount, totalLat / pointCount];
}

// Function to extract centroid coordinates from PostGIS geometry data
function extractCoordinatesFromGeometry(polygon: any): [number, number] | null {
  if (!polygon) return null;

  try {
    // Handle different PostGIS geometry formats
    if (typeof polygon === "string") {
      // Parse WKT string like "POLYGON((lng lat, lng lat, ...))"
      const polygonMatch = polygon.match(
        /POLYGON\s*\(\s*\(\s*([\d.-\s,]+)\s*\)\s*\)/i
      );
      if (polygonMatch) {
        const coordString = polygonMatch[1];
        const coordinates: number[][] = [];

        // Extract all coordinate pairs
        const coordPairs = coordString.split(",");
        coordPairs.forEach((pair) => {
          const coords = pair.trim().split(/\s+/);
          if (coords.length >= 2) {
            const lng = parseFloat(coords[0]);
            const lat = parseFloat(coords[1]);
            if (!isNaN(lng) && !isNaN(lat)) {
              coordinates.push([lng, lat]);
            }
          }
        });

        if (coordinates.length > 0) {
          return calculatePolygonCentroid(coordinates);
        }
      }
    } else if (polygon && typeof polygon === "object") {
      // If it's a GeoJSON-like object
      if (polygon.type === "Polygon" && polygon.coordinates?.[0]) {
        const ringCoordinates = polygon.coordinates[0]; // Outer ring
        if (Array.isArray(ringCoordinates) && ringCoordinates.length > 0) {
          return calculatePolygonCentroid(ringCoordinates);
        }
      }
      // If it's a Point, return it directly
      if (polygon.type === "Point" && polygon.coordinates) {
        const [lng, lat] = polygon.coordinates;
        return [lng, lat];
      }
      // If coordinates are directly available as array
      if (polygon.coordinates && Array.isArray(polygon.coordinates)) {
        if (Array.isArray(polygon.coordinates[0])) {
          // It's an array of coordinates, calculate centroid
          return calculatePolygonCentroid(polygon.coordinates);
        } else {
          // It's a single coordinate pair
          const [lng, lat] = polygon.coordinates;
          return [lng, lat];
        }
      }
    }
  } catch (error) {
    console.warn("Failed to parse geometry:", error);
  }

  return null;
}

// Transform Supabase alert data to match our DetailData interface
function transformAlertToDetailData(alert: AlertWithLocation): DetailData {
  const firstLocation = alert.alert_areas?.[0]?.place;

  // Extract coordinates from PostGIS geometry data
  let coordinates: [number, number];

  if (firstLocation?.polygon) {
    const extractedCoords = extractCoordinatesFromGeometry(
      firstLocation.polygon
    );
    if (extractedCoords) {
      coordinates = extractedCoords;
    } else {
      // Fallback to Pakistan center if geometry parsing fails
      coordinates = [69.3451, 30.3753]; // Pakistan center
    }
  } else {
    // Default to Pakistan center if no geometry data
    coordinates = [69.3451, 30.3753];
  }

  return {
    id: alert.id,
    title: alert.event,
    description: alert.description,
    location: firstLocation?.name || "Unknown Location",
    date: new Date(alert.effective_from),
    category: alert.category,
    severity: alert.severity,
    urgency: alert.urgency,
    instruction: alert.instruction,
    source: alert.document?.source || "Unknown",
    additionalInfo: {
      coordinates,
      effectiveUntil: new Date(alert.effective_until),
      places:
        alert.alert_areas?.map((area) => area.place?.name).filter(Boolean) ||
        [],
      polygon: firstLocation?.polygon, // Include polygon data for highlighting
    },
  };
}

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

export const App: React.FC = () => {
  const [selectedAlert, setSelectedAlert] = useState<DetailData | null>(null);
  const [isDetailCardVisible, setIsDetailCardVisible] = useState(false);
  const [isFilterPanelVisible, setIsFilterPanelVisible] = useState(false);
  const [isAlertsPanelVisible, setIsAlertsPanelVisible] = useState(false);
  const [isSettingsPanelVisible, setIsSettingsPanelVisible] = useState(false);
  const [dateFilters, setDateFilters] = useState<{
    startDate?: Date;
    endDate?: Date;
  }>({});
  const [severityFilters, setSeverityFilters] = useState<string[]>([]);
  const [categoryFilters, setCategoryFilters] = useState<string[]>([]);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [mapTheme, setMapTheme] = useState<string>("custom");
  const [showPolygons, setShowPolygons] = useState<boolean>(true);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [filtersInitialized, setFiltersInitialized] = useState(false);
  const mapRef = useRef<MapRef>(null);
  const autoRefreshInterval = useRef<number | null>(null);

  // Load user settings from localStorage on mount
  useEffect(() => {
    const loadUserSettings = async () => {
      try {
        const {
          data: { session },
        } = await import("./lib/supabase").then((m) =>
          m.supabase.auth.getSession()
        );
        if (session?.user?.email) {
          const storageKey = `reach_settings_${session.user.email}`;
          const savedSettings = localStorage.getItem(storageKey);
          if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            setUserSettings(settings);
            setMapTheme(settings.mapTheme || "custom");
            setShowPolygons(settings.showPolygons ?? true);
          }
        }
      } catch (error) {
        console.error("Failed to load user settings:", error);
      } finally {
        setSettingsLoaded(true);
      }
    };
    loadUserSettings();
  }, []);

  // Use the Supabase alerts hook with filters
  const alertsFilters = useMemo(
    () => ({
      startDate: dateFilters.startDate,
      endDate: dateFilters.endDate,
      ...(severityFilters.length > 0 ? { severities: severityFilters } : {}),
      ...(categoryFilters.length > 0 ? { categories: categoryFilters } : {}),
    }),
    [
      dateFilters.startDate,
      dateFilters.endDate,
      severityFilters,
      categoryFilters,
    ]
  );

  const {
    alerts: supabaseAlerts,
    loading,
    error,
    refetch,
  } = useAlerts({
    filters: alertsFilters,
    autoFetch: settingsLoaded && filtersInitialized,
  });

  // Transform Supabase alerts to DetailData format
  const currentAlerts = useMemo(
    () => supabaseAlerts.map(transformAlertToDetailData),
    [supabaseAlerts]
  );

  const getSeverityColor = (severity?: string): string => {
    switch (severity?.toLowerCase()) {
      case "extreme":
        return "bg-red-100 text-red-800";
      case "severe":
        return "bg-orange-100 text-orange-800";
      case "moderate":
        return "bg-yellow-100 text-yellow-800";
      case "minor":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const handleMapClick = (coordinates: [number, number], event: any) => {
    // Map clicks are now only used for marker interactions
    // No action needed for regular map clicks
  };

  const handleDateRangeChange = useCallback(
    (startDate: Date | null, endDate: Date | null) => {
      setDateFilters({
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      });
    },
    []
  );

  const handleFiltersChange = useCallback(
    (filters: { severities: string[]; categories: string[] }) => {
      setSeverityFilters(filters.severities);
      setCategoryFilters(filters.categories);
      setFiltersInitialized(true);
    },
    []
  );

  const handleAlertClick = (alert: DetailData) => {
    setSelectedAlert(alert);
    setIsDetailCardVisible(true);

    // Fly to location and highlight polygon on map
    if (alert.additionalInfo?.coordinates && mapRef.current) {
      const [lng, lat] = alert.additionalInfo.coordinates;
      mapRef.current.flyTo([lng, lat], 7);

      // Highlight the polygon if geometry data is available
      if (alert.additionalInfo?.polygon) {
        mapRef.current.highlightPolygon(alert.additionalInfo.polygon);
      }
    }
  };

  const handleDetailCardClose = () => {
    setIsDetailCardVisible(false);
    setSelectedAlert(null);

    // Clear polygon highlight when closing detail card
    if (mapRef.current) {
      mapRef.current.clearHighlight();
    }
  };

  const handleDetailCardAction = (action: string, data: DetailData) => {
    console.log("Detail card action:", action, data);

    switch (action) {
      case "view-more":
        alert(`View more details for: ${data.title}`);
        break;
      case "share":
        if (navigator.share) {
          navigator.share({
            title: data.title,
            text: data.description,
            url: window.location.href,
          });
        } else {
          navigator.clipboard.writeText(`${data.title}: ${data.description}`);
          alert("Alert details copied to clipboard!");
        }
        break;
    }
  };

  const refreshAlerts = useCallback(() => {
    refetch();
  }, [refetch]);

  // Handle settings changes
  const handleSettingsChange = useCallback(
    (settings: UserSettings) => {
      setUserSettings(settings);
      setMapTheme(settings.mapTheme);
      setShowPolygons(settings.showPolygons);

      // Update auto-refresh based on settings
      if (settings.autoRefresh) {
        // Set up auto-refresh every 5 minutes
        if (autoRefreshInterval.current) {
          clearInterval(autoRefreshInterval.current);
        }
        autoRefreshInterval.current = setInterval(() => {
          console.log("Auto-refreshing alerts...");
          refetch();
        }, 5 * 60 * 1000); // 5 minutes
      } else {
        // Clear auto-refresh
        if (autoRefreshInterval.current) {
          clearInterval(autoRefreshInterval.current);
          autoRefreshInterval.current = null;
        }
      }
    },
    [refetch]
  );

  // Clean up auto-refresh on unmount
  useEffect(() => {
    return () => {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current);
      }
    };
  }, []);

  // Prepare markers for map
  const mapMarkers = currentAlerts
    .filter((alert) => alert.additionalInfo?.coordinates)
    .map((alert) => ({
      coordinates: alert.additionalInfo!.coordinates as [number, number],
      popupContent: `
        <div class="p-3" style="background: var(--rich-black); color: var(--anti-flash-white);">
          <h3 class="font-semibold text-sm text-white mb-2">${alert.title}</h3>
          <p class="text-xs text-gray-300 mt-1 mb-2">${alert.description.substring(
            0,
            100
          )}...</p>
          <div class="mt-2">
            <span class="px-2 py-1 text-xs rounded-full ${getSeverityColor(
              alert.severity
            )}">${alert.severity}</span>
          </div>
        </div>
      `,
      onClick: () => handleAlertClick(alert),
    }));

  // Panel toggle handlers
  const handleToggleFilter = () => {
    setIsFilterPanelVisible(!isFilterPanelVisible);
    if (!isFilterPanelVisible) {
      setIsSettingsPanelVisible(false);
    }
  };

  const handleToggleAlerts = () => {
    setIsAlertsPanelVisible(!isAlertsPanelVisible);
    if (!isAlertsPanelVisible) {
      setIsSettingsPanelVisible(false);
    }
  };

  const handleToggleDetails = () => {
    setIsDetailCardVisible(!isDetailCardVisible);
    if (!isDetailCardVisible) {
      setIsSettingsPanelVisible(false);
    }
  };

  const handleToggleSettings = () => {
    const newVisibility = !isSettingsPanelVisible;
    setIsSettingsPanelVisible(newVisibility);

    if (newVisibility) {
      // Close other panels when settings is opened
      setIsFilterPanelVisible(false);
      setIsAlertsPanelVisible(false);
      setIsDetailCardVisible(false);
    }
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-rich-black">
      {/* Fixed Background Map */}
      <div className="fixed inset-0 z-0 pt-16 sm:pt-0 sm:pl-[72px]">
        <MapComponent
          ref={mapRef}
          accessToken={MAPBOX_TOKEN}
          center={[69.3451, 30.3753]}
          theme={mapTheme}
          showPolygons={showPolygons}
          // zoom={6}
          markers={mapMarkers}
          className="w-full h-full"
        />
      </div>

      {/* Navigation Bar */}
      <Navbar
        onToggleFilter={handleToggleFilter}
        onToggleAlerts={handleToggleAlerts}
        onToggleDetails={handleToggleDetails}
        onToggleSettings={handleToggleSettings}
        isFilterOpen={isFilterPanelVisible}
        isAlertsOpen={isAlertsPanelVisible}
        isDetailsOpen={isDetailCardVisible}
        isSettingsOpen={isSettingsPanelVisible}
      />

      {/* Filter Panel (Top Right) */}
      <FilterPanel
        isVisible={isFilterPanelVisible}
        onClose={() => setIsFilterPanelVisible(false)}
        onDateRangeChange={handleDateRangeChange}
        onFiltersChange={handleFiltersChange}
        defaultSeverity={userSettings?.minSeverity}
        defaultTimeRange={userSettings?.defaultTimeRange}
        isLoading={!settingsLoaded}
      />

      {/* Recent Alerts Panel (Bottom Left - Full Width) */}
      <RecentAlertsPanel
        isVisible={isAlertsPanelVisible}
        onClose={() => setIsAlertsPanelVisible(false)}
        alerts={currentAlerts}
        loading={loading}
        error={error}
        onAlertClick={handleAlertClick}
        onRefresh={refreshAlerts}
      />

      {/* Detail Card (Bottom Right) */}
      <DetailCard
        isVisible={isDetailCardVisible}
        data={selectedAlert}
        onClose={handleDetailCardClose}
        onActionClick={handleDetailCardAction}
      />

      {/* Settings Panel (Full Screen Popup) */}
      <SettingsPanel
        isVisible={isSettingsPanelVisible}
        onClose={() => setIsSettingsPanelVisible(false)}
        onSettingsChange={handleSettingsChange}
      />
    </div>
  );
};
