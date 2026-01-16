from fastapi import FastAPI, HTTPException, Request
import os
from scrapers.scraper_orchestrator import run_scrapers
from utils import load_env, get_logger

load_env()
logger = get_logger(__name__)
app = FastAPI()
SECRET_KEY = os.getenv("SECRET_KEY")

@app.post("/scrape")
async def scrape_endpoint(request: Request):
    logger.info("Received scrape request")
    #Authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    provided_key = auth_header.split("Bearer ")[1]
    if provided_key != SECRET_KEY:
        logger.warning("Invalid authorization key provided")
        raise HTTPException(status_code=401, detail="Invalid authorization key")
    
    #Running the scraper
    try:
        logger.info("Starting scraper execution")
        results = await run_scrapers()
        logger.info("Scraper execution completed successfully")
        return {
            "status": "success",
            "message": "Scraping completed",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Scraper failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "reach-scraper",
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)