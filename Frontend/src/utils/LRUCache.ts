/**
 * LRU (Least Recently Used) Cache implementation with TTL support
 * Prevents memory leaks by limiting cache size and expiring old entries
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  accessCount: number;
}

export class LRUCache<K, V> {
  private cache = new Map<K, CacheEntry<V>>();
  private maxSize: number;
  private ttl: number; // Time to live in milliseconds

  constructor(maxSize = 100, ttl = 5 * 60 * 1000) { // 5 min default
    this.maxSize = maxSize;
    this.ttl = ttl;
  }

  get(key: K): V | undefined {
    const entry = this.cache.get(key);
    if (!entry) return undefined;

    // Check expiration
    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return undefined;
    }

    // Update access count and timestamp for LRU
    entry.accessCount++;
    entry.timestamp = Date.now();
    return entry.data;
  }

  set(key: K, value: V): void {
    // Evict if at capacity and key doesn't exist
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      this.evictLRU();
    }

    this.cache.set(key, {
      data: value,
      timestamp: Date.now(),
      accessCount: 0,
    });
  }

  private evictLRU(): void {
    let lruKey: K | null = null;
    let lruAccessCount = Infinity;
    let oldestTime = Infinity;

    // Find least recently used entry (lowest access count, oldest timestamp)
    for (const [key, entry] of this.cache.entries()) {
      if (entry.accessCount < lruAccessCount || 
          (entry.accessCount === lruAccessCount && entry.timestamp < oldestTime)) {
        lruAccessCount = entry.accessCount;
        oldestTime = entry.timestamp;
        lruKey = key;
      }
    }

    if (lruKey !== null) {
      this.cache.delete(lruKey);
    }
  }

  has(key: K): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;

    // Check expiration
    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return false;
    }

    return true;
  }

  delete(key: K): boolean {
    return this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    // Clean up expired entries before returning size
    this.cleanExpired();
    return this.cache.size;
  }

  private cleanExpired(): void {
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.ttl) {
        this.cache.delete(key);
      }
    }
  }

  // Get all keys (useful for debugging)
  keys(): K[] {
    this.cleanExpired();
    return Array.from(this.cache.keys());
  }
}
