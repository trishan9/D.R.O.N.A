"""Web scrapers for Nepali job portals.

ToS / robots.txt status (checked May 2026):
  MeroJob    - robots.txt fully open; site is JS-rendered → manual collection
  JobsNepal  - robots.txt fully open; site is SSR → automated scraper ✅
  Internsathi - /all-opportunities disallowed; individual pages OK → sitemap scraper ✅
  KumariJob  - /search explicitly Allow'd; job pages OK → search+scrape ✅

All scrapers share the rate limiter in `_http.py` (default 0.5 req/s per portal).
"""
