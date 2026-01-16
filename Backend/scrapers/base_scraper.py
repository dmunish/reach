import hashlib
import json

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

    async def run(self):
        response = await self.http.get(self.url)
        entries = self.parser.parse_entries(response)
        
        try:
            new_entries = self.filter_new(entries)
            print(json.dumps(new_entries, indent=4))
            if new_entries:
                # upserted = self.upsert(new_entries)
                return 0
        except Exception as e:
            print(f"Error filtering new entries: {e}")
        return 0
    
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
            
            existing_hashes = {item['content_hash'] for item in response.data}
            
            new_entries = [
                entry for entry in entries 
                if entry.get("content_hash") in existing_hashes
            ]
            return new_entries
        except Exception as e:
            print(f"Error filtering new entries: {e}")
            return []
    
    def upsert(self, entries):
        response = self.db.table('documents').upsert(entries, on_conflict='content_hash').execute()
        return len(response.data)