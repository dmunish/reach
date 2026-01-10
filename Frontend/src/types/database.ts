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

// Combined view type for displaying alerts with location information
export interface AlertWithLocation extends Alert {
  document?: Document;
  alert_areas?: (AlertArea & {
    place?: Place;
  })[];
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
      [_ in never]: never;
    };
    Enums: {
      alert_category: AlertCategory;
      alert_urgency: AlertUrgency;
      alert_severity: AlertSeverity;
    };
  };
}
