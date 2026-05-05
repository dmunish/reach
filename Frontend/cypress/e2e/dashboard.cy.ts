/**
 * System E2E tests using Cypress
 * Tests dashboard functionality: loading, filtering, searching, date selection
 */

describe('REACH Dashboard E2E Tests', () => {
  beforeEach(() => {
    // Mock API responses
    cy.intercept('GET', '/api/v1/alerts*', {
      statusCode: 200,
      body: {
        results: [
          {
            id: '1',
            alert_type: 'FLOOD',
            severity: 'EXTREME',
            description: 'Flash flooding in Karachi',
            location: 'Karachi',
            issue_date: '2026-05-05T10:00:00Z',
            source: 'NDMA'
          },
          {
            id: '2',
            alert_type: 'FLOOD',
            severity: 'HIGH',
            description: 'Flood warning for Lahore',
            location: 'Lahore',
            issue_date: '2026-05-04T15:30:00Z',
            source: 'NDMA'
          },
          {
            id: '3',
            alert_type: 'EARTHQUAKE',
            severity: 'MODERATE',
            description: 'Minor earthquake in Peshawar',
            location: 'Peshawar',
            issue_date: '2026-05-03T08:00:00Z',
            source: 'PMD'
          }
        ],
        errors: []
      }
    }).as('getAlerts');

    cy.intercept('GET', '/api/v1/geometry*', {
      statusCode: 200,
      body: {
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [64, 24], [71, 24], [71, 27], [64, 27], [64, 24]
          ]]
        }
      }
    }).as('getGeometry');

    cy.visit('/');
  });

  describe('ST-001: Dashboard Loading', () => {
    it('should load dashboard and render map with alerts', () => {
      // Wait for API call
      cy.wait('@getAlerts');

      // Check map container exists
      cy.get('[data-testid="map-container"]')
        .should('be.visible');

      // Check alert list exists and has items
      cy.get('[data-testid="alert-list"]')
        .children()
        .should('have.length.greaterThan', 0);

      // Check no console errors
      cy.on('uncaught:exception', (err) => {
        expect(err).not.to.exist;
      });
    });

    it('should display alert summary on dashboard', () => {
      cy.wait('@getAlerts');

      // Check alert cards are visible
      cy.get('[data-testid="alert-item"]')
        .should('be.visible')
        .should('have.length', 3);
    });
  });

  describe('ST-002: Filter by Disaster Type', () => {
    it('should filter alerts by Flood category', () => {
      cy.wait('@getAlerts');

      // Open filter menu
      cy.get('[data-testid="filter-category"]')
        .click();

      // Select Flood
      cy.contains('Flood')
        .click();

      // Check only Flood alerts remain
      cy.get('[data-testid="alert-item"]')
        .each(($el) => {
          cy.wrap($el)
            .should('contain', 'FLOOD');
        });
    });

    it('should display all categories when no filter applied', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="alert-item"]')
        .should('have.length', 3);
    });

    it('should update map when filter changes', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="filter-category"]')
        .click();

      cy.contains('Flood')
        .click();

      // Map should still be visible
      cy.get('[data-testid="map-container"]')
        .should('be.visible');
    });
  });

  describe('ST-003: Filter by Severity', () => {
    it('should filter alerts by Severe+Extreme', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="filter-severity"]')
        .click();

      cy.get('[data-testid="severity-option"]')
        .filter(':contains("Extreme")')
        .click();

      cy.get('[data-testid="severity-option"]')
        .filter(':contains("High")')
        .click();

      // Check displayed alerts have correct severity
      cy.get('[data-testid="alert-item"]')
        .each(($el) => {
          const severity = cy.wrap($el)
            .find('[data-severity]')
            .invoke('attr', 'data-severity');

          cy.wrap(severity).should('match', /EXTREME|HIGH|SEVERE/);
        });
    });

    it('should maintain other filters when applying severity', () => {
      cy.wait('@getAlerts');

      // Apply category filter
      cy.get('[data-testid="filter-category"]')
        .click();
      cy.contains('Flood')
        .click();

      // Apply severity filter
      cy.get('[data-testid="filter-severity"]')
        .click();

      cy.get('[data-testid="severity-option"]')
        .filter(':contains("Extreme")')
        .click();

      // Should still show Flood alerts
      cy.get('[data-testid="alert-item"]')
        .should('contain', 'FLOOD');
    });
  });

  describe('ST-004: Search by Location', () => {
    it('should search and find alerts by location', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="search-input"]')
        .type('Lahore');

      cy.get('[data-testid="search-button"]')
        .click();

      // Map should center on searched location
      cy.get('[data-testid="map-container"]')
        .should('be.visible');

      // Alert list should narrow to Lahore
      cy.get('[data-testid="alert-item"]')
        .first()
        .should('contain', 'Lahore');
    });

    it('should clear search results when cleared', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="search-input"]')
        .type('Lahore');

      cy.get('[data-testid="search-button"]')
        .click();

      // Clear search
      cy.get('[data-testid="search-clear"]')
        .click();

      // Should show all alerts again
      cy.get('[data-testid="alert-item"]')
        .should('have.length', 3);
    });
  });

  describe('ST-005: Date Range Filter', () => {
    it('should filter alerts by date range', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="date-start"]')
        .type('2026-05-04');

      cy.get('[data-testid="date-end"]')
        .type('2026-05-05');

      cy.contains('Apply')
        .click();

      // Should show alerts within date range
      cy.get('[data-testid="alert-item"]')
        .should('have.length.greaterThan', 0);
    });

    it('should handle date range that contains no alerts', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="date-start"]')
        .type('2026-06-01');

      cy.get('[data-testid="date-end"]')
        .type('2026-06-05');

      cy.contains('Apply')
        .click();

      // Should show "no results" message
      cy.get('[data-testid="no-results"]')
        .should('be.visible');
    });
  });

  describe('ST-006: View Alert Detail Card', () => {
    it('should display alert details when clicked', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="alert-item"]')
        .first()
        .click();

      // Detail panel should be visible
      cy.get('[data-testid="detail-panel"]')
        .should('be.visible');

      // Check detail content
      cy.get('[data-testid="alert-title"]')
        .should('not.be.empty');

      cy.get('[data-testid="alert-severity"]')
        .should('not.be.empty');

      cy.get('[data-testid="alert-description"]')
        .should('not.be.empty');
    });

    it('should close detail panel when close button clicked', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="alert-item"]')
        .first()
        .click();

      cy.get('[data-testid="detail-panel"]')
        .should('be.visible');

      cy.get('[data-testid="detail-close"]')
        .click();

      cy.get('[data-testid="detail-panel"]')
        .should('not.be.visible');
    });

    it('should show all required fields in detail view', () => {
      cy.wait('@getAlerts');

      cy.get('[data-testid="alert-item"]')
        .first()
        .click();

      cy.get('[data-testid="detail-panel"]')
        .within(() => {
          cy.get('[data-testid="alert-title"]').should('exist');
          cy.get('[data-testid="alert-severity"]').should('exist');
          cy.get('[data-testid="alert-location"]').should('exist');
          cy.get('[data-testid="alert-source"]').should('exist');
          cy.get('[data-testid="alert-date"]').should('exist');
        });
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', () => {
      cy.intercept('GET', '/api/v1/alerts*', {
        statusCode: 500,
        body: { error: 'Internal server error' }
      }).as('getAlertsError');

      cy.visit('/');
      cy.wait('@getAlertsError');

      cy.get('[data-testid="error-message"]')
        .should('be.visible')
        .should('contain', 'Unable to load alerts');
    });

    it('should handle empty alert results', () => {
      cy.intercept('GET', '/api/v1/alerts*', {
        statusCode: 200,
        body: {
          results: [],
          errors: []
        }
      }).as('getEmptyAlerts');

      cy.visit('/');
      cy.wait('@getEmptyAlerts');

      cy.get('[data-testid="no-results"]')
        .should('be.visible');
    });
  });
});
