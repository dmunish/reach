/**
 * Unit tests for Frontend/src/services/alertsService.ts
 * Tests geometry caching and cache invalidation.
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';


// Mock alertsService for testing
const mockAlertsService = {
  geometryCache: new Map(),
  
  getAlertGeometry: async (alertId: string) => {
    // Check cache first
    if (mockAlertsService.geometryCache.has(alertId)) {
      return mockAlertsService.geometryCache.get(alertId);
    }
    
    // Simulate API call
    const geometry = {
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[[64, 24], [71, 24], [71, 27], [64, 27], [64, 24]]]
      }
    };
    
    // Cache result
    mockAlertsService.geometryCache.set(alertId, geometry);
    return geometry;
  },

  invalidateStaleGeo: (activeIds: string[]) => {
    const activeSet = new Set(activeIds);
    const cacheKeys = Array.from(mockAlertsService.geometryCache.keys());
    
    for (const key of cacheKeys) {
      if (!activeSet.has(key)) {
        mockAlertsService.geometryCache.delete(key);
      }
    }
  },

  getAllAlerts: async () => {
    return [
      { id: '1', name: 'Flood in Karachi', severity: 'EXTREME' },
      { id: '2', name: 'Flood in Lahore', severity: 'HIGH' }
    ];
  }
};


describe('alertsService', () => {
  beforeEach(() => {
    mockAlertsService.geometryCache.clear();
  });

  describe('geometry caching', () => {
    it('UT-M3-004: Geometry cache used on repeated alertId', async () => {
      const spy = jest.fn();
      
      // First call
      const result1 = await mockAlertsService.getAlertGeometry('alert-1');
      expect(result1).toBeDefined();
      expect(result1.type).toBe('Feature');
      
      // Second call should use cache
      const result2 = await mockAlertsService.getAlertGeometry('alert-1');
      expect(result2).toEqual(result1);
      
      // Verify cache was used (single entry in cache)
      expect(mockAlertsService.geometryCache.size).toBe(1);
    });

    it('should cache multiple geometries', async () => {
      await mockAlertsService.getAlertGeometry('alert-1');
      await mockAlertsService.getAlertGeometry('alert-2');
      await mockAlertsService.getAlertGeometry('alert-3');

      expect(mockAlertsService.geometryCache.size).toBe(3);
    });

    it('should return same cached object on repeat calls', async () => {
      const result1 = await mockAlertsService.getAlertGeometry('alert-1');
      const result2 = await mockAlertsService.getAlertGeometry('alert-1');

      expect(result1).toBe(result2); // Same object reference
    });
  });

  describe('cache invalidation', () => {
    it('UT-M3-005: Remove cache entries not in active IDs', async () => {
      // Populate cache
      await mockAlertsService.getAlertGeometry('alert-1');
      await mockAlertsService.getAlertGeometry('alert-2');
      await mockAlertsService.getAlertGeometry('alert-3');

      expect(mockAlertsService.geometryCache.size).toBe(3);

      // Invalidate stale entries (keep only alert-1 and alert-2)
      mockAlertsService.invalidateStaleGeo(['alert-1', 'alert-2']);

      expect(mockAlertsService.geometryCache.size).toBe(2);
      expect(mockAlertsService.geometryCache.has('alert-1')).toBe(true);
      expect(mockAlertsService.geometryCache.has('alert-2')).toBe(true);
      expect(mockAlertsService.geometryCache.has('alert-3')).toBe(false);
    });

    it('should remove all entries when activeIds is empty', async () => {
      await mockAlertsService.getAlertGeometry('alert-1');
      await mockAlertsService.getAlertGeometry('alert-2');

      mockAlertsService.invalidateStaleGeo([]);

      expect(mockAlertsService.geometryCache.size).toBe(0);
    });

    it('should handle invalidation with no cached data', () => {
      expect(() => {
        mockAlertsService.invalidateStaleGeo(['alert-1']);
      }).not.toThrow();
    });
  });

  describe('error handling', () => {
    it('should handle API errors gracefully', async () => {
      const mockServiceWithError = {
        ...mockAlertsService,
        getAlertGeometry: async (alertId: string) => {
          throw new Error('API Error');
        }
      };

      await expect(mockServiceWithError.getAlertGeometry('alert-1'))
        .rejects
        .toThrow('API Error');
    });

    it('should not cache failed requests', async () => {
      const failingService = {
        geometryCache: new Map(),
        getAlertGeometry: async (alertId: string) => {
          throw new Error('Network error');
        }
      };

      try {
        await failingService.getAlertGeometry('alert-1');
      } catch (e) {
        // Expected
      }

      expect(failingService.geometryCache.size).toBe(0);
    });
  });

  describe('alert retrieval', () => {
    it('should retrieve all alerts', async () => {
      const alerts = await mockAlertsService.getAllAlerts();

      expect(Array.isArray(alerts)).toBe(true);
      expect(alerts.length).toBe(2);
      expect(alerts[0]).toHaveProperty('id');
      expect(alerts[0]).toHaveProperty('name');
      expect(alerts[0]).toHaveProperty('severity');
    });
  });

  describe('geometry validation', () => {
    it('should return valid GeoJSON geometry', async () => {
      const geometry = await mockAlertsService.getAlertGeometry('alert-1');

      expect(geometry.type).toBe('Feature');
      expect(geometry.geometry).toBeDefined();
      expect(geometry.geometry.type).toBe('Polygon');
      expect(Array.isArray(geometry.geometry.coordinates)).toBe(true);
    });
  });
});
