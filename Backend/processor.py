import logging
from processing_engine.worker import QueueWorker
from processing_engine.models.schemas import QueueJob
import asyncio
from utils import load_env, async_supabase_client


async def process(limit: int = 5):
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Initialize environment and clients
    load_env()
    logger.info("Initializing worker...")

    supabase = await async_supabase_client()
    worker = QueueWorker(supabase)
    await worker.initialize()
    logger.info("Worker ready")

    # Process jobs in batches
    total_processed = 0
    
    while True:
        try:
            # Fetch jobs from queue
            response = await supabase.schema("pgmq_public").rpc("read", {
                "queue_name": "processing_queue",
                "sleep_seconds": 600,
                "n": limit
            }).execute()
            
            jobs_data = response.data
            logger.info(f"Fetched {len(jobs_data)} jobs from queue")
            
            if not jobs_data:
                logger.info("No more jobs in queue")
                break
            
            # Parse and process jobs concurrently
            jobs = [QueueJob(**job) for job in jobs_data]
            tasks = [worker.process_job(job) for job in jobs]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Job {jobs[i].id} failed: {result}")
                else:
                    total_processed += 1
            
            # Break if we got fewer jobs than requested (queue is empty)
            if int(len(jobs_data)) < int(limit):
                logger.info("Reached end of queue")
                break
                
        except Exception as e:
            logger.error(f"Error processing batch: {e}", exc_info=True)
            break

    logger.info(f"Worker completed. Total jobs processed: {total_processed}")
    return total_processed

if __name__ == "__main__":
    asyncio.run(process(limit=3))