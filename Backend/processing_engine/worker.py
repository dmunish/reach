import logging
from uuid import uuid4
from typing import List
import time
from datetime import datetime, timezone
from processing_engine.processors.pipeline_processor import PipelineProcessor
from processing_engine.models.schemas import QueueJob
from processing_engine.processor_utils.pipeline_prompts import _load_examples

LLM = "gemini-3"

class QueueWorker:
    def __init__(self, supabase):
        self.logger = logging.getLogger(__name__)
        self.db = supabase
        self.processor = PipelineProcessor(LLM)
        self._cache_initialized = False

    async def initialize(self):
        """Pre-warm caches before processing jobs"""
        if not self._cache_initialized:
            self.logger.info("Pre-warming example files cache...")
            try:
                await _load_examples()
                self._cache_initialized = True
            except Exception as e:
                self.logger.error(f"Failed to pre-warm cache: {e}")
                raise

    async def process_job(self, job: QueueJob) -> bool:
        """Process a single job: transform, upload, then remove from queue."""
        msg_id = job.msg_id
        document_id = job.message.document_id

        try:
            if not self._cache_initialized:
                await self.initialize()

            self.logger.info(f"Processing job {msg_id} (document: {document_id})")
            start_time = time.time()

            # Step 1: Transform document
            alert_id = str(uuid4())
            json_response, alert, alert_areas = await self.processor.transform(job, document_id, alert_id)
            
            if not json_response or not alert:
                self.logger.error(f"Job {msg_id}: Transform returned empty result")
                return False

            json_response["processing_time"] = f"{time.time() - start_time:.2f}"
            json_response["processing_model"] = LLM
            self.logger.info(f"Job {msg_id}: Transform complete in {json_response['processing_time']}s")
            print(json_response)

            # # Step 2: Upload to database (atomic transaction)
            # if not await self._upload(json_response, alert, alert_areas):
            #     self.logger.error(f"Job {msg_id}: Upload failed, keeping in queue for retry")
            #     return False

            # # Step 3: Remove from queue only after successful upload
            # if not await self._mark_complete(msg_id):
            #     # Data is uploaded but queue removal failed - log but don't fail
            #     # Job will be reprocessed but upsert will handle idempotency
            #     self.logger.warning(f"Job {msg_id}: Upload succeeded but queue removal failed")
            #     return True

            self.logger.info(f"Job {msg_id}: Completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Job {msg_id} failed: {e}", exc_info=True)
            return False

    async def _upload(self, json_response: dict, alert: dict, alert_areas: List[dict]):
        """Atomically upsert document, alert, and alert_areas via stored procedure"""
        document_id = alert["document_id"]
        try:
            # Call the stored procedure for atomic transaction
            response = await self.db.rpc("upload_processed_alert", {
                "p_document_id": document_id,
                "p_processed_at": datetime.now(timezone.utc).isoformat(),
                "p_structured_text": json_response,
                "p_alert": alert,
                "p_alert_areas": alert_areas if alert_areas else []
            }).execute()

            if response.data is None:
                self.logger.error(f"Transaction failed for document {document_id}: {response}")
                return False

            if not alert_areas:
                self.logger.warning(f"No valid alert_areas uploaded for document {document_id}")

            self.logger.info(f"Successfully uploaded data for document {document_id}")
            return True

        except Exception as e:
            self.logger.error(f"Upload failed for document {document_id}: {e}")
            return False
    
    async def _mark_complete(self, msg_id: int):
        response = await self.db.schema("pgmq_public").rpc("delete", {
            "queue_name": "processing_queue",
            "message_id": msg_id
        }).execute()
        if response.data and not response.error:
            self.logger.info(f"Successfully removed job {msg_id} from queue")
            return True
        else:
            self.logger.error(f"Error removing job {msg_id}: {response.error}")
            return False