// Database types matching the DBML schema
export type AlertCategory =
  | "Geo"
  | "Met"
  | "Safety"
  | "Security"
  | "Rescue"
  | "Fire"
  | "Health"
  | "Env"
  | "Transport"
  | "Infra"
  | "CBRNE"
  | "Other";

export type AlertUrgency =
  | "Immediate"
  | "Expected"
  | "Future"
  | "Past"
  | "Unknown";

export type AlertSeverity =
  | "Extreme"
  | "Severe"
  | "Moderate"
  | "Minor"
  | "Unknown";

export interface Document {
  id: string;
  source: string; // NDMA, NEOC, etc.
  posted_date: string;
  title: string;
  url: string;
  filename: string;
  filetype: string;
  processed_at: string | null;
}

export interface Place {
  id: string;
  name: string;
  parent_id: string | null;
  parent_name: string | null;
  hierarchy_level: number | null;
  polygon: any; // PostGIS geometry type
}

export interface Alert {
  id: string;
  document_id: string;
  category: AlertCategory;
  event: string;
  urgency: AlertUrgency;
  severity: AlertSeverity;
  description: string;
  instruction: string;
  effective_from: string;
  effective_until: string;
}

export interface AlertArea {
  id: string;
  alert_id: string;
  place_id: string;
  specific_effective_from: string | null;
  specific_effective_until: string | null;
  specific_urgency: AlertUrgency | null;
  specific_severity: AlertSeverity | null;
  specific_instruction: string | null;
}

// Combined view type for displaying alerts with location information (legacy)
export interface AlertWithLocation extends Alert {
  document?: Document;
  alert_areas?: (AlertArea & {
    place?: Place;
  })[];
}

// New type for alerts returned by get_alerts() RPC function
// Contains pre-computed centroids and bbox for performance
export interface AlertFromRPC {
  id: string;
  category: AlertCategory | null;
  event: string | null;
  severity: AlertSeverity | null;
  urgency: AlertUrgency | null;
  description: string | null;
  source: string | null;
  url: string | null;
  effective_from: string | null;
  effective_until: string | null;
  affected_places: string[] | null;
  centroid_lat: number | null;
  centroid_lng: number | null;
  bbox_xmin: number | null;
  bbox_ymin: number | null;
  bbox_xmax: number | null;
  bbox_ymax: number | null;
}

// GeoJSON geometry type returned by get_alert_geometry()
export interface AlertGeometry {
  type: string;
  coordinates: number[][][] | number[][][][];
}

// Filter parameters for get_alerts() RPC function
export interface AlertsRPCFilters {
  status_filter?: 'active' | 'archived' | 'all';
  search_query?: string;
  category_filter?: AlertCategory;
  severity_filter?: AlertSeverity;
  urgency_filter?: AlertUrgency;
  date_start?: string;
  date_end?: string;
  sort_by?: 'effective_from' | 'severity' | 'urgency';
  sort_order?: 'asc' | 'desc';
  page_size?: number;
  page_offset?: number;
}

// Database schema type for Supabase client
export interface Database {
  public: {
    Tables: {
      documents: {
        Row: Document;
        Insert: Omit<Document, "id">;
        Update: Partial<Omit<Document, "id">>;
      };
      places: {
        Row: Place;
        Insert: Omit<Place, "id">;
        Update: Partial<Omit<Place, "id">>;
      };
      alerts: {
        Row: Alert;
        Insert: Omit<Alert, "id">;
        Update: Partial<Omit<Alert, "id">>;
      };
      alert_areas: {
        Row: AlertArea;
        Insert: Omit<AlertArea, "id">;
        Update: Partial<Omit<AlertArea, "id">>;
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      get_alerts: {
        Args: {
          status_filter: "active" | "archived" | "all";
          search_query: string | null;
          category_filter: string | null;
          severity_filter: string | null;
          urgency_filter: string | null;
          date_start: string | null;
          date_end: string | null;
          sort_by: string;
          sort_order: string;
          page_size: number;
          page_offset: number;
        };
        Returns: AlertFromRPC[];
      };
      get_alert_geometry: {
        Args: {
          alert_uuid: string;
        };
        Returns: AlertGeometry | null;
      };
    };
    Enums: {
      alert_category: AlertCategory;
      alert_urgency: AlertUrgency;
      alert_severity: AlertSeverity;
    };
  };
}
