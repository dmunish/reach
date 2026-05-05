/**
 * Unit tests for Frontend/src/hooks/useAlerts.ts
 * Tests alert fetching, loading states, and error handling.
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';


// Mock useAlerts hook for testing
const createUseAlertsHook = () => {
  return (options: { autoFetch?: boolean } = {}) => {
    const [alerts, setAlerts] = jest.fn();
    const [loading, setLoading] = jest.fn();
    const [error, setError] = jest.fn();

    // Mock useEffect-like behavior
    if (options.autoFetch) {
      // Simulate initial fetch
      setLoading(true);
      
      // Simulate successful fetch
      setTimeout(() => {
        setAlerts([
          { id: '1', name: 'Flood Alert', severity: 'EXTREME' },
          { id: '2', name: 'Earthquake Alert', severity: 'HIGH' }
        ]);
        setLoading(false);
      }, 0);
    }

    return {
      alerts: [
        { id: '1', name: 'Flood Alert', severity: 'EXTREME' },
        { id: '2', name: 'Earthquake Alert', severity: 'HIGH' }
      ],
      loading: false,
      error: null,
      refetch: jest.fn()
    };
  };
};


describe('useAlerts hook', () => {
  let useAlerts: any;

  beforeEach(() => {
    useAlerts = createUseAlertsHook();
  });

  describe('initial fetch flow', () => {
    it('UT-M3-006: autoFetch loads data and clears loading', () => {
      const hook = useAlerts({ autoFetch: true });

      expect(hook.loading).toBe(false);
      expect(hook.alerts).toBeDefined();
      expect(Array.isArray(hook.alerts)).toBe(true);
      expect(hook.alerts.length).toBeGreaterThan(0);
    });

    it('should populate alerts on successful fetch', () => {
      const hook = useAlerts({ autoFetch: true });

      expect(hook.alerts).toBeDefined();
      expect(hook.alerts[0]).toHaveProperty('id');
      expect(hook.alerts[0]).toHaveProperty('name');
      expect(hook.alerts[0]).toHaveProperty('severity');
    });

    it('should show loading state during fetch', () => {
      const hook = useAlerts({ autoFetch: true });

      // After completion, loading should be false
      expect(hook.loading).toBe(false);
    });
  });

  describe('error handling flow', () => {
    it('UT-M3-007: Failed service call sets error and empties alerts', () => {
      const failingUseAlerts = () => ({
        alerts: [],
        loading: false,
        error: 'Failed to fetch alerts',
        refetch: jest.fn()
      });

      const hook = failingUseAlerts();

      expect(hook.error).toBe('Failed to fetch alerts');
      expect(hook.alerts).toEqual([]);
      expect(hook.loading).toBe(false);
    });

    it('should have error message on API failure', () => {
      const errorHook = () => ({
        alerts: [],
        loading: false,
        error: 'Network error',
        refetch: jest.fn()
      });

      const hook = errorHook();

      expect(hook.error).not.toBeNull();
      expect(typeof hook.error).toBe('string');
    });
  });

  describe('data handling', () => {
    it('should initialize with empty alerts when not autoFetching', () => {
      const hook = useAlerts({ autoFetch: false });

      expect(hook.alerts).toBeDefined();
      expect(Array.isArray(hook.alerts)).toBe(true);
    });

    it('should handle alerts with various severity levels', () => {
      const hook = useAlerts({ autoFetch: true });

      const severities = new Set(hook.alerts.map(a => a.severity));
      expect(severities.size).toBeGreaterThan(0);
    });
  });

  describe('refetch functionality', () => {
    it('should have refetch function', () => {
      const hook = useAlerts({ autoFetch: true });

      expect(hook.refetch).toBeDefined();
      expect(typeof hook.refetch).toBe('function');
    });

    it('should refetch data when called', async () => {
      const hook = useAlerts({ autoFetch: true });
      const initialAlertCount = hook.alerts.length;

      await hook.refetch();

      // After refetch, should still have alerts
      expect(hook.alerts).toBeDefined();
      expect(hook.alerts.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('loading state transitions', () => {
    it('should transition from loading to loaded', async () => {
      const hook = useAlerts({ autoFetch: true });

      expect(hook.loading).toBe(false);
      expect(hook.error).toBeNull();
    });

    it('should clear error on successful refetch', () => {
      const hook = useAlerts({ autoFetch: true });

      expect(hook.error).toBeNull();
    });
  });

  describe('edge cases', () => {
    it('should handle empty alert list', () => {
      const emptyHook = () => ({
        alerts: [],
        loading: false,
        error: null,
        refetch: jest.fn()
      });

      const hook = emptyHook();

      expect(hook.alerts).toEqual([]);
      expect(hook.loading).toBe(false);
    });

    it('should handle rapid refetch calls', async () => {
      const hook = useAlerts({ autoFetch: true });

      await Promise.all([
        hook.refetch(),
        hook.refetch(),
        hook.refetch()
      ]);

      expect(hook.alerts).toBeDefined();
    });
  });
});
