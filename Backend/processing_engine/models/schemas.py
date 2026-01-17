from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

# Alerts Enums
class AlertCategory(str, Enum):
    GEO = "Geo"
    MET = "Met"
    SAFETY = "Safety"
    SECURITY = "Security"
    RESCUE = "Rescue"
    FIRE = "Fire"
    HEALTH = "Health"
    ENV = "Env"
    TRANSPORT = "Transport"
    INFRA = "Infra"
    CBRNE = "CBRNE"
    OTHER = "Other"


class AlertUrgency(str, Enum):
    IMMEDIATE = "Immediate"
    EXPECTED = "Expected"
    FUTURE = "Future"
    PAST = "Past"
    UNKNOWN = "Unknown"


class AlertSeverity(str, Enum):
    EXTREME = "Extreme"
    SEVERE = "Severe"
    MODERATE = "Moderate"
    MINOR = "Minor"
    UNKNOWN = "Unknown"

#LLM structured response
class AreaList(BaseModel):
    """Represents a specific area or group if areas sharing same overrides (or none) affected by the alert."""
    place_names: List[str]
    specific_effective_from: Optional[str] = None
    specific_effective_until: Optional[str] = None
    specific_urgency: Optional[AlertUrgency] = None
    specific_severity: Optional[AlertSeverity] = None
    specific_instruction: Optional[str] = None

class StructuredAlert(BaseModel):
    """Represents the response from the LLM, with unflattened area list"""
    category: AlertCategory
    event: str
    urgency: AlertUrgency
    severity: AlertSeverity
    description: str
    instruction: str
    effective_from: str
    effective_until: str
    areas: List[AreaList]

# For insertion into DB
class AlertArea(BaseModel):
    """Represents a specific area affected by the alert."""
    alert_id: str
    place_id: str
    specific_effective_from: Optional[datetime] = None
    specific_effective_until: Optional[datetime] = None
    specific_urgency: Optional[AlertUrgency] = None
    specific_severity: Optional[AlertSeverity] = None
    specific_instruction: Optional[str] = None

class Alert(BaseModel):
    """Complete alert data following a CAP inspired format"""
    id: str
    document_id: str
    category: AlertCategory
    event: str
    urgency: AlertUrgency
    severity: AlertSeverity
    description: str
    instruction: str
    effective_from: datetime
    effective_until: datetime

class DocumentPayload(BaseModel):
    """Schema for the message payload/content"""
    url: Optional[str]
    title: str
    source: Literal["NDMA", "NEOC", "PMD"]
    filetype: Literal["pdf", "pptx", "txt", "gif", "png", "jpeg", "jpg"]
    raw_text: Optional[str] = None
    document_id: str
    posted_date: str

class QueueJob(BaseModel):
    """Complete schema for a PGMQ queue job"""
    msg_id: int
    read_ct: int
    enqueued_at: datetime
    vt: datetime
    message: DocumentPayload
