import asyncio
from httpx import AsyncClient
from scrapers.parsers import NdmaParser, NeocParser, NdmaAPIParser, PmdPRParser
from scrapers.base_scraper import BaseScraper
from utils import supabase_client, load_env, get_logger
import os

load_env()

logger = get_logger(__name__)

SCRAPER_CONFIGS = [
    {
        'name': 'ndma',
        'url': 'https://www.ndma.gov.pk/advisories',
        'parser': NdmaParser()
    },
    {
        'name': 'neoc',
        'url': 'https://www.ndma.gov.pk/projection-impact-list_new',
        'parser': NeocParser()
    },
    {
        'name': 'ndma-api',
        'url': os.getenv("NDMA_API"),
        'parser': NdmaAPIParser()
    },
    {
        'name': 'pmd-press-releases',
        'url': 'https://nwfc.pmd.gov.pk/new/press-releases.php',
        'parser': PmdPRParser()
    }
]

async def run_scrapers():
    logger.info("Starting scraper orchestration")
    # Initialize shared clients
    http_client = AsyncClient(timeout=30.0)
    db_client = supabase_client()
    
    results = {}
    
    # Run all scrapers
    for config in SCRAPER_CONFIGS:
        logger.info(f"Running scraper: {config['name']}")
        scraper = BaseScraper(
            url=config['url'],
            parser=config['parser'],
            db_client=db_client,
            http_client=http_client
        )        
        try:
            count = await scraper.run()
            results[config['name']] = f"Added {count} new entries"
            logger.info(f"Scraper {config['name']} completed successfully. Added {count} entries.")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            results[config['name']] = error_msg
            logger.error(f"Scraper {config['name']} failed: {error_msg}", exc_info=True)
    
    await http_client.aclose()
    logger.info("Scraper orchestration completed")
    return results

if __name__ == "__main__":
    asyncio.run(run_scrapers())