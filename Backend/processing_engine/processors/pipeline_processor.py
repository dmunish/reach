import json
from pydantic import ValidationError
from typing import List
from processing_engine.processor_utils.llm_client import AsyncLLMClient
from processing_engine.processor_utils.pipeline_prompts import messages
from processing_engine.models.schemas import QueueJob, Alert, AlertArea, StructuredAlert
import os
from httpx import AsyncClient


class PipelineProcessor():
    def __init__(self, llm: str):
        self.llm = AsyncLLMClient(llm)
    
    async def transform(self, job: QueueJob, document_id: str, alert_id: str):
        if job.message.filetype == "txt":
            document = job.message.raw_text
            filetype = "text"
        elif job.message.filetype in ["pdf", "pptx", "gif", "png", "jpeg", "jpg"]:
            document = job.message.url
            filetype = "document"
        llm_message = await messages(input=document, type=filetype)
        response = await self.llm.call(llm_message)
        json_response, alert, alert_areas = await self._parse(response, document_id, alert_id)
        return json_response, alert, alert_areas
    
    async def _parse(self, response: str, document_id: str, alert_id: str) -> tuple[dict, Alert, list[AlertArea]]:
        """Parse LLM JSON response"""
        response = response[response.find("{") : response.rfind("}") + 1]
        
        try:
            # Parse and validate JSON structure
            structured_alert = StructuredAlert.model_validate_json(response)
            json_response = structured_alert.model_dump(mode='json')
            
            # Create Alert object
            alert_model = Alert(
                id=alert_id,
                document_id=document_id,
                category=structured_alert.category,
                event=structured_alert.event,
                urgency=structured_alert.urgency,
                severity=structured_alert.severity,
                description=structured_alert.description,
                instruction="\n".join(structured_alert.instructions),
                effective_from=structured_alert.effective_from,
                effective_until=structured_alert.effective_until
            )

            alert = alert_model.model_dump(mode='json')
            
            # Create AlertArea objects from the areas list
            alert_areas = []
            for area_list in structured_alert.areas:
                place_ids = await self._geocode(area_list.place_names)
                for place_id in place_ids:
                    # Skip empty place_ids (unmatched locations)
                    if not place_id:
                        continue
                    alert_area_model = AlertArea(
                        alert_id=alert_id,
                        place_id=place_id,
                        specific_effective_from=area_list.specific_effective_from,
                        specific_effective_until=area_list.specific_effective_until,
                        specific_urgency=area_list.specific_urgency,
                        specific_severity=area_list.specific_severity,
                        specific_instruction=area_list.specific_instructions

                    )
                    alert_areas.append(alert_area_model.model_dump(mode='json'))
            
            return json_response, alert, alert_areas
            
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}")
        except ValidationError as e:
            raise ValueError(f"JSON doesn't match expected schema: {e}")
        
    async def _geocode(self, places: List[str]) -> List[str]:        
        url = os.getenv("MODAL_GEOCODER")
        auth_token = os.getenv("SECRET_KEY")
        
        async with AsyncClient(timeout=120.0) as http_client:
            response = await http_client.post(
                url,
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json"
                },
                json={"locations": places}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("place_ids", [])