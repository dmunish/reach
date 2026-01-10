import asyncio
from httpx import AsyncClient
from scrapers.parsers import NdmaParser, NeocParser
from scrapers.base_scraper import BaseScraper
from utils import supabase_client

SCRAPER_CONFIGS = [
    {
        'name': 'ndma',
        'url': 'https://www.ndma.gov.pk/advisories',
        'parser': NdmaParser(),
    },
    {
        'name': 'neoc',
        'url': 'https://www.ndma.gov.pk/projection-impact-list_new',
        'parser': NeocParser(),
    }
]

async def main():
    # Initialize shared clients
    http_client = AsyncClient(timeout=30.0)
    db_client = supabase_client()
    
    results = {}
    
    # Run all scrapers
    for config in SCRAPER_CONFIGS:
        scraper = BaseScraper(
            url=config['url'],
            parser=config['parser'],
            db_client=db_client,
            http_client=http_client
        )        
        try:
            count = await scraper.run()
            results[config['name']] = f"Added {count} new entries"
        except Exception as e:
            results[config['name']] = f"Error: {str(e)}"
    
    await http_client.aclose()
    return results

if __name__ == "__main__":
    asyncio.run(main())