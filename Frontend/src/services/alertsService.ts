// @ts-nocheck
import { supabase } from "../lib/supabase";
import type {
  AlertWithLocation,
  AlertCategory,
  AlertSeverity,
  AlertUrgency,
} from "../types/database";

export interface AlertsFilters {
  startDate?: Date;
  endDate?: Date;
  category?: AlertCategory;
  categories?: string[];
  severity?: AlertSeverity;
  severities?: string[];
  urgency?: AlertUrgency;
  source?: string;
}

export interface AlertsServiceResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

class AlertsService {
  /**
   * Fetch all alerts with optional filtering and pagination
   */
  async getAlerts(
    filters?: AlertsFilters,
    limit = 1000,
    offset = 0
  ): Promise<AlertsServiceResult<AlertWithLocation[]>> {
    try {
      let query = supabase
        .from("alerts")
        .select(
          `
          *,
          document:documents(*),
          alert_areas(
            *,
            place:places(*)
          )
        `
        )
        .order("effective_from", { ascending: false })
        .range(offset, offset + limit - 1);

      // Apply filters
      if (filters?.startDate) {
        console.log("Applying startDate filter:", filters.startDate);
        query = query.gte("effective_until", filters.startDate.toISOString());
      }

      if (filters?.endDate) {
        console.log("Applying endDate filter:", filters.endDate);
        query = query.lte("effective_from", filters.endDate.toISOString());
      }

      if (filters?.category) {
        console.log("Applying category filter:", filters.category);
        query = query.eq("category", filters.category);
      }

      if (filters?.categories && filters.categories.length > 0) {
        console.log("Applying categories filter:", filters.categories);
        query = query.in("category", filters.categories);
      }

      if (filters?.severity) {
        console.log("Applying severity filter:", filters.severity);
        query = query.eq("severity", filters.severity);
      }

      if (filters?.severities && filters.severities.length > 0) {
        console.log("Applying severities filter:", filters.severities);
        query = query.in("severity", filters.severities);
      }

      if (filters?.urgency) {
        console.log("Applying urgency filter:", filters.urgency);
        query = query.eq("urgency", filters.urgency);
      }

      console.log("Executing query with filters:", filters);
      const { data, error } = await query;
      console.log("Query result - data count:", data?.length, "error:", error);

      if (error) {
        console.error("Error fetching alerts:", error);
        return { data: null, error: error.message, loading: false };
      }

      return { data: data as AlertWithLocation[], error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alerts:", error);
      return {
        data: null,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }

  /**
   * Fetch a single alert by ID with full details
   */
  async getAlertById(
    id: string
  ): Promise<AlertsServiceResult<AlertWithLocation>> {
    try {
      const { data, error } = await supabase
        .from("alerts")
        .select(
          `
          *,
          document:documents(*),
          alert_areas(
            *,
            place:places(*)
          )
        `
        )
        .eq("id", id)
        .single();

      if (error) {
        console.error("Error fetching alert by ID:", error);
        return { data: null, error: error.message, loading: false };
      }

      return { data: data as AlertWithLocation, error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alert by ID:", error);
      return {
        data: null,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }

  /**
   * Fetch alerts by geographic bounds (for map display)
   */
  async getAlertsByBounds(
    _north: number,
    _south: number,
    _east: number,
    _west: number
  ): Promise<AlertsServiceResult<AlertWithLocation[]>> {
    try {
      // This would require a PostGIS function to check if alert areas intersect with bounds
      // For now, we'll fetch all alerts and let the frontend filter
      const { data, error } = await supabase
        .from("alerts")
        .select(
          `
          *,
          document:documents(*),
          alert_areas(
            *,
            place:places(*)
          )
        `
        )
        .order("effective_from", { ascending: false });

      if (error) {
        console.error("Error fetching alerts by bounds:", error);
        return { data: null, error: error.message, loading: false };
      }

      return { data: data as AlertWithLocation[], error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alerts by bounds:", error);
      return {
        data: null,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }

  /**
   * Fetch active alerts (currently effective)
   */
  async getActiveAlerts(): Promise<AlertsServiceResult<AlertWithLocation[]>> {
    try {
      const now = new Date().toISOString();

      const { data, error } = await supabase
        .from("alerts")
        .select(
          `
          *,
          document:documents(*),
          alert_areas(
            *,
            place:places(*)
          )
        `
        )
        .lte("effective_from", now)
        .gte("effective_until", now)
        .order("effective_from", { ascending: false });

      if (error) {
        console.error("Error fetching active alerts:", error);
        return { data: null, error: error.message, loading: false };
      }

      return { data: data as AlertWithLocation[], error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching active alerts:", error);
      return {
        data: null,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
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

      const uniqueSources = [...new Set(data.map((item) => item.source))];
      return { data: uniqueSources, error: null, loading: false };
    } catch (error) {
      console.error("Unexpected error fetching alert sources:", error);
      return {
        data: null,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
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
      // @ts-ignore - Suppress type errors for dynamic alert data aggregation
      const bySeverity = allAlerts.reduce((acc, alert) => {
        acc[alert.severity] = (acc[alert.severity] || 0) + 1;
        return acc;
      }, {} as Record<AlertSeverity, number>);

      // @ts-ignore - Suppress type errors for dynamic alert data aggregation
      const byCategory = allAlerts.reduce((acc, alert) => {
        acc[alert.category] = (acc[alert.category] || 0) + 1;
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
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        loading: false,
      };
    }
  }
}

// Export a singleton instance
export const alertsService = new AlertsService();
