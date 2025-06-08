import json
import os
from datetime import datetime, timedelta
import threading

class CacheManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CacheManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        self.cache_dir = 'search_cache'
        self.cache_duration = timedelta(hours=1)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._clean_old_cache()
    
    def _get_cache_file(self, query, source):
        # Create a safe filename from the query
        safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return os.path.join(self.cache_dir, f"{safe_query}_{source}.json")
    
    def _clean_old_cache(self):
        """Remove cache files older than cache_duration"""
        now = datetime.now()
        for filename in os.listdir(self.cache_dir):
            filepath = os.path.join(self.cache_dir, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if now - file_time > self.cache_duration:
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass

    def get_cached_results(self, query, source):
        """Get cached results if they exist and are not expired"""
        cache_file = self._get_cache_file(query, source)
        
        if not os.path.exists(cache_file):
            return None
            
        # Check if cache is expired
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - file_time > self.cache_duration:
            try:
                os.remove(cache_file)
            except OSError:
                pass
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def cache_results(self, query, source, results):
        """Cache the search results"""
        if not results:
            return
            
        cache_file = self._get_cache_file(query, source)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # Silently fail if we can't write to cache

    def clear_cache(self):
        """Clear all cached results"""
        for filename in os.listdir(self.cache_dir):
            try:
                os.remove(os.path.join(self.cache_dir, filename))
            except OSError:
                pass 