import asyncio
from typing import List
import logging
from processing_engine.processor_utils.doc_utils import url_to_b64_strings

_EXAMPLE_URLS = [
    "https://www.ndma.gov.pk/storage/advisories/August2025/WMpJfGUze00GwXezWekr.pdf", 
    "https://www.ndma.gov.pk/storage/advisories/January2026/s192iGRrLKbNUURRYmIy.pdf", 
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
- **Standardization**: Convert all location names, abbreviations, and directional terms to standard forms
- **Completeness**: Extract all relevant information including area-specific variations in timing, severity, or instructions
- **Context Awareness**: Use visual context (maps, severity indicators, timeline graphics) to inform and validate text-based extractions
- **Citizen-Focused**: When generating instructions, prioritize actionable guidance for general public safety

## Geographic Expertise:
- Know all Pakistani provinces, districts, tehsils, and major cities
- Understand regional references and expand to districts/directional (e.g. Potohar, Pothohar Region = [Rawalpindi, Attock, Chakwal, Jhelum])
- Recognize major infrastructure (dams, motorways, highways) and map them to administrative units
- Apply consistent directional terminology (North/South/East/West/Central/North-Eastern/etc.)

## Quality Standards:
- Output valid, properly-formatted JSON only (no markdown, no explanations)
- Ensure all enum fields use only permitted values
- Use ISO 8601 datetime format with timezone (e.g."2024-03-15T14:30:00Z")
- Validate logical consistency (e.g., effective_from before effective_until)
- Include area-specific overrides only when document explicitly differentiates by location

You excel at transforming complex, multi-modal disaster documents into clean, actionable structured data that can power emergency response systems.
"""

json_prompt = """Convert the attached Pakistani disaster alert/information document to the specified CAP-derived JSON structure.
If there are images/visualizations, try to understand images in detail and make the extracted JSON information informed by the content of the text and the images/maps/charts in the document. 
Don't miss any information. Be wary of typos in the document, and correct if possible. Output only the JSON object, without any leading or trailing markdown.

# JSON Response Format:
{
  "category": "string",
  "event": "string",
  "urgency": "string",
  "severity": "string",
  "description": "string",
  "instructions": ["string"],
  "effective_from": "ISO 8601 datetime",
  "effective_until": "ISO 8601 datetime",
  "areas": [
    {
      "place_names": ["string"],
      "specific_effective_from": "ISO 8601 datetime or null",
      "specific_effective_until": "ISO 8601 datetime or null",
      "specific_urgency": "string or null",
      "specific_severity": "string or null",
      "specific_instructions": "string or null"
    }
  ]
}

# Field Definitions:
- **category**: Type of alert. The only valid values are: "Geo", "Met", "Safety", "Security", "Rescue", "Fire", "Health", "Env", "Transport", "Infra", "CBRNE", "Other"
- **event**: Brief name or title of the hazard or event (e.g., "Severe Thunderstorm", "Wildfire", "Flood Warning")
- **urgency**: Response time expected. The only valid values are: "Immediate", "Expected", "Future", "Past", "Unknown"
- **severity**: Severity of the event. The only valid values are: "Extreme", "Severe", "Moderate", "Minor", "Unknown"
- **description**: Description of the alert situation, hazards, and expected impacts in simple language. Avoid detailed mentions of affected areas, dates, etc. here as they will be mentioned in other fields.
- **instructions**: An array of strings, where each string is a distinct recommended action for citizens. If no citizen-centric instructions present but needed, generate your own with [AI-generated] tag at the end of the list. Limited to at most 5 items.

- **effective_from**: ISO 8601 datetime when alert becomes active (e.g., "2024-03-15T14:30:00Z")
- **effective_until**: ISO 8601 datetime when alert expires
- **areas**: Array of affected locations with optional area-specific overrides

# Area Object Fields:
- **place_names**: Array of location names (cities, provinces, disctricts, province with directional term, etc.).
- **specific_effective_from**: (Optional) Override effective_from for this area(s)
- **specific_effective_until**: (Optional) Override effective_until for this area(s)
- **specific_urgency**: (Optional) Override urgency for this area(s)
- **specific_severity**: (Optional) Override severity for this area(s)
- **specific_instructions**: A single string overriding instructions for this area(s)

# Place Names:
- **Abbreviations**: Convert each abbreviation to its full form, like AJ&K to Azad Jammu and Kashmir.
- **Clustering**: Try to cluster different regions/districts into a single list as much as possible, and only make seperate lists when there is a need to override the base alert's fields (effective_from, instructions, etc.).
- **Directional**: Extract directional for regions to a unified form, like "North-Eastern Balochistan". The only valid values are "North", "South", "East", "West", "Central", "North-Eastern", "North-Western", "South-Eastern" and "South-Western".
- **Overlap**: Try to avoid overlaps and be as general as possible. For examples, if specific districts from a province relevant to the alert are mentioned alongside name of the entire province, select the specific districts if they are a small part of the province, or select the province if the mentioned districts make up the majority of the province.
- **Patchy Lists**: If the mentioned districts result in a patchy network if districts, expand the list slightly with the least amount of additinal districts possible so as to create a smooth polygon. Also try to use directional descriptions over listing specific names for this very reason.
- **Infrastructure**: When specific infrastructure is mentioned, convert it to the disctricts/tehsils containing it. For example:
    - "Tarbela Dam" to "Haripur"
    - "Motorways M2 and M5" to ["Multan","Bahawalpur","Rahim Yar Khan","Ghotki","Sukkur","Rawalpindi","Chakwal","Khushab","Sargodha","Sheikhupura","Lahore"]
- **Examples**: Some examples for the wrong and correct values:
    1.  Wrong: [:Balochistan (Quetta, Ziarat, Zhob, Sherani, Chaman, Pishin, Qilla Abdullah, Qilla, Saifullah, Noushki)"]
        Reason: Improper formatting
        Correct: ["Quetta","Ziarat","Zhob","Sherani","Chaman","Pishin","Qilla Abdullah","Qilla","Saifullah","Noushki"]
    2.  Wrong: ["Punjab (plain areas)"]
        Reason: Cannot be geocoded. Expand to directional descriptions.
        Correct: ["Central Punjab","South Punjab"]
    3.  Wrong: "[Upper Sindh]"
        Reason: Improper wording for geocoder.
        Correct: ["North Sindh"]
    4.  Wrong: ["Potohar region"]
        Reason: Region names cannot be geocoded by geocoder. Only official administrative units or their directional versions. Expand region names like these to the constituent districts using your world knowledge.
        Correct: ["Rawalpindi","Attock","Chakwal","Jhelum"]
    5.  Wrong: ["Sindh Coastal Areas"]
        Reason: Natural language descriptions like these cannot be processed by geocoder.
        Correct: ["Southern Sindh"]
    6.  Wrong: ["Kotli","Bhimber","Muzaffarabad","Jhelum Valley","Neelam Valley","Poonch","Bagh","Haveli"}
        Reason: Majority of districts of Azad Kashmir province listed. Better to replace with entire province to ensure smooth polygon.
        Correct: ["Azad Kashmir"]
    7.  Wrong: ["Upper Chitral","Lower Chitral","Upper Dir","Lower Dir","Central Dir","Swat","Upper Swat","Shangla","Buner","Malakand","Bajaur","Upper Kohistan","Lower Kohistan","Kolai-Palas","Allai","Battagram","Torghar","Abbottabad"]
        Reason: Majority of districts of Northern KPK listed. Better to replace with directional description of province to ensure smooth polygon.
        Correct: ["North Khyber Pakhtunkhwa"]
    8.  Wrong: ["Murree","Galiyat"]
        Reason: Galiyat is not an administrative unit, but instead a region.
        Correct: ["Murree","Abbottabad"]
    9.  Wrong: ["Lahore","Gujranwala","Sheikhupura","Kasur","Nankana Sahib","Faisalabad","Multan","Bahawalpur","Rahim Yar Khan","Bahawalnagar","Khanpur"]
        Reason: Too many specific districts. Might result in patchy polygon when geocoded.
        Correct: ["Central Punjab","South Punjab"]
"""

async def messages(input: str, type: str):
    """Prepares prompt for conversion of image to markdown, along with examples (few-shot prompting)"""
    b64_files = await _load_examples()
    if type == "document":
      images = await url_to_b64_strings(input)
      request = {
        "role": "user",
        "content": [{"type": "text", "text": json_prompt}] + 
        [
          {
            "type": "image_url",
            "image_url":
            {
              "url": image
            }
          } for image in images
        ]
      }
    elif type == "text":
      request = {
      "role": "user",
      "content": [{"type": "text", "text": json_prompt},  
        {
          "type": "text",
          "text": input
        }
      ]
      }
       
       
  
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
  "instructions": ["1. Avoid unnecessary movement in vulnerable areas, especially near discharge nullahs, streams, and rivers.","2. Be aware of the risk of vehicles being washed away in fast-flowing water channels. If living in a low-lying area, exercise extra caution and heed community-based alert systems.","3. Familiarize yourself with and follow the local evacuation plan for at-risk communities.","4. Tourists should avoid trekking in glacier-prone areas, refrain from taking pictures or videos near glaciers, and strictly avoid going close to glacier sites."],
  "effective_from": "2025-08-12T11:30:00Z",
  "effective_until": "2025-08-18T23:59:59Z",
  "areas": [
    {
      "place_names": ["Gilgit Baltistan", "Northern Khyber Pakhtunkhwa"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instructions": null
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
  "event": "Widespread Rain, Snowfall, and Thunderstorms",
  "urgency": "Expected",
  "severity": "Severe",
  "description": "Rain and snowfall expected across Pakistan from January 16-23. Light weather starts 16th, intensifying 20th-23rd with heavy snow in mountains and widespread rain/thunderstorms. Hazards include snow-blocked roads, landslides, avalanches, flash floods in streams, flooding in low-lying areas, and damage to structures/crops from windstorms and hail.",
  "instructions": ["1. Tourists should avoid mountainous areas Jan 16-23. If you must travel, check weather updates, bring tire chains and warm clothes.","2. Stay away from weak structures, billboards, power lines, and solar panels during storms.","3. Residents of mountainous regions should watch for landslides and avalanches. Residents of low-lying areas should prepare for flooding.","4. Farmers should protect crops and livestock from hail and cold weather."],
  "effective_from": "2026-01-16T18:00:00",
  "effective_until": "2026-01-23T23:59:59",
  "areas": [
    {
      "place_names": ["Gilgit Baltistan","Azad Kashmir","North Khyber Pakhtunkhwa"],
      "specific_effective_from": "2026-01-16T18:00:00Z",
      "specific_effective_until": "2026-01-19T23:59:59Z",
      "specific_urgency": "Expected",
      "specific_severity": "Moderate",
      "specific_instructions": "Rain and thunderstorms with light-to-moderate snowfall expected."
    },
    {
      "place_names": ["Murree","Abbottabad"],
      "specific_effective_from": "2026-01-18T18:00:00Z",
      "specific_effective_until": "2026-01-20T23:59:59Z",
      "specific_urgency": "Expected",
      "specific_severity": "Moderate",
      "specific_instructions": "Light rain and snowfall expected in Murree, Galiyat and surrounding areas"
    },
    {
      "place_names": ["Rawalpindi","Attock","Chakwal","Jhelum","Islamabad"],
      "specific_effective_from": "2026-01-18T00:00:00Z",
      "specific_effective_until": "2026-01-23T23:59:59Z",
      "specific_urgency": "Expected",
      "specific_severity": "Severe",
      "specific_instructions": "Urban flooding risk in twin cities."
    },
    {
      "place_names": ["Central Khyber Pakhtunkhwa","South Khyber Pakhtunkhwa","Central Punjab","South Punjab"],
      "specific_effective_from": "2026-01-20T00:00:00Z",
      "specific_effective_until": "2026-01-23T23:59:59Z",
      "specific_urgency": "Future",
      "specific_severity": "Moderate",
      "specific_instructions": null
    },
    {
      "place_names": ["Balochistan"],
      "specific_effective_from": "2026-01-21T00:00:00Z",
      "specific_effective_until": "2026-01-22T23:59:59Z",
      "specific_urgency": "Future",
      "specific_severity": "Severe",
      "specific_instructions": "Flash flood risk in local nullahs."
    },
    {
      "place_names": ["North Balochistan"],
      "specific_effective_from": "2026-01-21T00:00:00Z",
      "specific_effective_until": "2026-01-22T23:59:59Z",
      "specific_urgency": "Future",
      "specific_severity": "Severe",
      "specific_instructions": "Heavy snowfall expected in Quetta, Ziarat, and northern districts."
    },
    {
      "place_names": ["Sindh"],
      "specific_effective_from": "2026-01-22T00:00:00Z",
      "specific_effective_until": "2026-01-23T23:59:59Z",
      "specific_urgency": "Future",
      "specific_severity": "Moderate",
      "specific_instructions": null
    },
    {
      "place_names": ["Gilgit Baltistan","North Azad Kashmir","Central Azad Kashmir","North Khyber Pakhtunkhwa","Murree"],
      "specific_effective_from": "2026-01-20T18:00:00Z",
      "specific_effective_until": "2026-01-23T23:59:59Z",
      "specific_urgency": "Expected",
      "specific_severity": "Severe",
      "specific_instructions": "Expect heavy rain and snowfall, road closures, and avalanche risks. Ensure vehicle winterization."
      },
      {
      "place_names": ["Punjab","Islamabad","Central Khyber Pakhtunkhwa","South Khyber Pakhtunkhwa"],
      "specific_effective_from": "2026-01-20T18:00:00Z",
      "specific_effective_until": "2026-01-23T23:59:59Z",
      "specific_urgency": "Expected",
      "specific_severity": "Severe",
      "specific_instructions": "Expect widespread rain and thunderstorms with occasional gaps. Heavy rains may generate flash floods in local streams and nullahs, and may cause urban flooding."}
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
  "instructions": ["1. Be watchful of landslides, slope failures, rock falls, and ground subsidence in vulnerable zones. ","2. Avoid unnecessary travel. ","3. Stay updated on weather and road conditions through social media and local news."],
  "effective_from": "2024-04-08T00:00:00Z",
  "effective_until": "2024-04-15T23:59:59Z",
  "areas": [
    {
      "place_names": ["North Khyber Pakhtunkhwa","Khyber","North Gilgit Baltistan","East Gilgit Baltistan","North Azad Kashmir","Central Azad Kashmir", "North-Eastern Balochistan"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instructions": null
    }
  ]
}
"""
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json_prompt},
                      {
                        "type": "text",
                        "text":"""
{
	"id": 3324,
	"title": "Cold wave & Snow -  Northern Pakistan (January 14-20, 2026)",
	"description": "A strong cold wave is expected over Gilgit-Baltistan, upper Khyber Pakhtunkhwa, and Azad Jammu & Kashmir from 14–20 January 2026, with very cold to extremely cold conditions, especially during nights and early mornings. Day temperatures will remain below normal, while moderate to heavy snowfall is likely in high-altitude and hilly areas, and cold, dry weather with frost in pockets is expected over adjoining plains.",
	"impact": "Snowfall may disrupt road access, transportation, and power supply in mountainous areas.\r","Higher risk of snow slides/avalanches in the vulnerable locations.\r","Extreme cold/snow can increase health risks.\r","Frost may damage standing crops and orchards in adjoining plains.",
	"action": "Avoid non-essential travel to high-altitude and snowfall-prone areas, and use snowchains.\r","Ensure adequate heating, warm clothing, and protection for vulnerable populations.\r","Communities should follow local advisories.\r","Authorities should remain prepared for snow clearance, emergency response, and power restoration.",
	"type": "2",
	"lat_long": "[\"36.37683240010968\",\"74.1854310938566\"]",
	"image_url": "https://alert.ndma.gov.pk/public/storage/uploads/images/5jDVmuHSKi2qtKpbct9EoWO2gLp5Sul8oOGi1ICt.png",
	"priority": "3",
	"status": 1,
	"user_id": null,
	"category_alerts_id": 17,
	"status_changed_by_id": null,
	"created_at": "14-01-26",
	"updated_at": "14-01-26",
	"name": "Cold Wave",
	"icon_1": "https://alert.ndma.gov.pk/public/storage/uploads/icon_ones/O8lsBdqRxjqP4S5fAqAb2IddfkWRrJ3sSsHb7qM3.png",
	"icon_2": "https://alert.ndma.gov.pk/public/storage/uploads/icon_twos/kTZsAS2VGMOsJrBmxUvjxnb0Zng2LEgxZyrC4KnF.png",
	"icon_3": null,
	"latitude": "36.37683240010968",
	"longitude": "74.1854310938566",
	"audio": null
}
"""
                      } 
                    ] 
                },
                {
                    "role": "assistant",
                    "content": """
{
  "category": "Met",
  "event": "Cold Wave and Snowfall",
  "urgency": "Immediate",
  "severity": "Severe",
  "description": "A strong cold wave is expected to bring very cold to extremely cold conditions, particularly during nights and early mornings. Moderate to heavy snowfall is likely in high-altitude and hilly areas, while cold, dry weather with frost pockets is anticipated in adjacent plains. Impacts include potential disruptions to transport infrastructure and increased risk of landslide.",
  "instructions": ["1. Avoid non-essential travel to high-altitude and snowfall-prone areas, and use snow chains if driving is necessary.","2. Ensure adequate heating arrangements and wear warm clothing to prevent health risks from extreme cold.","3. Farmers should take measures to protect standing crops and orchards from frost.",""],
  "effective_from": "2026-01-14T00:00:00Z",
  "effective_until": "2026-01-20T23:59:59Z",
  "areas": [
    {
      "place_names": ["Gilgit Baltistan","North Khyber Pakhtunkhwa","Azad Kashmir"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instructions": null
    }
  ]
}
"""
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json_prompt},
                      {
                        "type": "text",
                        "text":"""
#Rising Smog Levels in the country in coming days","","**Issue Date:** 23 Oct, 2025 03:54 PM","","SMOG is the combination of smoke and fog and develops from November to mid-December. 
The stable and dry weather conditions is conducive to smog level increase in coming days. Pakistan can face an alarming increase in smog levels across its major cities, aggravated by recent stable meteorological conditions. Combination of industrial pollution, vehicular emissions, and conducive weather patterns may lead to an increase of air pollution, posing threats to public health and the environment in the coming days.","
Stable weather conditions, will contribute to the accumulation of harmful pollutants in the atmosphere. Calm wind pattern, lower temperatures, and humidity may prevent pollutants from dispersing and causing thick layers of smog to linger on Eastern parts of Punjab (Lahore, Gujranwala, Sheikhupura, Kasur, Nankana Sahib, Faisalabad, Multan, Bahawalpur, Rahim Yar Khan, Bahawalnagar and Khanpur)
.","Impacts","The rise in smog levels may trigger an increase in respiratory illnesses, asthma cases, and other pollution-related health problems. Vulnerable populations, including children, the elderly, and people with pre-existing health conditions, are at high risk.","Poor air quality can cause reduced visibility on roads, leading to a surge in traffic accidents. Outdoor activities can also be disrupted.","
For daily weather updates please visit:","www.pmd.gov.pk",",","Pak Weather Application",", \r","Social Media platforms & CAP (Alert).
"""
                      } 
                    ] 
                },
                {
                    "role": "assistant",
                    "content": """
{
  "category": "Env",
  "event": "Rising Smog Levels",
  "urgency": "Expected",
  "severity": "Severe",
  "description": "Stable and dry weather conditions are contributing to the accumulation of pollutants, leading to an alarming increase in smog levels. This situation poses threats to public health, particularly respiratory illnesses, and reduces visibility on roads.",
  "instructions": ["1. Wear face masks when outdoors to minimize inhalation of pollutants.","2. Limit prolonged outdoor activities, especially for children, the elderly, and those with respiratory conditions.","3. Keep windows closed to maintain indoor air quality and use air purifiers if available.","4. Drive with extreme caution and use fog lights due to reduced visibility.","5. Stay hydrated and seek medical attention if experiencing breathing difficulties.","[AI-generated]"],
  "effective_from": "2025-11-01T00:00:00Z",
  "effective_until": "2025-12-10T23:59:59Z",
  "areas": [
    {
      "place_names": ["Central Punjab","South Punjab"],
      "specific_effective_from": null,
      "specific_effective_until": null,
      "specific_urgency": null,
      "specific_severity": null,
      "specific_instructions": null
    }
  ]
}
"""
                },
                request
            ]