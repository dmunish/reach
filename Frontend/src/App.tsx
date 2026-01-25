import React, {
  useState,
  useRef,
  useMemo,
  useCallback,
  useEffect,
} from "react";
import { useDebouncedCallback } from "use-debounce";
import { MapComponent, type MapRef } from "./components/MapComponent";
import { Navbar } from "./components/Navbar";
import { FilterAlertsPanel } from "./components/FilterAlertsPanel";
import { DetailCard, type DetailData } from "./components/DetailCard";
import { SettingsPanel, type UserSettings } from "./components/SettingsPanel";
import { UserGuide } from "./components/UserGuide";
import { useAlerts, useAlertGeometry } from "./hooks/useAlerts";
import type { AlertFromRPC, AlertsRPCFilters, AlertCategory, AlertSeverity, AlertUrgency } from "./types/database";

// Transform RPC alert data to match our DetailData interface
// Uses pre-computed centroids and bbox from the server
function transformAlertToDetailData(alert: AlertFromRPC): DetailData {
  // Use pre-computed centroid from server (already lat/lng from PostGIS)
  const coordinates: [number, number] = 
    alert.centroid_lng != null && alert.centroid_lat != null
      ? [alert.centroid_lng, alert.centroid_lat]
      : [69.3451, 30.3753]; // Default to Pakistan center

  // Extract bbox for zoom fitting
  const bbox = (alert.bbox_xmin != null && alert.bbox_ymin != null && 
                alert.bbox_xmax != null && alert.bbox_ymax != null)
    ? {
        xmin: alert.bbox_xmin,
        ymin: alert.bbox_ymin,
        xmax: alert.bbox_xmax,
        ymax: alert.bbox_ymax,
      }
    : null;

  return {
    id: alert.id,
    title: alert.event || "Unknown Event",
    description: alert.description || "",
    location: alert.affected_places?.[0] || "Unknown Location",
    date: alert.effective_from ? new Date(alert.effective_from) : new Date(),
    postedDate: alert.posted_date ? new Date(alert.posted_date) : undefined,
    category: alert.category || undefined,
    severity: alert.severity || undefined,
    urgency: alert.urgency || undefined,
    instruction: alert.instruction || undefined,
    source: alert.source || "Unknown",
    documentUrl: alert.url || undefined,
    additionalInfo: {
      coordinates,
      bbox,
      effectiveUntil: alert.effective_until ? new Date(alert.effective_until) : undefined,
      places: alert.affected_places || [],
      // Geometry will be loaded on-demand via hover/click
      geometry: undefined,
    },
  };
}

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

export const App: React.FC = () => {
  const [selectedAlert, setSelectedAlert] = useState<DetailData | null>(null);
  const [isDetailCardVisible, setIsDetailCardVisible] = useState(false);
  
  // Replaced individual panel toggles with a consolidated one where appropriate
  // We'll treat 'isAlertsPanelVisible' as the visibility for the new FilterAlertsPanel
  const [isAlertsPanelVisible, setIsAlertsPanelVisible] = useState(false);
  const [isSettingsPanelVisible, setIsSettingsPanelVisible] = useState(false);
  const [isUserGuideVisible, setIsUserGuideVisible] = useState(false);
  
  // Resizable panel states
  const [alertsPanelHeight, setAlertsPanelHeight] = useState(400);
  const [sidePanelWidth, setSidePanelWidth] = useState(576); // Increased by 50% from 384
  
  // Filter States
  const [scope, setScope] = useState<'nationwide' | 'local'>('nationwide');
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState<string>("");
  const [dateFilters, setDateFilters] = useState<{
    startDate?: Date;
    endDate?: Date;
  }>({});
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<AlertCategory | undefined>(undefined);
  const [urgencyFilter, setUrgencyFilter] = useState<AlertUrgency | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active');
  const [sortBy, setSortBy] = useState<'effective_from' | 'posted_date' | 'severity' | 'urgency'>('posted_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [mapTheme, setMapTheme] = useState<string>("dark-v11");
  const [showPolygons, setShowPolygons] = useState<boolean>(true);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [filtersInitialized, setFiltersInitialized] = useState(false);
  const mapRef = useRef<MapRef>(null);
  const autoRefreshInterval = useRef<number | null>(null);
  const activeAlertIdRef = useRef<string | null>(null);

  // Geometry fetching hook
  const { fetchGeometry, prefetchGeometry } = useAlertGeometry();

  // Debounced search - waits 300ms after user stops typing
  const debouncedSetSearch = useDebouncedCallback(
    (value: string) => {
      setDebouncedSearchQuery(value);
    },
    300
  );

  // Clear search
  const handleClearSearch = useCallback(() => {
    setSearchQuery("");
    setDebouncedSearchQuery("");
  }, [debouncedSetSearch]);

  const handleRequestLocation = useCallback(() => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser");
      setScope('nationwide');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setUserLocation({ lat: latitude, lng: longitude });
        if (mapRef.current) {
          mapRef.current.flyTo([longitude, latitude], 10);
        }
      },
      (error) => {
        console.error("Error getting location:", error);
        alert("Unable to retrieve your location. Reverting to nationwide scope.");
        setScope('nationwide');
        setUserLocation(null);
      }
    );
  }, []);

  const handleResetFilters = useCallback(() => {
    setSearchQuery("");
    setDebouncedSearchQuery("");
    setDateFilters({});
    setSeverityFilter(undefined);
    setCategoryFilter(undefined);
    setUrgencyFilter(undefined);
    setStatusFilter('active');
    setSortBy('posted_date');
    setSortOrder('desc');
    setScope('nationwide');
    setUserLocation(null);
  }, []);

  const handleFilterChange = useCallback((key: string, value: any) => {
    switch (key) {
      case 'scope':
        setScope(value);
        if (value === 'local') {
          handleRequestLocation();
        } else {
          setUserLocation(null);
        }
        break;
      case 'searchQuery':
        setSearchQuery(value);
        debouncedSetSearch(value);
        break;
      case 'status':
        setStatusFilter(value);
        break;
      case 'severity':
        setSeverityFilter(value);
        break;
      case 'urgency':
        setUrgencyFilter(value);
        break;
      case 'category':
        setCategoryFilter(value);
        break;
      case 'startDate':
        setDateFilters(prev => ({ ...prev, startDate: value }));
        break;
      case 'endDate':
        setDateFilters(prev => ({ ...prev, endDate: value }));
        break;
      case 'sortBy':
        setSortBy(value);
        break;
      case 'sortOrder':
        setSortOrder(value);
        break;
    }
  }, [debouncedSetSearch, handleRequestLocation]);

  // Load user settings from localStorage on mount
  useEffect(() => {
    // Check if it's the first time the user is visiting
    const hasSeenGuide = localStorage.getItem("reach_has_seen_guide");
    if (!hasSeenGuide) {
      setIsUserGuideVisible(true);
    }

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
        setFiltersInitialized(true);
      }
    };
    loadUserSettings();
  }, []);

  const handleCloseUserGuide = useCallback(() => {
    setIsUserGuideVisible(false);
    localStorage.setItem("reach_has_seen_guide", "true");
  }, []);

  const handleOpenUserGuide = useCallback(() => {
    setIsUserGuideVisible(true);
  }, []);

  // Build RPC filters from UI state (uses debounced search query)
  const alertsFilters = useMemo<AlertsRPCFilters>(
    () => ({
      status_filter: statusFilter,
      search_query: debouncedSearchQuery || undefined,
      category_filter: categoryFilter,
      severity_filter: severityFilter,
      urgency_filter: urgencyFilter,
      date_start: dateFilters.startDate?.toISOString(),
      date_end: dateFilters.endDate?.toISOString(),
      sort_by: sortBy,
      sort_order: sortOrder,
      page_size: 100,
      page_offset: 0,
      user_lat: scope === 'local' ? userLocation?.lat : undefined,
      user_lng: scope === 'local' ? userLocation?.lng : undefined,
      radius_km: scope === 'local' ? 20 : undefined,
    }),
    [
      debouncedSearchQuery, 
      categoryFilter, 
      severityFilter, 
      urgencyFilter,
      dateFilters.startDate, 
      dateFilters.endDate,
      statusFilter,
      sortBy,
      sortOrder,
      scope,
      userLocation
    ]
  );

  const {
    alerts: rpcAlerts,
    loading,
    error,
    refetch,
  } = useAlerts({
    filters: alertsFilters,
    autoFetch: settingsLoaded && filtersInitialized,
  });

  // Transform RPC alerts to DetailData format
  const currentAlerts = useMemo(() => {
    return rpcAlerts.map(transformAlertToDetailData);
  }, [rpcAlerts]);

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

  // Handle hover on alert - prefetch geometry only (no map movement)
  const handleAlertHover = useCallback(async (alert: DetailData) => {
    if (alert.id) {
      // Start prefetching geometry asynchronously
      prefetchGeometry(alert.id);
    }
  }, [prefetchGeometry]);

  const handleAlertClick = useCallback(async (alert: DetailData) => {
    setSelectedAlert(alert);
    setIsDetailCardVisible(true);

    if (alert.id) {
      activeAlertIdRef.current = alert.id;
    }

    if (mapRef.current && alert.id) {
      // Clear any existing highlight immediately
      mapRef.current.clearHighlight();

      // First, zoom to bbox if available
      if (alert.additionalInfo?.bbox) {
        mapRef.current.fitToBbox(alert.additionalInfo.bbox, 60);
      } else if (alert.additionalInfo?.coordinates) {
        const [lng, lat] = alert.additionalInfo.coordinates;
        mapRef.current.flyTo([lng, lat], 8);
      }

      // Fetch geometry (will use cache if available from hover)
      const geometry = await fetchGeometry(alert.id);
      
      if (activeAlertIdRef.current === alert.id && geometry && mapRef.current) {
        // Highlight the geometry on the map
        mapRef.current.highlightGeoJSON(geometry);
      }
    }
  }, [fetchGeometry]);

  const handleDetailCardClose = () => {
    setIsDetailCardVisible(false);
    setSelectedAlert(null);
    activeAlertIdRef.current = null;

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
            title: data.title || "",
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

  // Prepare markers for map using pre-computed centroids
  const mapMarkers = useMemo(() => {
    const markers = currentAlerts
      .filter((alert) => alert.additionalInfo?.coordinates)
      .filter((alert) => !selectedAlert || alert.id === selectedAlert.id)
      .map((alert) => ({
        coordinates: alert.additionalInfo!.coordinates as [number, number],
        severity: alert.severity,
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

    // Add user location marker if available
    if (userLocation) {
      markers.push({
        coordinates: [userLocation.lng, userLocation.lat],
        severity: "user",
        popupContent: `
          <div class="p-2 bg-rich-black text-white rounded shadow-lg border border-white/10">
            <p class="text-xs font-semibold">Your Location</p>
          </div>
        `,
        onClick: async () => {
          if (mapRef.current) {
            mapRef.current.flyTo([userLocation.lng, userLocation.lat], 10);
          }
        },
      });
    }

    return markers;
  }, [currentAlerts, selectedAlert, userLocation, handleAlertClick]);

  // Panel toggle handlers
  const handleToggleFilter = () => {
    // Both toggle the same panel now as they are merged
    setIsAlertsPanelVisible(!isAlertsPanelVisible);
    if (!isAlertsPanelVisible) {
      setIsSettingsPanelVisible(false);
    }
  };

  const handleToggleDetails = () => {
    if (isDetailCardVisible) {
      handleDetailCardClose();
    } else {
      setIsDetailCardVisible(true);
      if (isDetailCardVisible !== true) {
        setIsSettingsPanelVisible(false);
      }
    }
  };

  const handleToggleSettings = () => {
    const newVisibility = !isSettingsPanelVisible;
    setIsSettingsPanelVisible(newVisibility);

    if (newVisibility) {
      // Close other panels when settings is opened
      setIsAlertsPanelVisible(false);
      if (isDetailCardVisible) {
        handleDetailCardClose();
      }
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
          markers={mapMarkers}
          className="w-full h-full"
        />
      </div>

      {/* Navigation Bar */}
      <Navbar
        onToggleFilter={handleToggleFilter}
        onToggleDetails={handleToggleDetails}
        onToggleSettings={handleToggleSettings}
        isFilterOpen={isAlertsPanelVisible}
        isDetailsOpen={isDetailCardVisible}
        isSettingsOpen={isSettingsPanelVisible}
      />

      {/* Combined Filter & Alerts Panel (Bottom Left - Full Width) */}
      <FilterAlertsPanel
        isVisible={isAlertsPanelVisible}
        onClose={() => setIsAlertsPanelVisible(false)}
        height={alertsPanelHeight}
        onHeightChange={setAlertsPanelHeight}
        sidePanelWidth={sidePanelWidth}
        alerts={currentAlerts}
        loading={loading}
        error={error}
        filters={{
          searchQuery,
          status: statusFilter,
          severity: severityFilter,
          category: categoryFilter,
          urgency: urgencyFilter,
          startDate: dateFilters.startDate,
          endDate: dateFilters.endDate,
          sortBy,
          sortOrder,
          scope
        }}
        onFilterChange={handleFilterChange}
        onClearSearch={handleClearSearch}
        onResetFilters={handleResetFilters}
        onRefresh={refreshAlerts}
        onAlertClick={handleAlertClick}
        onAlertHover={handleAlertHover}
      />

      {/* Detail Card (Right Side Full Height) */}
      <DetailCard
        isVisible={isDetailCardVisible}
        data={selectedAlert}
        onClose={handleDetailCardClose}
        onActionClick={handleDetailCardAction}
        width={sidePanelWidth}
        onWidthChange={setSidePanelWidth}
      />

      {/* Settings Panel (Full Screen Popup) */}
      <SettingsPanel
        isVisible={isSettingsPanelVisible}
        onClose={() => setIsSettingsPanelVisible(false)}
        onSettingsChange={handleSettingsChange}
        onOpenUserGuide={handleOpenUserGuide}
      />

      <UserGuide
        isVisible={isUserGuideVisible}
        onClose={handleCloseUserGuide}
      />
    </div>
  );
};
