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
  
  // Resizable panel states
  const [alertsPanelHeight, setAlertsPanelHeight] = useState(400);
  const [sidePanelWidth, setSidePanelWidth] = useState(384);
  
  // Filter States
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState<string>("");
  const [dateFilters, setDateFilters] = useState<{
    startDate?: Date;
    endDate?: Date;
  }>({});
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<AlertCategory | undefined>(undefined);
  const [urgencyFilter, setUrgencyFilter] = useState<AlertUrgency | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<'active' | 'archived' | 'all'>('active');
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

  // Calculate map padding based on active panels
  // This ensures the polygon is centered in the visible area
  const calculateMapPadding = useCallback(() => {
    // Base padding for comfortable viewing
    const basePadding = 40;
    // Navbar width on desktop (72px) + some margin
    const navbarOffset = window.innerWidth >= 640 ? 72 : 0;
    // Top offset for mobile navbar
    const topNavbarOffset = window.innerWidth < 640 ? 64 : 0;
    
    let padding = {
      top: basePadding + topNavbarOffset,
      bottom: basePadding,
      left: basePadding + navbarOffset,
      right: basePadding,
    };

    // Add padding for FilterAlertsPanel (bottom panel)
    if (isAlertsPanelVisible) {
      // Panel height + margin (16px bottom-4)
      padding.bottom = alertsPanelHeight + 16 + basePadding;
    }

    // Add padding for DetailCard (right panel)
    if (isDetailCardVisible) {
      // Panel width + margin (16px right-4)
      padding.right = sidePanelWidth + 16 + basePadding;
    }

    return padding;
  }, [isAlertsPanelVisible, isDetailCardVisible, alertsPanelHeight, sidePanelWidth]);

  // Function to fit map to selected alert's bbox with panel-aware padding
  const fitMapToSelectedAlert = useCallback(() => {
    if (!selectedAlert?.additionalInfo?.bbox || !mapRef.current) return;
    
    const padding = calculateMapPadding();
    mapRef.current.fitToBboxWithOffset(selectedAlert.additionalInfo.bbox, padding);
  }, [selectedAlert, calculateMapPadding]);

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
  }, []);

  const handleFilterChange = useCallback((key: string, value: any) => {
    switch (key) {
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
  }, [debouncedSetSearch]);

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
        setFiltersInitialized(true);
      }
    };
    loadUserSettings();
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
      sortOrder
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

      // Calculate padding accounting for panels that will be visible
      // Detail card will be visible after this click, and alerts panel may also be visible
      const basePadding = 40;
      const navbarOffset = window.innerWidth >= 640 ? 72 : 0;
      const topNavbarOffset = window.innerWidth < 640 ? 64 : 0;
      
      const padding = {
        top: basePadding + topNavbarOffset,
        bottom: isAlertsPanelVisible ? alertsPanelHeight + 16 + basePadding : basePadding,
        left: basePadding + navbarOffset,
        right: sidePanelWidth + 16 + basePadding, // Detail card will be visible
      };

      // Fit to bbox with panel-aware padding if available
      if (alert.additionalInfo?.bbox) {
        mapRef.current.fitToBboxWithOffset(alert.additionalInfo.bbox, padding);
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
  }, [fetchGeometry, isAlertsPanelVisible, alertsPanelHeight, sidePanelWidth]);

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

  // Re-fit map when panel dimensions change (resize) while an alert is selected
  useEffect(() => {
    if (selectedAlert?.additionalInfo?.bbox && (isDetailCardVisible || isAlertsPanelVisible)) {
      // Use a small timeout to allow the panel resize to complete
      const timeoutId = setTimeout(() => {
        fitMapToSelectedAlert();
      }, 50);
      return () => clearTimeout(timeoutId);
    }
  }, [alertsPanelHeight, sidePanelWidth, fitMapToSelectedAlert, selectedAlert, isDetailCardVisible, isAlertsPanelVisible]);

  // Re-fit map when panels are toggled while an alert is selected
  useEffect(() => {
    if (selectedAlert?.additionalInfo?.bbox) {
      // Only re-fit if at least one panel is visible
      if (isDetailCardVisible || isAlertsPanelVisible) {
        fitMapToSelectedAlert();
      }
    }
  }, [isDetailCardVisible, isAlertsPanelVisible, selectedAlert, fitMapToSelectedAlert]);

  // Prepare markers for map using pre-computed centroids
  const mapMarkers = currentAlerts
    .filter((alert) => alert.additionalInfo?.coordinates)
    .filter((alert) => !selectedAlert || alert.id === selectedAlert.id) // Only show selected alert's pin when focused
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
          sortOrder
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
      />
    </div>
  );
};
