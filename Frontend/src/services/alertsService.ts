import { supabase } from "../lib/supabase";
import type {
  AlertFromRPC,
  AlertGeometry,
  AlertsRPCFilters,
  AlertCategory,
  AlertSeverity,
} from "../types/database";

export interface AlertsServiceResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

// Geometry cache to avoid redundant fetches
const geometryCache = new Map<string, AlertGeometry | null>();

class AlertsService {
  /**
   * Fetch alerts using the get_alerts() RPC function
   * All filtering, sorting, and pagination is handled server-side
   */
  async getAlerts(
    filters?: AlertsRPCFilters
  ): Promise<AlertsServiceResult<AlertFromRPC[]>> {
    try {
      console.log("alertsService: Calling get_alerts RPC with filters:", filters);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data, error } = await (supabase.rpc as any)("get_alerts", {
        status_filter: filters?.status_filter ?? "active",
        search_query: filters?.search_query ?? null,
        category_filter: filters?.category_filter ?? null,
        severity_filter: filters?.severity_filter ?? null,
        urgency_filter: filters?.urgency_filter ?? null,
        date_start: filters?.date_start ?? null,
        date_end: filters?.date_end ?? null,
        sort_by: filters?.sort_by ?? "posted_date",
        sort_order: filters?.sort_order ?? "desc",
        page_size: filters?.page_size ?? 100,
        page_offset: filters?.page_offset ?? 0,
      });

      if (error) {
        console.error("Error fetching alerts via RPC:", error);
        return { data: null, error: error.message, loading: false };
      }

      console.log("alertsService: Fetched alerts count:", (data as AlertFromRPC[])?.length ?? 0);
      return { data: (data as AlertFromRPC[]) ?? [], error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alerts:", error);
      return {
        data: null,
        error: error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }

  /**
   * Fetch geometry for an alert using get_alert_geometry() RPC function
   * Results are cached to avoid redundant fetches
   */
  async getAlertGeometry(
    alertId: string
  ): Promise<AlertsServiceResult<AlertGeometry | null>> {
    try {
      // Check cache first
      if (geometryCache.has(alertId)) {
        console.log("alertsService: Returning cached geometry for alert:", alertId);
        return { data: geometryCache.get(alertId) ?? null, error: null, loading: false };
      }

      console.log("alertsService: Fetching geometry for alert:", alertId);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data, error } = await (supabase.rpc as any)("get_alert_geometry", {
        alert_uuid: alertId,
      });

      if (error) {
        console.error("Error fetching alert geometry via RPC:", error);
        return { data: null, error: error.message, loading: false };
      }

      // Cache the result (even if null)
      const geometry = data as AlertGeometry | null;
      geometryCache.set(alertId, geometry);

      console.log("alertsService: Fetched and cached geometry for alert:", alertId);
      return { data: geometry, error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alert geometry:", error);
      return {
        data: null,
        error: error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }

  /**
   * Check if geometry is already cached for an alert
   */
  isGeometryCached(alertId: string): boolean {
    return geometryCache.has(alertId);
  }

  /**
   * Get cached geometry without fetching
   */
  getCachedGeometry(alertId: string): AlertGeometry | null | undefined {
    return geometryCache.get(alertId);
  }

  /**
   * Pre-fetch geometry for an alert (for hover preloading)
   * Returns a promise that resolves when the geometry is cached
   */
  async prefetchGeometry(alertId: string): Promise<void> {
    if (!geometryCache.has(alertId)) {
      await this.getAlertGeometry(alertId);
    }
  }

  /**
   * Clear the geometry cache (useful for testing or memory management)
   */
  clearGeometryCache(): void {
    geometryCache.clear();
    console.log("alertsService: Geometry cache cleared");
  }

  /**
   * Get unique alert sources for filtering
   */
  async getAlertSources(): Promise<AlertsServiceResult<string[]>> {
    try {
      const { data, error } = await supabase
        .from("documents")
        .select("source")
        .not("source", "is", null);

      if (error) {
        console.error("Error fetching alert sources:", error);
        return { data: null, error: error.message, loading: false };
      }

      if (!data) {
        return { data: [], error: null, loading: false };
      }

      const uniqueSources = [...new Set(data.map((item: any) => item.source))];
      return { data: uniqueSources, error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alert sources:", error);
      return {
        data: null,
        error: error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }

  /**
   * Get alert statistics for dashboard
   */
  async getAlertStatistics(): Promise<
    AlertsServiceResult<{
      total: number;
      active: number;
      bySeverity: Record<AlertSeverity, number>;
      byCategory: Record<AlertCategory, number>;
    }>
  > {
    try {
      const now = new Date().toISOString();

      // Get total count
      const { count: totalCount, error: totalError } = await supabase
        .from("alerts")
        .select("*", { count: "exact", head: true });

      if (totalError) {
        return { data: null, error: totalError.message, loading: false };
      }

      // Get active count
      const { count: activeCount, error: activeError } = await supabase
        .from("alerts")
        .select("*", { count: "exact", head: true })
        .lte("effective_from", now)
        .gte("effective_until", now);

      if (activeError) {
        return { data: null, error: activeError.message, loading: false };
      }

      // Get all alerts for grouping (could be optimized with database functions)
      const { data: allAlerts, error: alertsError } = await supabase
        .from("alerts")
        .select("severity, category");

      if (alertsError) {
        return { data: null, error: alertsError.message, loading: false };
      }

      // Group by severity and category
      const bySeverity = (allAlerts || []).reduce((acc: any, alert: any) => {
        if (alert.severity) {
          acc[alert.severity as AlertSeverity] = (acc[alert.severity] || 0) + 1;
        }
        return acc;
      }, {} as Record<AlertSeverity, number>);

      const byCategory = (allAlerts || []).reduce((acc: any, alert: any) => {
        if (alert.category) {
          acc[alert.category as AlertCategory] = (acc[alert.category] || 0) + 1;
        }
        return acc;
      }, {} as Record<AlertCategory, number>);

      return {
        data: {
          total: totalCount || 0,
          active: activeCount || 0,
          bySeverity,
          byCategory,
        },
        error: null,
        loading: false,
      };
    } catch (error) {
      console.error("Unexpected error fetching alert statistics:", error);
      return {
        data: null,
        error: error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }
}

// Export a singleton instance
export const alertsService = new AlertsService();

// Re-export types for convenience
export type { AlertsRPCFilters };
