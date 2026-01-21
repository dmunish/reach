import { useState, useEffect, useCallback, useRef } from "react";
import { alertsService, type AlertsRPCFilters } from "../services/alertsService";
import type { AlertFromRPC, AlertGeometry, AlertCategory, AlertSeverity, AlertUrgency } from "../types/database";

interface UseAlertsOptions {
  filters?: AlertsRPCFilters;
  autoFetch?: boolean;
}

export function useAlerts(options: UseAlertsOptions = {}) {
  const { filters, autoFetch = true } = options;

  const [alerts, setAlerts] = useState<AlertFromRPC[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Track the last fetched filters to avoid duplicate calls
  const lastFetchedFilters = useRef<string>("");

  const fetchAlerts = useCallback(async (forceRefetch = false) => {
    // Create a string representation of current filters for comparison
    const filterString = JSON.stringify(filters);
    
    // Skip if already fetched with same filters (unless forced)
    if (!forceRefetch && filterString === lastFetchedFilters.current && alerts.length > 0) {
      console.log("useAlerts: Skipping fetch - filters unchanged");
      return;
    }

    console.log("useAlerts: Fetching alerts with RPC filters:", filters);
    setLoading(true);
    setError(null);

    try {
      const result = await alertsService.getAlerts(filters);

      if (result.error) {
        setError(result.error);
        setAlerts([]);
      } else {
        console.log("useAlerts: Fetched alerts count:", result.data?.length);
        setAlerts(result.data || []);
        lastFetchedFilters.current = filterString;
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch alerts";
      setError(errorMessage);
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [
    filters?.status_filter,
    filters?.search_query,
    filters?.category_filter,
    filters?.severity_filter,
    filters?.urgency_filter,
    filters?.date_start,
    filters?.date_end,
    filters?.sort_by,
    filters?.sort_order,
    filters?.page_size,
    filters?.page_offset,
    filters?.user_lat,
    filters?.user_lng,
    filters?.radius_km,
  ]);

  const refetch = useCallback(() => {
    return fetchAlerts(true);
  }, [fetchAlerts]);

  useEffect(() => {
    if (autoFetch) {
      console.log("useAlerts: Auto-fetching with filters:", filters);
      fetchAlerts();
    }
  }, [fetchAlerts, autoFetch]);

  return {
    alerts,
    loading,
    error,
    refetch,
    fetchAlerts,
  };
}

// Hook for fetching alert geometry with caching
export function useAlertGeometry() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGeometry = useCallback(async (alertId: string): Promise<AlertGeometry | null> => {
    // Check cache first
    if (alertsService.isGeometryCached(alertId)) {
      console.log("useAlertGeometry: Returning cached geometry for:", alertId);
      return alertsService.getCachedGeometry(alertId) ?? null;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await alertsService.getAlertGeometry(alertId);

      if (result.error) {
        setError(result.error);
        return null;
      }

      return result.data;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch geometry";
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const prefetchGeometry = useCallback(async (alertId: string): Promise<void> => {
    // Non-blocking prefetch for hover preloading
    if (!alertsService.isGeometryCached(alertId)) {
      alertsService.prefetchGeometry(alertId).catch((err) => {
        console.warn("useAlertGeometry: Prefetch failed for:", alertId, err);
      });
    }
  }, []);

  const isGeometryCached = useCallback((alertId: string): boolean => {
    return alertsService.isGeometryCached(alertId);
  }, []);

  const getCachedGeometry = useCallback((alertId: string): AlertGeometry | null | undefined => {
    return alertsService.getCachedGeometry(alertId);
  }, []);

  return {
    loading,
    error,
    fetchGeometry,
    prefetchGeometry,
    isGeometryCached,
    getCachedGeometry,
  };
}
