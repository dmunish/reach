import asyncio
from typing import List
import logging
from processing_engine.processor_utils.doc_utils import url_to_b64_strings

_EXAMPLE_URLS = [
    "https://www.ndma.gov.pk/storage/advisories/August2025/WMpJfGUze00GwXezWekr.pdf", 
    "https://www.ndma.gov.pk/storage/advisories/December2025/evgtuouxcEBpD4FSxL9w.pdf", 
    "https://www.ndma.gov.pk/storage/projection-impact-langs/August2024/S1I2t0WfnuuE6fmYyK3D.pdf"
]

# Cache for base64-encoded example files
_cached_b64_files = None
_cache_lock = asyncio.Lock()

logger = logging.getLogger(__name__)

async def _load_examples() -> List[List[str]]:
  """
  Load example files
  """
  global _cached_b64_files
  
  # Fast path: cache already initialized
  if _cached_b64_files is not None:
    return _cached_b64_files
  
  # Slow path: acquire lock and initialize cache
  async with _cache_lock:
    # Double-check after acquiring lock (another coroutine may have initialized)
    if _cached_b64_files is not None:
        return _cached_b64_files
    
    print("Initializing example files cache...")  # Debug log
    
    try:
      tasks = [url_to_b64_strings(url) for url in _EXAMPLE_URLS]
      b64_files = await asyncio.gather(*tasks)
      _cached_b64_files = b64_files
      logger.info(f"Cache initialized with {len(_cached_b64_files)} example files")
      return _cached_b64_files
    except Exception as e:
      logger.error(f"Failed to initialize example cache: {e}")
      raise

system_prompt = """You are an expert disaster alert processor specializing in Pakistani emergency documents. 
Your role is to extract structured information from disaster alerts, advisories, and warnings issued by Pakistani authorities (NDMA, PMD, etc.).

## Core Competencies:
1. **Document Analysis**: You read only English text and output only English text.
2. **Visual Intelligence**: Analyze maps, charts, satellite imagery, and infographics to effectively understand them and extract data
3. **Geospatial Knowledge**: Deep familiarity with Pakistani administrative geography (provinces, districts, tehsils, major cities, and infrastructure)
4. **Meteorological & Disaster Literacy**: Understand weather patterns, hazard terminology, and emergency management concepts
5. **Error Correction**: Identify and fix common typos, transliteration errors, and inconsistencies in source documents

## Key Principles:
- **Accuracy over Speed**: Carefully review all text and visual elements before extracting data
- **Specificity**: Prefer specific locations over broad regions when both are mentioned
- **Standardization**: Convert all location names, abbreviations, and directional terms to standard forms
- **Completeness**: Extract all relevant information including area-specific variations in timing, severity, or instructions
- **Context Awareness**: Use visual context (maps, severity indicators, timeline graphics) to inform and validate text-based extractions
- **Citizen-Focused**: When generating instructions, prioritize actionable guidance for general public safety

## Geographic Expertise:
- Know all Pakistani provinces, districts, tehsils, and major cities
- Understand regional references (Potohar, Pothohar Region = Rawalpindi, Attock, Chakwal, Jhelum)
- Recognize major infrastructure (dams, motorways, highways) and map them to administrative units
- Apply consistent directional terminology (North/South/East/West/Central/North-Eastern/etc.)
- Resolve overlapping location mentions by using the most specific level available

## Quality Standards:
- Output valid, properly-formatted JSON only (no markdown, no explanations)
- Ensure all enum fields use only permitted values
- Use ISO 8601 datetime format with timezone
- Validate logical consistency (e.g., effective_from before effective_until)
- Include area-specific overrides only when document explicitly differentiates by location

You excel at transforming complex, multi-modal disaster documents into clean, actionable structured data that can power emergency response systems.
"""

json_prompt = """Convert the attached Pakistani disaster alert/information document to the specified CAP-derived JSON structure. 
Output only English text and ignore any Urdu text. Try to understand images in detail and make the extracted JSON information informed by the content of the text and the images/maps/charts in the document. 
Don't miss any information. Be wary of typos in the document, and correct if possible. Output only the JSON object, without any leading or trailing markdown.

# Field Definitions:
- **category**: Type of alert. The only valid values are: "Geo", "Met", "Safety", "Security", "Rescue", "Fire", "Health", "Env", "Transport", "Infra", "CBRNE", "Other"
- **event**: Brief name or title of the hazard or event (e.g., "Severe Thunderstorm", "Wildfire", "Flood Warning")
- **urgency**: Response time expected. The only valid values are: "Immediate", "Expected", "Future", "Past", "Unknown"
- **severity**: Severity of the event. The only valid values are: "Extreme", "Severe", "Moderate", "Minor", "Unknown"
- **description**: Description of the alert situation, hazards, and expected impacts in simple language
- **instruction**: A numbered list of recommended actions for citizens (not government personnel) to take. If no citizen-centric instructions present but needed, generate your own with [AI-generated] tag at the end of the list. Use proper end-lines "\n" at the end of each list instruction. Limited to at most 10 items.

- **effective_from**: ISO 8601 datetime when alert becomes active (e.g., "2024-03-15T14:30:00Z")
- **effective_until**: ISO 8601 datetime when alert expires
- **areas**: Array of affected locations with optional area-specific overrides

# Area Object Fields:
- **place_names**: Array of location names (cities, provinces, disctricts, province with directional term, etc.). If listing more specific parts (districts/tehsils/regions), don't mention more general regions(whole provinces, larger regions, etc.)
- **specific_effective_from**: (Optional) Override effective_from for this area(s)
- **specific_effective_until**: (Optional) Override effective_until for this area(s)
- **specific_urgency**: (Optional) Override urgency for this area(s)
- **specific_severity**: (Optional) Override severity for this area(s)
- **specific_instruction**: (Optional) Additional or override instructions for this area(s)

# Place Names:
- **Abbreviations**: Convert each abbreviation to its full form, like AJ&K to Azad Jammu and Kashmir.
- **Directional**: Extract directional for regions to a unified form, like "North-Eastern Balochistan". The only valid values are "North", "South", "East", "West", "Central", "North-Eastern", "North-Western", "South-Eastern" and "South-Western".
- **Overlap**: Try to avoid overlaps and be as specific as possible. For examples, if specific districts from a province relevant to the alert are mentioned alongside name of the entire province, use only specific districts.
- **Infrastructure**: When specific infrastructure is mentioned, convert it to the disctricts/tehsils containing it. For example:
    - "Tarbela Dam" to "Haripur"
    - "Motorways M2 and M5" to "Multan", "Bahawalpur", "Rahim Yar Khan", "Ghotki", "Sukkur", "Rawalpindi", "Chakwal", "Khushab", "Sargodha", "Sheikhupura", "Lahore"
- **Examples**: Some examples for the wrong and correct values:
    1.  Wrong: "Balochistan (Quetta, Ziarat, Zhob, Sherani, Chaman, Pishin, Qilla Abdullah, Qilla, Saifullah, Noushki)"
        Correct: "Quetta", "Ziarat", "Zhob", "Sherani", "Chaman", "Pishin", "Qilla Abdullah", "Qilla", "Saifullah", "Noushki"
    2.  Wrong: "Punjab (plain areas)"
        Correct: "Central Punjab", "South Punjab"
    3.  Wrong: "Upper Sindh"
        Correct: "North Sindh"
    4.  Wrong: "Potohar region"
        Correct: "Rawalpindi", "Attock", "Chakwal", "Jhelum"
    5.  Wrong: "Sindh Coastal Areas"
        Correct: "Southern Sindh"

# JSON Response Format:
{
  "category": "string",
  "event": "string",
  "urgency": "string",
  "severity": "string",
  "description": "string",
  "instruction": "string",
  "effective_from": "ISO 8601 datetime",
  "effective_until": "ISO 8601 datetime",
  "areas": [
    {
      "place_names": ["string"],
      "specific_effective_from": "ISO 8601 datetime or null",
      "specific_effective_until": "ISO 8601 datetime or null",
      "specific_urgency": "string or null",
      "specific_severity": "string or null",
      "specific_instruction": "string or null"
    }
  ]
}"""

async def messages(inputs: List[str]):
    """Prepares prompt for conversion of image to markdown, along with examples (few-shot prompting)"""
    b64_files = await _load_examples()
    return [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json_prompt}] + 
                    [
                      {
                        "type": "image_url",
                        "image_url":
                        {
                          "url": file
                        }
                      } for file in b64_files[0]
                    ] 
                },
                {
                    "role": "assistant",
                    "content": """
{
  "category": "Env",
  "event": "Glacial Lake Outburst Flood (GLOF) Alert",
  "urgency": "Immediate",
  "severity": "Severe",
  "description": "A wet spell is likely to affect Gilgit-Baltistan and Khyber Pakhtunkhwa in the current week, with scattered rain and thunderstorms and isolated heavy falls. This increases the risk of Glacial Lake Outburst Floods (GLOFs), flash floods, and landslides in vulnerable glaciated regions.",
  "instruction": "1. Avoid unnecessary movement in vulnerable areas, especially near discharge nullahs, streams, and rivers. \n2. Be aware of the risk of vehicles being washed away in fast-flowing water channels. If living in a low-lying area, exercise extra caution and heed community-based alert systems. \n3. Familiarize yourself with and follow the local evacuation plan for at-risk communities. \n4. Tourists should avoid trekking in glacier-prone areas, refrain from taking pictures or videos near glaciers, and strictly avoid going close to glacier sites.",
  "effective_from": "2025-08-12T11:30:00Z",
  "effective_until": "2025-08-18T23:59:59Z",
  "areas": [
    {
      "place_names": ["Gilgit-Baltistan", "Northern Khyber Pakhtunkhwa"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instruction": null
    }
  ]
}
"""
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json_prompt}] + 
                    [
                      {
                        "type": "image_url",
                        "image_url":
                        {
                          "url": file
                        }
                      } for file in b64_files[1]
                    ] 
                },
                {
                    "role": "assistant",
                    "content": """
{
  "category": "Met",
  "event": "Light Rain with Snowfall and Smog",
  "urgency": "Immediate",
  "severity": "Moderate",
  "description": "A weather system will bring light rain and snow to parts of Gilgit-Baltistan, Azad Jammu and Kashmir, and the upper areas of Khyber Pakhtunkhwa from the night of December 4th through December 5th, 2025. Meanwhile, smog and fog will continue in the plains of Punjab and Khyber Pakhtunkhwa overnight and in the mornings. This weather could lead to landslides, flash floods, damage from hail and strong winds, and an increased risk of lightning strikes.",
  "instruction": "1.Seek shelter immediately if there is hail or a thunderstorm. \n2. Avoid open fields, hilltops, and windows during storms. \n3.Do not drive during heavy hail or in standing water. \n4. Stay away from rivers, drainage canals, and flowing water in nullahs. \n5. If traveling, avoid crowded spots, maintain distance from water bodies, and do not go trekking in the rain. \n6. Check weather updates before heading to mountainous areas and avoid driving in unfamiliar or hilly terrain during rain.",
  "effective_from": "2025-12-04T20:00:00Z",
  "effective_until": "2025-12-05T23:59:59Z",
  "areas": [
    {
      "place_names": ["Gilgit-Baltistan", "Azad Jammu and Kashmir", "Dir", "Chitral", "Swat", "Kohistan", "Shangla", "Battagram"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instruction": "1. Be aware of potential landslides, rockfalls, and flash flooding. \n2. Avoid outdoor exposure in rainy and windy weather. \n3. Check weather updates before traveling to mountainous areas. \n4.Avoid self-driving in unfamiliar or hilly areas during rains. \n5. Farmers should manage activities keeping weather forecast in mind. \n6. Tourists should remain cautious of flash floods, avalanches, and tree falls."
    },
    {
      "place_names": ["Sialkot", "Narowal", "Lahore", "Sheikhupura", "Gujranwala", "Gujrat", "Jhelum", "Faisalabad", "Sahiwal", "Multan", "Khanewal", "Layyah", "Kot Addu", "Bahawalpur", "Peshawar", "Swabi", "Mardan", "Dera Ismail Khan"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": "Minor",
      "specific_instruction": "1. Exercise caution during night and morning hours due to reduced visibility. \n2. Avoid unnecessary travel during peak fog hours. \n3. Do not risk crossing any drain or road with water flow. \n4. Properly dispose of garbage to prevent clogging of drainage systems. \n5. Keep children away from nullahs and drainage lines."
    }
  ]
}
"""
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json_prompt}] + 
                    [
                      {
                        "type": "image_url",
                        "image_url":
                        {
                          "url": file
                        }
                      } for file in b64_files[2]
                    ] 
                },
                {
                    "role": "assistant",
                    "content": """
{
  "category": "Geo",
  "event": "Landslide Risk Advisory",
  "urgency": "Immediate",
  "severity": "Extreme",
  "description": "Heavy rainfall is expected from April 8 to 15, 2024, in Gilgit-Baltistan, Khyber Pakhtunkhwa, Azad Jammu and Kashmir, and Balochistan. This may cause landslides, slope failures, rock falls, and ground subsidence in vulnerable zones. Specific districts and sections of Karakoram Highway are at high risk.",
  "instruction": "1. Be watchful of landslides, slope failures, rock falls, and ground subsidence in vulnerable zones. \n2. Avoid unnecessary travel. \n3. Stay updated on weather and road conditions through social media and local news.",
  "effective_from": "2024-04-08T00:00:00Z",
  "effective_until": "2024-04-15T23:59:59Z",
  "areas": [
    {
      "place_names": ["Swat", "Shangla", "Mansehra", "Khyber", "Kohistan", "Abbottabad", "Skardu", "Ghanche", "Nagar", "Diamir", "Hunza", "Gilgit", "Muzaffarabad", "Haveli", "Bagh", "Zhob", "Musakhel", "Loralai", "Ziarat", "Sherani", "Killa Saifullah"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instruction": null
    }
  ]
}
"""
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json_prompt}] + 
                    [
                      {
                        "type": "image_url",
                        "image_url":
                        {
                          "url": input
                        }
                      } for input in inputs
                    ]
                }
            ]