#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PKC 4.2: Smart Metadata Caching

In-memory cache for Plex metadata to reduce API requests.
Particularly useful for widgets and frequently accessed items.

Features:
- LRU (Least Recently Used) eviction policy
- TTL (Time To Live) based expiration
- Thread-safe operations
- Memory limit management
- Automatic cleanup

Cache Types:
- Widget cache: Short TTL (5 min), for dashboard/home items
- Detail cache: Medium TTL (15 min), for item detail views
- Sync cache: Long TTL (60 min), for library sync operations
"""
from logging import getLogger
from collections import OrderedDict
from threading import RLock
from time import time
from copy import deepcopy

from . import utils

LOG = getLogger('PLEX.metadata_cache')

# Cache configuration defaults
DEFAULT_MAX_SIZE = 1000  # Maximum number of items in cache
DEFAULT_TTL_WIDGET = 300  # 5 minutes for widget data
DEFAULT_TTL_DETAIL = 900  # 15 minutes for detail data
DEFAULT_TTL_SYNC = 3600  # 60 minutes for sync data

# Cache type constants
CACHE_TYPE_WIDGET = 'widget'
CACHE_TYPE_DETAIL = 'detail'
CACHE_TYPE_SYNC = 'sync'


class CacheEntry:
    """Single cache entry with timestamp and metadata"""
    __slots__ = ['data', 'timestamp', 'cache_type', 'access_count']
    
    def __init__(self, data, cache_type=CACHE_TYPE_WIDGET):
        self.data = data
        self.timestamp = time()
        self.cache_type = cache_type
        self.access_count = 0
    
    def is_expired(self, ttl):
        """Check if entry has exceeded its TTL"""
        return (time() - self.timestamp) > ttl
    
    def touch(self):
        """Update access count (for LRU tracking)"""
        self.access_count += 1


class MetadataCache:
    """
    Thread-safe LRU cache with TTL expiration for Plex metadata.
    
    Usage:
        cache = MetadataCache()
        
        # Store item
        cache.set(plex_id, xml_data, cache_type=CACHE_TYPE_WIDGET)
        
        # Retrieve item (returns None if expired or not found)
        data = cache.get(plex_id)
        
        # Invalidate item
        cache.invalidate(plex_id)
        
        # Clear all
        cache.clear()
    """
    
    def __init__(self, max_size=None, ttl_widget=None, ttl_detail=None, ttl_sync=None):
        """
        Initialize the metadata cache.
        
        Args:
            max_size: Maximum number of cached items (default: 1000)
            ttl_widget: TTL in seconds for widget data (default: 300)
            ttl_detail: TTL in seconds for detail data (default: 900)
            ttl_sync: TTL in seconds for sync data (default: 3600)
        """
        self._cache = OrderedDict()
        self._lock = RLock()
        self._max_size = max_size or DEFAULT_MAX_SIZE
        self._ttl = {
            CACHE_TYPE_WIDGET: ttl_widget or DEFAULT_TTL_WIDGET,
            CACHE_TYPE_DETAIL: ttl_detail or DEFAULT_TTL_DETAIL,
            CACHE_TYPE_SYNC: ttl_sync or DEFAULT_TTL_SYNC,
        }
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
        }
        LOG.debug('MetadataCache initialized: max_size=%d, ttl_widget=%d, '
                  'ttl_detail=%d, ttl_sync=%d',
                  self._max_size, self._ttl[CACHE_TYPE_WIDGET],
                  self._ttl[CACHE_TYPE_DETAIL], self._ttl[CACHE_TYPE_SYNC])
    
    def _get_ttl(self, cache_type):
        """Get TTL for cache type"""
        return self._ttl.get(cache_type, DEFAULT_TTL_WIDGET)
    
    def _evict_if_needed(self):
        """Evict oldest items if cache exceeds max size (must hold lock)"""
        while len(self._cache) >= self._max_size:
            oldest_key, _ = self._cache.popitem(last=False)
            self._stats['evictions'] += 1
            LOG.debug('Cache eviction: plex_id=%s', oldest_key)
    
    def _cleanup_expired(self):
        """Remove expired entries (must hold lock)"""
        now = time()
        expired_keys = []
        for key, entry in self._cache.items():
            ttl = self._get_ttl(entry.cache_type)
            if (now - entry.timestamp) > ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            self._stats['expirations'] += 1
        
        if expired_keys:
            LOG.debug('Cache cleanup: removed %d expired entries', len(expired_keys))
    
    def get(self, plex_id, cache_type=None):
        """
        Retrieve cached metadata for plex_id.
        
        Args:
            plex_id: Plex item ID
            cache_type: Optional cache type filter
        
        Returns:
            Cached data or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(plex_id)
            
            if entry is None:
                self._stats['misses'] += 1
                return None
            
            # Check cache type if specified
            if cache_type is not None and entry.cache_type != cache_type:
                self._stats['misses'] += 1
                return None
            
            # Check expiration
            ttl = self._get_ttl(entry.cache_type)
            if entry.is_expired(ttl):
                del self._cache[plex_id]
                self._stats['expirations'] += 1
                self._stats['misses'] += 1
                return None
            
            # Move to end for LRU
            self._cache.move_to_end(plex_id)
            entry.touch()
            self._stats['hits'] += 1
            
            # Return deep copy to prevent modification
            return deepcopy(entry.data)
    
    def set(self, plex_id, data, cache_type=CACHE_TYPE_WIDGET):
        """
        Store metadata in cache.
        
        Args:
            plex_id: Plex item ID
            data: Data to cache (will be deep copied)
            cache_type: Cache type for TTL selection
        """
        with self._lock:
            # Evict if needed before adding new item
            if plex_id not in self._cache:
                self._evict_if_needed()
            
            # Store deep copy to prevent external modification
            self._cache[plex_id] = CacheEntry(deepcopy(data), cache_type)
            self._cache.move_to_end(plex_id)
    
    def set_batch(self, items, cache_type=CACHE_TYPE_WIDGET):
        """
        Store multiple items in cache.
        
        Args:
            items: Dict of {plex_id: data}
            cache_type: Cache type for TTL selection
        """
        with self._lock:
            for plex_id, data in items.items():
                if plex_id not in self._cache:
                    self._evict_if_needed()
                self._cache[plex_id] = CacheEntry(deepcopy(data), cache_type)
                self._cache.move_to_end(plex_id)
            LOG.debug('Batch cached %d items as type %s', len(items), cache_type)
    
    def invalidate(self, plex_id):
        """
        Remove item from cache.
        
        Args:
            plex_id: Plex item ID to invalidate
        """
        with self._lock:
            if plex_id in self._cache:
                del self._cache[plex_id]
                LOG.debug('Cache invalidate: plex_id=%s', plex_id)
    
    def invalidate_batch(self, plex_ids):
        """
        Remove multiple items from cache.
        
        Args:
            plex_ids: List of Plex item IDs to invalidate
        """
        with self._lock:
            count = 0
            for plex_id in plex_ids:
                if plex_id in self._cache:
                    del self._cache[plex_id]
                    count += 1
            if count:
                LOG.debug('Batch invalidate: removed %d items', count)
    
    def invalidate_by_type(self, cache_type):
        """
        Remove all items of a specific cache type.
        
        Args:
            cache_type: Cache type to invalidate
        """
        with self._lock:
            keys_to_remove = [
                key for key, entry in self._cache.items()
                if entry.cache_type == cache_type
            ]
            for key in keys_to_remove:
                del self._cache[key]
            LOG.debug('Invalidate by type %s: removed %d items',
                      cache_type, len(keys_to_remove))
    
    def clear(self):
        """Clear all cached data"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            LOG.info('Cache cleared: removed %d items', count)
    
    def cleanup(self):
        """Manually trigger cleanup of expired entries"""
        with self._lock:
            self._cleanup_expired()
    
    def get_stats(self):
        """
        Get cache statistics.
        
        Returns:
            Dict with hits, misses, size, hit_rate, etc.
        """
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
            
            # Count by type
            type_counts = {
                CACHE_TYPE_WIDGET: 0,
                CACHE_TYPE_DETAIL: 0,
                CACHE_TYPE_SYNC: 0,
            }
            for entry in self._cache.values():
                if entry.cache_type in type_counts:
                    type_counts[entry.cache_type] += 1
            
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'expirations': self._stats['expirations'],
                'hit_rate': round(hit_rate, 2),
                'by_type': type_counts,
            }
    
    def __len__(self):
        """Return number of cached items"""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, plex_id):
        """Check if plex_id is in cache (without updating LRU)"""
        with self._lock:
            if plex_id not in self._cache:
                return False
            entry = self._cache[plex_id]
            ttl = self._get_ttl(entry.cache_type)
            return not entry.is_expired(ttl)


# Global cache instance (lazy initialization)
_global_cache = None


def get_cache():
    """
    Get the global metadata cache instance.
    
    Returns:
        MetadataCache instance
    """
    global _global_cache
    if _global_cache is None:
        # Read settings for cache configuration
        try:
            max_size = int(utils.settings('metadataCacheSize') or DEFAULT_MAX_SIZE)
        except (ValueError, TypeError):
            max_size = DEFAULT_MAX_SIZE
        
        _global_cache = MetadataCache(max_size=max_size)
        LOG.info('Global metadata cache initialized with max_size=%d', max_size)
    
    return _global_cache


def clear_cache():
    """Clear the global metadata cache"""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()


def invalidate_item(plex_id):
    """Invalidate a specific item in the global cache"""
    global _global_cache
    if _global_cache is not None:
        _global_cache.invalidate(plex_id)


def get_cache_stats():
    """Get statistics from the global cache"""
    global _global_cache
    if _global_cache is not None:
        return _global_cache.get_stats()
    return None
