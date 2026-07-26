import hashlib
import json
import httpx
from utils import get_logger

logger = get_logger(__name__)

class BaseParser:
    def parse_html(self, html: str) -> list[dict]:
        """Extract entries from HTML."""
        raise NotImplementedError

    def generate_hash(self, *args) -> str:
        """Generate SHA256 hash from variable arguments joined by a pipe."""
        clean_args = [str(arg) if arg is not None else "" for arg in args]
        joined = "|".join(clean_args)
        return hashlib.sha256(joined.encode('utf-8')).hexdigest()
    
class BaseScraper:
    def __init__(self, url, parser: BaseParser, db_client, http_client):
        self.url = url
        self.parser = parser
        self.db = db_client
        self.http = http_client
        self.logger = get_logger(self.__class__.__name__)

    async def run(self):
        self.logger.info(f"Starting scrape for {self.url}")
        try:
            response = await self.http.get(self.url)
            response.raise_for_status()
            
            entries = self.parser.parse_entries(response)
            self.logger.info(f"Parsed {len(entries)} entries from {self.url}")
            
            # Deduplicate by content_hash before upsert
            entries = self._deduplicate_by_hash(entries)
            
            new_entries = self.filter_new(entries)
            self.logger.info(f"Found {len(new_entries)} new entries")

            if new_entries:
                count = self.upsert(new_entries)
                self.logger.info(f"Upserted {count} entries")
                return count
            
            return 0

        except httpx.ConnectError:
            self.logger.warning(f"Connection failed for {self.url} — host may be unreachable")
            return 0
        except httpx.TimeoutException:
            self.logger.warning(f"Request timed out for {self.url}")
            return 0
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"HTTP {e.response.status_code} for {self.url}")
            return 0
        except httpx.RequestError as e:
            self.logger.warning(f"Request error for {self.url}: {e}")
            return 0
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {self.url}: {e}", exc_info=True)
            return 0
    
    def _deduplicate_by_hash(self, entries: list[dict]) -> list[dict]:
        """Remove entries with duplicate content_hash, keeping first occurrence."""
        seen = set()
        deduped = []
        for entry in entries:
            h = entry.get("content_hash")
            if h and h not in seen:
                seen.add(h)
                deduped.append(entry)
        dupes = len(entries) - len(deduped)
        if dupes:
            self.logger.info(f"Deduplicated {dupes} duplicate entries")
        return deduped

    def filter_new(self, entries):
        if not entries:
            return []
        
        hashes = [entry.get("content_hash") for entry in entries if entry.get("content_hash")]
        if not hashes:
            return []
        
        try:
            response = self.db.rpc(
                'filter_new_hashes', 
                {'hashes': hashes}
            ).execute()
            
            new_hashes = {item['content_hash'] for item in response.data}
            
            new_entries = [entry for entry in entries if entry.get("content_hash") in new_hashes]
            return new_entries
        except Exception as e:
            self.logger.error(f"Error filtering new entries: {str(e)}", exc_info=True)
            return [] # Fail safe to return empty list or maybe raise? returning empty list prevents duplicates if DB is down but loses data. 
            # Actually, if DB is down, we probably can't proceed. But existing code returned [] on error.
    
    def upsert(self, entries):
        try:
            response = self.db.table('documents').upsert(entries, on_conflict='content_hash').execute()
            return len(response.data)
        except Exception as e:
            self.logger.error(f"Error upserting entries: {str(e)}", exc_info=True)
            raise e