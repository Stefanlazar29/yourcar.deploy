# backend/models.py — Pydantic models pentru Mulberry Brain

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CloudFile(BaseModel):
    """Document uploadat în Mulberry Cloud"""
    id: int
    type: str  # "ITP", "RCA", "Talon", etc.
    filename: str
    verified: bool = False
    ai_confidence: Optional[float] = None
    uploaded_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class Reminder(BaseModel):
    """Task de mentenanță"""
    id: int
    task: str
    status: str = "pending"  # "pending", "completed", "overdue"
    due_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class MulberryBrain(BaseModel):
    """
    Orchestratorul central — leagă toate datele vehiculului
    VIN-centric: fiecare vehicul = un creier independent
    """
    vin: str
    owner_email: str
    mlbr_code: str
    
    # Date înmatriculare (bazice)
    marca: Optional[str] = None
    model: Optional[str] = None
    series: Optional[str] = None
    an: Optional[int] = None
    nr: Optional[str] = None  # plate number
    
    # Sateliți (relații)
    cloud_files: List[CloudFile] = Field(default_factory=list)
    reminders: List[Reminder] = Field(default_factory=list)
    
    # Rezultate "gândire" (calculate automat)
    soft_score: float = 0.0
    status_health: str = "Calibrare necesară"
    last_sync: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class SyncRequest(BaseModel):
    """Request pentru endpoint /sync"""
    vin: str
    owner_email: Optional[str] = None
    cloud_files: Optional[List[CloudFile]] = None
    reminders: Optional[List[Reminder]] = None
    # Opțional: trigger explicit pentru recalculare
    force_recalc: bool = False

class SyncResponse(BaseModel):
    """Response de la /sync cu analiza nouă"""
    vin: str
    soft_score: float
    status_health: str
    alerts: List[str] = Field(default_factory=list)
    last_sync: str
