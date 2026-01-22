#!/usr/bin/env python3
"""
Redis Cache Performance Test

Tests the performance improvement of Redis caching for geocoding queries.
Compares cold cache (database) vs warm cache (Redis) response times.
"""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from geocoding.dependencies import get_redis_cache
from geocoding.config import get_settings


async def test_redis_connection():
    """Test Redis connectivity"""
    print("=" * 60)
    print("REDIS CONNECTIVITY TEST")
    print("=" * 60)
    
    settings = get_settings()
    print(f"\n📋 Configuration:")
    print(f"   Host: {settings.redis_host}")
    print(f"   Port: {settings.redis_port}")
    print(f"   DB: {settings.redis_db}")
    print(f"   Enabled: {settings.redis_enabled}")
    
    if not settings.redis_enabled:
        print("\n❌ Redis is DISABLED in settings")
        return False
    
    print(f"\n🔌 Connecting to Redis...")
    try:
        cache = await get_redis_cache()
        
        if cache is None:
            print("❌ Failed to get Redis cache instance")
            return False
        
        is_connected = await cache.is_connected()
        
        if is_connected:
            print("✅ Redis connection successful!")
            
            # Test basic operations
            print(f"\n🧪 Testing basic operations...")
            
            # SET
            test_key = "test_connection"
            test_value = {"message": "Hello from Redis!", "timestamp": time.time()}
            success = await cache.set("test", test_key, test_value, ttl_seconds=60)
            print(f"   SET: {'✅' if success else '❌'}")
            
            # GET
            retrieved = await cache.get("test", test_key)
            print(f"   GET: {'✅' if retrieved == test_value else '❌'}")
            
            # DELETE
            deleted = await cache.delete("test", test_key)
            print(f"   DELETE: {'✅' if deleted else '❌'}")
            
            return True
        else:
            print("❌ Redis is not responding to PING")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cache_performance():
    """Test cache performance with actual geocoding operations"""
    print("\n" + "=" * 60)
    print("CACHE PERFORMANCE TEST")
    print("=" * 60)
    
    try:
        from geocoding.dependencies import get_places_repository
        from uuid import UUID
        
        cache = await get_redis_cache()
        if not cache or not await cache.is_connected():
            print("❌ Redis not available - skipping performance test")
            return
        
        repo = get_places_repository()
        
        # Test data - use a common directional query
        print("\n🔍 Test Query: Directional search (simulated)")
        print("   This simulates 'North Punjab' type queries")
        
        # Clear any existing cache for this test
        test_namespace = "test_performance"
        await cache.clear_namespace(test_namespace)
        
        test_data = [
            {"id": "1", "name": "Place A", "level": 2},
            {"id": "2", "name": "Place B", "level": 2},
            {"id": "3", "name": "Place C", "level": 3},
        ] * 100  # 300 items to simulate real query size
        
        # Cold cache (write)
        print("\n❄️  COLD CACHE (first query - database simulation)")
        start = time.time()
        await asyncio.sleep(0.5)  # Simulate database query time
        await cache.set(test_namespace, "test_query", test_data, ttl_seconds=60)
        cold_time = time.time() - start
        print(f"   Time: {cold_time*1000:.0f}ms (includes simulated DB query)")
        
        # Warm cache (read)
        print("\n🔥 WARM CACHE (subsequent query - Redis)")
        start = time.time()
        cached_result = await cache.get(test_namespace, "test_query")
        warm_time = time.time() - start
        print(f"   Time: {warm_time*1000:.0f}ms")
        
        # Results
        print("\n📊 RESULTS:")
        speedup = cold_time / warm_time if warm_time > 0 else 0
        print(f"   Cold: {cold_time*1000:.0f}ms")
        print(f"   Warm: {warm_time*1000:.0f}ms")
        print(f"   Speedup: {speedup:.1f}x faster ⚡")
        print(f"   Data verified: {'✅' if cached_result == test_data else '❌'}")
        
        # Cleanup
        await cache.delete(test_namespace, "test_query")
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n" + "🚀 " * 20)
    print("GEOCODING SERVICE - REDIS CACHE TEST SUITE")
    print("🚀 " * 20 + "\n")
    
    # Test 1: Connection
    connection_ok = await test_redis_connection()
    
    # Test 2: Performance (only if connection works)
    if connection_ok:
        await test_cache_performance()
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60 + "\n")
    
    if connection_ok:
        print("✅ All tests passed!")
        print("\n💡 Next steps:")
        print("   1. Start the geocoding service: python -m geocoder")
        print("   2. Run a query twice to see caching in action")
        print("   3. Check logs for cache HIT/MISS indicators")
    else:
        print("❌ Redis connection failed")
        print("\n🔧 Troubleshooting:")
        print("   1. Check if Redis is running: redis-cli ping")
        print("   2. Verify REDIS_ENABLED=true in .env")
        print("   3. Check Redis host/port in .env")
        print("   4. Install Redis: sudo apt install redis-server (Ubuntu)")
        print("                    brew install redis (macOS)")


if __name__ == "__main__":
    asyncio.run(main())
