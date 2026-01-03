class BaseParser:
    def parse_html(self, html: str) -> list[dict]:
        """Extract entries from HTML."""
        raise NotImplementedError
    
class BaseScraper:
    def __init__(self, url, parser: BaseParser, db_client, http_client):
        self.url = url
        self.parser = parser
        self.db = db_client
        self.http = http_client

    async def run(self):
        response = await self.http.get(self.url)
        html = response.text
        entries = self.parser.parse_entries(html)
        
        try:
            new_entries = self.filter_new(entries)
            if new_entries:
                upserted = self.upsert(new_entries)
                return upserted
        except Exception as e:
            print(f"Error filtering new entries: {e}")
        return 0
    
    def filter_new(self, entries):
        if not entries:
            return []
        
        filenames = [entry.get("filename") for entry in entries if entry.get("filename")]
        if not filenames:
            return []
        
        try:
            response = self.db.rpc(
                'filter_new_documents',
                {'filenames': filenames}
            ).execute()

            missing_filenames = {item['filename'] for item in response.data}
            new_entries = [
                entry for entry in entries 
                if entry.get("filename") in missing_filenames
            ]
            return new_entries
        except Exception as e:
            print(f"Error filtering new entries: {e}")
            return []
    
    def upsert(self, entries):
        response = self.db.table('documents').upsert(entries, on_conflict='filename').execute()
        return len(response.data)