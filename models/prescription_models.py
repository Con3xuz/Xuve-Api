"""
OMNI - Modelos de Recetas Médicas
=================================
Sistema de recetas digitales que conecta médicos con Farmabien.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PrescriptionMedication(BaseModel):
    """Medicamento individual en una receta"""

    name: str
    dosage: str = ""
    frequency: str = ""
    duration: str = ""
    quantity: int = 1
    notes: str = ""
    product_id: Optional[str] = None


class PrescriptionCreate(BaseModel):
    """Modelo para crear una receta"""

    patient_name: str = Field(..., min_length=1)
    patient_cedula: str = Field(..., min_length=1)
    patient_phone: str = ""
    patient_email: str = ""
    diagnosis: str = ""
    medications: List[PrescriptionMedication] = []
    notes: str = ""
    pharmacy_store_id: Optional[str] = None


class PrescriptionUpdate(BaseModel):
    """Modelo para actualizar estado de receta"""

    status: Optional[str] = None
    pharmacy_notes: Optional[str] = None
