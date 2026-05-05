/**
 * Dashboard E2E tests for the current REACH UI.
 * Covers the first-visit guide, the merged alerts/search panel, and Supabase RPC-backed filtering.
 */

type AlertFixture = {
  id: string;
  category: string | null;
  event: string | null;
  severity: string | null;
  urgency: string | null;
  description: string | null;
  instruction: string | null;
  source: string | null;
  url: string | null;
  effective_from: string | null;
  effective_until: string | null;
  posted_date: string | null;
  affected_places: string[] | null;
  centroid_lat: number | null;
  centroid_lng: number | null;
  bbox_xmin: number | null;
  bbox_ymin: number | null;
  bbox_xmax: number | null;
  bbox_ymax: number | null;
};

const baseAlerts: AlertFixture[] = [
  {
    id: "alert-1",
    category: "Met",
    event: "Flash Flood Warning",
    severity: "Extreme",
    urgency: "Immediate",
    description: "Flash flooding expected across Karachi within the next 12 hours.",
    instruction: "Move to higher ground immediately.",
    source: "NDMA",
    url: "https://example.com/alerts/1",
    effective_from: "2026-05-05T10:00:00.000Z",
    effective_until: "2026-05-06T10:00:00.000Z",
    posted_date: "2026-05-05T09:15:00.000Z",
    affected_places: ["Karachi", "Sindh"],
    centroid_lat: 24.8607,
    centroid_lng: 67.0011,
    bbox_xmin: 66.8,
    bbox_ymin: 24.6,
    bbox_xmax: 67.3,
    bbox_ymax: 25.1,
  },
  {
    id: "alert-2",
    category: "Geo",
    event: "Earthquake Advisory",
    severity: "Moderate",
    urgency: "Expected",
    description: "Minor aftershocks may continue around Quetta.",
    instruction: "Inspect buildings for structural damage.",
    source: "PMD",
    url: "https://example.com/alerts/2",
    effective_from: "2026-05-04T08:00:00.000Z",
    effective_until: "2026-05-05T20:00:00.000Z",
    posted_date: "2026-05-04T07:45:00.000Z",
    affected_places: ["Quetta", "Balochistan"],
    centroid_lat: 30.1798,
    centroid_lng: 66.975,
    bbox_xmin: 66.7,
    bbox_ymin: 29.9,
    bbox_xmax: 67.2,
    bbox_ymax: 30.4,
  },
  {
    id: "alert-3",
    category: "Met",
    event: "Heatwave Watch",
    severity: "Severe",
    urgency: "Expected",
    description: "High temperatures expected in Lahore over the next two days.",
    instruction: "Limit outdoor activity during afternoon hours.",
    source: "NDMA",
    url: "https://example.com/alerts/3",
    effective_from: "2026-05-03T06:00:00.000Z",
    effective_until: "2026-05-07T18:00:00.000Z",
    posted_date: "2026-05-03T05:30:00.000Z",
    affected_places: ["Lahore", "Punjab"],
    centroid_lat: 31.5204,
    centroid_lng: 74.3587,
    bbox_xmin: 74.1,
    bbox_ymin: 31.2,
    bbox_xmax: 74.6,
    bbox_ymax: 31.8,
  },
];

const geometryFixture = {
  type: "Polygon",
  coordinates: [[
    [66.8, 24.6],
    [67.3, 24.6],
    [67.3, 25.1],
    [66.8, 25.1],
    [66.8, 24.6],
  ]],
};

function filterAlerts(alerts: AlertFixture[], filters: Record<string, unknown>): AlertFixture[] {
  const searchQuery = String(filters.search_query ?? "").trim().toLowerCase();
  const categoryFilter = String(filters.category_filter ?? "").trim();
  const severityFilter = String(filters.severity_filter ?? "").trim();
  const urgencyFilter = String(filters.urgency_filter ?? "").trim();
  const dateStart = String(filters.date_start ?? "").trim();
  const dateEnd = String(filters.date_end ?? "").trim();
  const sortBy = String(filters.sort_by ?? "posted_date");
  const sortOrder = String(filters.sort_order ?? "desc");

  const startMs = dateStart ? Date.parse(dateStart) : null;
  const endMs = dateEnd ? Date.parse(dateEnd) : null;

  const filtered = alerts.filter((alert) => {
    if (categoryFilter && alert.category !== categoryFilter) {
      return false;
    }

    if (severityFilter && alert.severity !== severityFilter) {
      return false;
    }

    if (urgencyFilter && alert.urgency !== urgencyFilter) {
      return false;
    }

    if (searchQuery) {
      const haystack = [
        alert.event,
        alert.description,
        alert.source,
        ...(alert.affected_places ?? []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      if (!haystack.includes(searchQuery)) {
        return false;
      }
    }

    if (startMs !== null || endMs !== null) {
      const effectiveFromMs = alert.effective_from ? Date.parse(alert.effective_from) : null;
      if (effectiveFromMs === null) {
        return false;
      }
      if (startMs !== null && effectiveFromMs < startMs) {
        return false;
      }
      if (endMs !== null && effectiveFromMs > endMs) {
        return false;
      }
    }

    return true;
  });

  return filtered.sort((left, right) => {
    const leftValue = left[sortBy as keyof AlertFixture];
    const rightValue = right[sortBy as keyof AlertFixture];
    const leftComparable = typeof leftValue === "string" ? leftValue : "";
    const rightComparable = typeof rightValue === "string" ? rightValue : "";
    const comparison = leftComparable.localeCompare(rightComparable);
    return sortOrder === "asc" ? comparison : comparison * -1;
  });
}

function mockSupabaseRpc(options?: {
  alerts?: AlertFixture[];
  alertsMode?: "success" | "network-error";
}) {
  const alerts = options?.alerts ?? baseAlerts;
  const alertsMode = options?.alertsMode ?? "success";

  cy.intercept("**/rest/v1/rpc/get_alerts", (req) => {
    if (req.method === "OPTIONS") {
      req.reply({ statusCode: 200, body: {} });
      return;
    }

    if (alertsMode === "network-error") {
      req.reply({ forceNetworkError: true });
      return;
    }

    const filters =
      req.body && typeof req.body === "object"
        ? (req.body as Record<string, unknown>)
        : {};

    req.reply({
      statusCode: 200,
      body: filterAlerts(alerts, filters),
    });
  }).as("getAlerts");

  cy.intercept("**/rest/v1/rpc/get_alert_geometry", (req) => {
    if (req.method === "OPTIONS") {
      req.reply({ statusCode: 200, body: {} });
      return;
    }

    req.reply({
      statusCode: 200,
      body: geometryFixture,
    });
  }).as("getAlertGeometry");
}

function visitDashboard() {
  cy.visit("/");
  cy.wait("@getAlerts");

  cy.get('[data-testid="user-guide"]').should("be.visible");
  cy.get('[data-testid="user-guide-close"]').click();
  cy.get('[data-testid="user-guide"]').should("not.be.visible");

  cy.get('[data-testid="navbar-filter-toggle"]').click();
  cy.get('[data-testid="alerts-panel"]').should("be.visible");
}

function expandFilters() {
  cy.get('[data-testid="filters-toggle"]').click();
  cy.get('[data-testid="filter-category"]').should("be.visible");
}

function setDateInput(testId: string, value: string) {
  cy.get(`[data-testid="${testId}"]`)
    .invoke("val", value)
    .trigger("change", { force: true });
}

describe("REACH Dashboard E2E Tests", () => {
  beforeEach(() => {
    mockSupabaseRpc();
    visitDashboard();
  });

  describe("ST-001: Dashboard Loading", () => {
    it("loads the dashboard and renders the map with alerts", () => {
      cy.get('[data-testid="map-container"]').should("be.visible");
      cy.get('[data-testid="alert-list"]').should("be.visible");
      cy.get('[data-testid="alert-item"]').should("have.length", 3);
    });
  });

  describe("ST-002: Filter by Category", () => {
    it("filters alerts by category after expanding the hidden filters", () => {
      expandFilters();

      cy.get('[data-testid="filter-category"]').select("Met");
      cy.wait("@getAlerts");

      cy.get('[data-testid="alert-item"]').should("have.length", 2);
      cy.get('[data-testid="alert-item"]').each(($item) => {
        expect($item.attr("data-category")).to.equal("Met");
      });
    });
  });

  describe("ST-003: Filter by Severity", () => {
    it("filters alerts by severity with the current single-select control", () => {
      expandFilters();

      cy.get('[data-testid="filter-severity"]').select("Extreme");
      cy.wait("@getAlerts");

      cy.get('[data-testid="alert-item"]').should("have.length", 1);
      cy.get('[data-testid="alert-item"]')
        .first()
        .should("have.attr", "data-severity", "Extreme");
    });
  });

  describe("ST-004: Search by Location", () => {
    it("searches alerts from the merged filter/search panel", () => {
      cy.get('[data-testid="search-input"]').type("Lahore");
      cy.wait("@getAlerts");

      cy.get('[data-testid="alert-item"]').should("have.length", 1);
      cy.get('[data-testid="alert-item"]')
        .first()
        .should("have.attr", "data-location")
        .and("include", "Lahore");
    });

    it("restores the full list when the search is cleared", () => {
      cy.get('[data-testid="search-input"]').type("Lahore");
      cy.wait("@getAlerts");

      cy.get('[data-testid="search-clear"]').click();
      cy.wait("@getAlerts");

      cy.get('[data-testid="alert-item"]').should("have.length", 3);
    });
  });

  describe("ST-005: Date Range Filter", () => {
    it("filters alerts by date after expanding the hidden advanced controls", () => {
      expandFilters();

      setDateInput("date-start", "2026-05-04");
      cy.wait("@getAlerts");

      setDateInput("date-end", "2026-05-05");
      cy.wait("@getAlerts");

      cy.get('[data-testid="alert-item"]').should("have.length", 2);
    });

    it("shows the empty-state message when the date range matches nothing", () => {
      expandFilters();

      setDateInput("date-start", "2026-05-06");
      cy.wait("@getAlerts");

      setDateInput("date-end", "2026-05-07");
      cy.wait("@getAlerts");

      cy.get('[data-testid="no-results"]').should("be.visible");
    });
  });

  describe("ST-006: View Alert Detail Card", () => {
    it("opens and closes the detail card for an alert", () => {
      cy.get('[data-testid="alert-item"]').first().click();
      cy.wait("@getAlertGeometry");

      cy.get('[data-testid="detail-panel"]').should("be.visible");
      cy.get('[data-testid="alert-title"]').should("contain", "Flash Flood Warning");
      cy.get('[data-testid="alert-severity"]').should("contain", "Extreme");
      cy.get('[data-testid="alert-description"]').should("contain", "Karachi");
      cy.get('[data-testid="alert-source"]').should("contain", "NDMA");
      cy.get('[data-testid="affected-area-item"]').first().should("contain", "Karachi");

      cy.get('[data-testid="detail-close"]').click();
      cy.get('[data-testid="detail-panel"]').should("not.be.visible");
    });
  });

  describe("Error Handling", () => {
    it("shows an error message when alert loading fails", () => {
      mockSupabaseRpc({ alertsMode: "network-error" });
      cy.visit("/");

      cy.get('[data-testid="user-guide-close"]').click();
      cy.get('[data-testid="navbar-filter-toggle"]').click();
      cy.get('[data-testid="error-message"]').should("be.visible");
    });

    it("shows the empty-state message when the RPC returns no alerts", () => {
      mockSupabaseRpc({ alerts: [] });
      cy.visit("/");
      cy.wait("@getAlerts");

      cy.get('[data-testid="user-guide-close"]').click();
      cy.get('[data-testid="navbar-filter-toggle"]').click();
      cy.get('[data-testid="no-results"]').should("be.visible");
    });
  });
});
