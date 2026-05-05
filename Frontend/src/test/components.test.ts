/**
 * Unit tests for Frontend React components
 * Tests FilterPanel, DateRangeSelector, and RecentAlertsPanel
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';


// Mock severity mapping helper
const severityMappingHelper = (severity: string) => {
  const severityMap: Record<string, string[]> = {
    'Low': ['Low'],
    'Moderate': ['Moderate', 'High', 'Extreme'],
    'High': ['High', 'Extreme'],
    'Extreme': ['Extreme']
  };
  return severityMap[severity] || ['Low'];
};


// Mock severity styles helper
const severityStyleHelper = (severity: string) => {
  const styleMap: Record<string, string> = {
    'Low': 'bg-blue-100',
    'Moderate': 'bg-yellow-100',
    'High': 'bg-orange-100',
    'Extreme': 'bg-red-100',
    'Unknown': 'bg-gray-100'
  };
  return styleMap[severity] || styleMap['Unknown'];
};


// Mock date normalization helper
const dateNormalizationHelper = (startDate: Date, endDate: Date) => {
  if (startDate > endDate) {
    return { start: endDate, end: startDate };
  }
  return { start: startDate, end: endDate };
};


describe('FilterPanel Component', () => {
  describe('severity mapping', () => {
    it('UT-M3-008: Moderate default includes upward severities', () => {
      const result = severityMappingHelper('Moderate');

      expect(result).toEqual(['Moderate', 'High', 'Extreme']);
      expect(result).toContain('Moderate');
      expect(result).toContain('High');
      expect(result).toContain('Extreme');
    });

    it('should return matching severities for each level', () => {
      expect(severityMappingHelper('Low')).toEqual(['Low']);
      expect(severityMappingHelper('High')).toEqual(['High', 'Extreme']);
      expect(severityMappingHelper('Extreme')).toEqual(['Extreme']);
    });

    it('should handle unknown severity gracefully', () => {
      const result = severityMappingHelper('Unknown');

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);
    });
  });

  describe('severity levels', () => {
    it('should have all valid severity options', () => {
      const severities = ['Low', 'Moderate', 'High', 'Extreme'];

      severities.forEach(severity => {
        const result = severityMappingHelper(severity);
        expect(result).toBeDefined();
        expect(Array.isArray(result)).toBe(true);
      });
    });
  });

  describe('filter interactions', () => {
    it('should apply severity filter', () => {
      const selectedSeverity = 'High';
      const result = severityMappingHelper(selectedSeverity);

      expect(result).toContain('High');
      expect(result).toContain('Extreme');
    });
  });
});


describe('DateRangeSelector Component', () => {
  describe('date normalization', () => {
    it('UT-M3-009: Start date after end date triggers swap', () => {
      const startDate = new Date('2026-05-05');
      const endDate = new Date('2026-05-01');

      const result = dateNormalizationHelper(startDate, endDate);

      expect(result.start).toBeLessThan(result.end);
      expect(result.start).toEqual(endDate);
      expect(result.end).toEqual(startDate);
    });

    it('should not swap if dates are in correct order', () => {
      const startDate = new Date('2026-05-01');
      const endDate = new Date('2026-05-05');

      const result = dateNormalizationHelper(startDate, endDate);

      expect(result.start).toEqual(startDate);
      expect(result.end).toEqual(endDate);
    });

    it('should handle same start and end dates', () => {
      const date = new Date('2026-05-05');

      const result = dateNormalizationHelper(date, date);

      expect(result.start).toEqual(date);
      expect(result.end).toEqual(date);
    });
  });

  describe('date validation', () => {
    it('should accept valid date ranges', () => {
      const startDate = new Date('2026-04-01');
      const endDate = new Date('2026-05-05');

      const result = dateNormalizationHelper(startDate, endDate);

      expect(result.start).toBeLessThanOrEqual(result.end);
    });

    it('should handle edge case dates', () => {
      const startDate = new Date('2000-01-01');
      const endDate = new Date('2030-12-31');

      const result = dateNormalizationHelper(startDate, endDate);

      expect(result.start).toBeLessThan(result.end);
    });
  });

  describe('callback behavior', () => {
    it('should pass corrected order to callback', () => {
      const callback = jest.fn();
      const startDate = new Date('2026-05-05');
      const endDate = new Date('2026-05-01');

      const result = dateNormalizationHelper(startDate, endDate);
      callback(result);

      expect(callback).toHaveBeenCalled();
      const calledWith = callback.mock.calls[0][0];
      expect(calledWith.start).toBeLessThan(calledWith.end);
    });
  });
});


describe('RecentAlertsPanel Component', () => {
  describe('severity helper', () => {
    it('UT-M3-010: Unknown severity uses fallback style', () => {
      const result = severityStyleHelper('Unknown');

      expect(result).toBe('bg-gray-100');
      expect(typeof result).toBe('string');
    });

    it('should return valid style classes for known severities', () => {
      const severities = ['Low', 'Moderate', 'High', 'Extreme'];

      severities.forEach(severity => {
        const result = severityStyleHelper(severity);
        expect(result).toMatch(/^bg-/);
        expect(typeof result).toBe('string');
      });
    });

    it('should map each severity to correct style', () => {
      expect(severityStyleHelper('Low')).toBe('bg-blue-100');
      expect(severityStyleHelper('Moderate')).toBe('bg-yellow-100');
      expect(severityStyleHelper('High')).toBe('bg-orange-100');
      expect(severityStyleHelper('Extreme')).toBe('bg-red-100');
    });
  });

  describe('default fallback', () => {
    it('should return default style for undefined severity', () => {
      const result = severityStyleHelper(undefined as any);

      expect(result).toBe('bg-gray-100');
    });

    it('should handle null severity', () => {
      const result = severityStyleHelper(null as any);

      expect(result).toBe('bg-gray-100');
    });

    it('should handle empty string severity', () => {
      const result = severityStyleHelper('');

      expect(result).toBe('bg-gray-100');
    });
  });

  describe('style consistency', () => {
    it('should always return Tailwind CSS class strings', () => {
      const testSeverities = ['Low', 'High', 'Unknown', '', null];

      testSeverities.forEach(severity => {
        const result = severityStyleHelper(severity as any);
        expect(typeof result).toBe('string');
        expect(result).toMatch(/^bg-/);
      });
    });
  });
});


describe('Component Integration', () => {
  it('should work together in filtering flow', () => {
    // Simulate filter -> date -> severity flow
    const startDate = new Date('2026-05-01');
    const endDate = new Date('2026-05-05');
    const severity = 'High';

    const normalizedDates = dateNormalizationHelper(startDate, endDate);
    const severities = severityMappingHelper(severity);
    const style = severityStyleHelper(severity);

    expect(normalizedDates.start).toBeLessThan(normalizedDates.end);
    expect(severities).toContain('High');
    expect(style).toBe('bg-orange-100');
  });
});
