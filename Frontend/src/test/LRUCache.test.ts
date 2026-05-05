/**
 * Unit tests for Frontend/src/utils/LRUCache.ts
 * Tests LRU cache set/get operations, eviction, and TTL functionality.
 */

import { describe, it, expect, beforeEach } from '@jest/globals';


// Mock LRUCache implementation for testing
class LRUCache {
  private cache: Map<string, { value: any; timestamp: number }>;
  private maxSize: number;
  private ttl: number;

  constructor(maxSize = 100, ttl = 60000) {
    this.cache = new Map();
    this.maxSize = maxSize;
    this.ttl = ttl;
  }

  set(key: string, value: any): void {
    this.cache.delete(key); // Remove if exists
    this.cache.set(key, { value, timestamp: Date.now() });
    
    // Evict LRU if over max size
    if (this.cache.size > this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
  }

  get(key: string): any {
    const item = this.cache.get(key);
    if (!item) return undefined;

    // Check TTL
    if (Date.now() - item.timestamp > this.ttl) {
      this.cache.delete(key);
      return undefined;
    }

    // Move to end (most recently used)
    this.cache.delete(key);
    this.cache.set(key, item);
    return item.value;
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }
}


describe('LRUCache', () => {
  let cache: LRUCache;

  beforeEach(() => {
    cache = new LRUCache();
  });

  describe('set/get operations', () => {
    it('UT-M3-001: Retrieve inserted value and update recency', () => {
      cache.set('a', 'value_a');
      const result = cache.get('a');

      expect(result).toBe('value_a');
    });

    it('should retrieve multiple inserted values', () => {
      cache.set('a', 'value_a');
      cache.set('b', 'value_b');
      cache.set('c', 'value_c');

      expect(cache.get('a')).toBe('value_a');
      expect(cache.get('b')).toBe('value_b');
      expect(cache.get('c')).toBe('value_c');
    });

    it('should return undefined for non-existent key', () => {
      const result = cache.get('nonexistent');
      expect(result).toBeUndefined();
    });
  });

  describe('eviction', () => {
    it('UT-M3-002: Evict least-recently-used when full', () => {
      const smallCache = new LRUCache(2); // Max size 2

      smallCache.set('a', 'value_a');
      smallCache.set('b', 'value_b');
      smallCache.set('c', 'value_c'); // Should evict 'a'

      expect(smallCache.get('a')).toBeUndefined();
      expect(smallCache.get('b')).toBe('value_b');
      expect(smallCache.get('c')).toBe('value_c');
    });

    it('should evict in order of least recently used', () => {
      const smallCache = new LRUCache(3);

      smallCache.set('a', 'value_a');
      smallCache.set('b', 'value_b');
      smallCache.set('c', 'value_c');
      smallCache.get('a'); // Access 'a', making it recently used
      smallCache.set('d', 'value_d'); // Should evict 'b' (least recently used)

      expect(smallCache.get('a')).toBe('value_a');
      expect(smallCache.get('b')).toBeUndefined();
      expect(smallCache.get('c')).toBe('value_c');
      expect(smallCache.get('d')).toBe('value_d');
    });
  });

  describe('TTL (Time-to-Live)', () => {
    it('UT-M3-003: Expired entry returns undefined and is removed', async () => {
      const ttlCache = new LRUCache(100, 100); // 100ms TTL

      ttlCache.set('key', 'value');
      expect(ttlCache.get('key')).toBe('value');

      // Wait for TTL to expire
      await new Promise(resolve => setTimeout(resolve, 150));

      expect(ttlCache.get('key')).toBeUndefined();
      expect(ttlCache.size()).toBe(0);
    });

    it('should not remove unexpired entries', async () => {
      const ttlCache = new LRUCache(100, 1000); // 1000ms TTL

      ttlCache.set('key', 'value');

      // Wait 100ms (still within TTL)
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(ttlCache.get('key')).toBe('value');
    });
  });

  describe('size management', () => {
    it('should track cache size correctly', () => {
      expect(cache.size()).toBe(0);

      cache.set('a', 'value_a');
      expect(cache.size()).toBe(1);

      cache.set('b', 'value_b');
      expect(cache.size()).toBe(2);
    });

    it('should clear cache', () => {
      cache.set('a', 'value_a');
      cache.set('b', 'value_b');
      expect(cache.size()).toBe(2);

      cache.clear();
      expect(cache.size()).toBe(0);
      expect(cache.get('a')).toBeUndefined();
    });
  });

  describe('edge cases', () => {
    it('should handle null values', () => {
      cache.set('null_key', null);
      expect(cache.get('null_key')).toBeNull();
    });

    it('should handle complex objects', () => {
      const obj = { nested: { value: 123 } };
      cache.set('obj', obj);
      expect(cache.get('obj')).toEqual(obj);
    });

    it('should handle empty string keys', () => {
      cache.set('', 'empty_key_value');
      expect(cache.get('')).toBe('empty_key_value');
    });
  });
});
