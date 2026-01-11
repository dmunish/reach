import { useState, useEffect, useCallback } from "react";
import { alertsService, type AlertsFilters } from "../services/alertsService";
import type { AlertWithLocation } from "../types/database";

interface UseAlertsOptions {
  filters?: AlertsFilters;
  autoFetch?: boolean;
  activeOnly?: boolean;
}

export function useAlerts(options: UseAlertsOptions = {}) {
  const { filters, autoFetch = true, activeOnly = false } = options;

  const [alerts, setAlerts] = useState<AlertWithLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    console.log("useAlerts: Fetching alerts with filters:", filters);
    setLoading(true);
    setError(null);

    try {
      let result;
      if (activeOnly) {
        result = await alertsService.getActiveAlerts();
      } else {
        result = await alertsService.getAlerts(filters);
      }

      if (result.error) {
        setError(result.error);
        setAlerts([]);
      } else {
        console.log("useAlerts: Fetched alerts count:", result.data?.length);
        setAlerts(result.data || []);
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
    filters?.startDate?.toISOString(),
    filters?.endDate?.toISOString(),
    filters?.severities?.join(","),
    filters?.categories?.join(","),
    filters?.severity,
    filters?.category,
    filters?.urgency,
    filters?.source,
    activeOnly,
  ]);

  const refetch = useCallback(() => {
    return fetchAlerts();
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

// Hook for fetching a single alert
export function useAlert(id: string | null) {
  const [alert, setAlert] = useState<AlertWithLocation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAlert = useCallback(async (alertId: string) => {
    setLoading(true);
    setError(null);

    try {
      const result = await alertsService.getAlertById(alertId);

      if (result.error) {
        setError(result.error);
        setAlert(null);
      } else {
        setAlert(result.data);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch alert";
      setError(errorMessage);
      setAlert(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (id) {
      fetchAlert(id);
    } else {
      setAlert(null);
      setError(null);
    }
  }, [id, fetchAlert]);

  return {
    alert,
    loading,
    error,
    refetch: id ? () => fetchAlert(id) : () => Promise.resolve(),
  };
}
