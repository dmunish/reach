from langchain_core.tools import tool
from Backend.agenting import get_supabase

FORBIDDEN_KEYWORDS = frozenset({
    "drop", "delete", "update", "insert",
    "alter", "truncate", "grant", "revoke", "create"
})


@tool
def execute_sql(query: str) -> dict:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns: { "columns": [...], "rows": [...], "row_count": int}

    The schema of REACH is based on the Common Alerting Protocol standard, with some modifications.
    It consists of the following tables:
    - documents: Metadata of scraped documents.
    - alerts: The main table containing alert information.
    - alert_areas: A many-to-one relationship with alerts. Contains information about the alreas relavant to 
    an alert and any area-specific overrides.
    - places: Contains geometry data for Pakistan's administrative boundaries (national and subnational)
    - alert_search_index: A denormalized view for fast searching of alerts.

    
    Available schema:

    | Table                | Column                     | Description                                    |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | documents            | id                         | UUID primary key                               |
    |                      | source                     | Name of the originating data source            |
    |                      | posted_date                | Date the document was published                |
    |                      | title                      | Document title                                 |
    |                      | url                        | URL of the source document                     |
    |                      | filename                   | Unique filename used for storage               |
    |                      | filetype                   | File format or MIME type                       |
    |                      | processed_at               | Timestamp when processed by the pipeline       |
    |                      | structured_text            | Extracted structured content as JSONB          |
    |                      | scraped_at                 | Timestamp when the document was scraped        |
    |                      | raw_text                   | Raw plain-text content of the file             |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | alerts               | id                         | UUID primary key                               |
    |                      | document_id                | FK → documents.id                              |
    |                      | category                   | CAP-based category (Geo, Met, Safety, etc.)    |
    |                      | event                      | Short event label, e.g. Flash Flood            |
    |                      | urgency                    | Immediate / Expected / Future / Past / Unknown |
    |                      | severity                   | Extreme / Severe / Moderate / Minor / Unknown  |
    |                      | description                | Full narrative description of the alert        |
    |                      | instruction                | Recommended action for affected people         |
    |                      | effective_from             | Start of the alert validity window             |
    |                      | effective_until            | End of the alert validity window               |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | alert_areas          | id                         | UUID primary key                               |
    |                      | alert_id                   | FK → alerts.id                                 |
    |                      | place_id                   | FK → places.id                                 |
    |                      | specific_effective_from    | Area-level override for effective start        |
    |                      | specific_effective_until   | Area-level override for effective end          |
    |                      | specific_urgency           | Area-level urgency override                    |
    |                      | specific_severity          | Area-level severity override                   |
    |                      | specific_instruction       | Area-level protective instruction override     |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | places               | id                         | UUID primary key                               |
    |                      | name                       | Place name                                     |
    |                      | parent_id                  | Self-referencing FK to parent place            |
    |                      | parent_name                | Denormalised parent place name                 |
    |                      | hierarchy_level            | Depth in the geographic hierarchy              |
    |                      | polygon                    | PostGIS geometry of the place boundary         |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | alert_search_index   | alert_id                   | PK + FK → alerts.id (cascade delete)           |
    |                      | centroid                   | PostGIS point centroid of covered area         |
    |                      | bbox                       | Bounding-box geometry of covered area          |
    |                      | unioned_polygon            | Merged polygon of all linked place geometries  |
    |                      | search_text                | Concatenated full-text search string           |
    |                      | category                   | Denormalised from alerts.category              |
    |                      | severity                   | Denormalised from alerts.severity              |
    |                      | urgency                    | Denormalised from alerts.urgency               |
    |                      | event                      | Denormalised from alerts.event                 |
    |                      | description                | Denormalised from alerts.description           |
    |                      | instruction                | Denormalised from alerts.instruction           |
    |                      | source                     | Denormalised from documents.source             |
    |                      | url                        | Denormalised from documents.url                |
    |                      | posted_date                | Denormalised from documents.posted_date        |
    |                      | effective_from             | Denormalised from alerts.effective_from        |
    |                      | effective_until            | Denormalised from alerts.effective_until       |
    |                      | affected_places            | Array of place name strings for the alert      |
    |                      | last_updated_at            | Timestamp of the last index refresh            |
    |                      | place_ids                  | Array of linked place UUIDs                    |

    Useful patterns:
      - ST_AsGeoJSON(polygon) → GeoJSON for map highlighting
      - ST_X(centroid), ST_Y(centroid) → lon, lat
      - Use alert_search_index for fast analytical queries (pre-joined, indexed)
      - severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'
      - urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'
      - category values: 'Geo','Met','Safety','Security','Rescue','Fire',
                         'Health','Env','Transport','Infra','CBRNE','Other'
    """
    normalized = query.lower()
    if any(kw in normalized for kw in FORBIDDEN_KEYWORDS):
        return {"error": "Write operations are not permitted."}

    try:
        client = get_supabase()
        result = client.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        columns = list(rows[0].keys()) if rows else []
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e)}
