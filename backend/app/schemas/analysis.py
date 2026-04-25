from datetime import datetime
from pydantic import BaseModel


class ColorInfo(BaseModel):
    name: str
    rgb: tuple[int, int, int]
    confidence: float


class VehicleAnalysisResponse(BaseModel):
    id: int
    job_id: int
    source_ref: str
    frame_index: int
    track_id: int | None
    bbox: dict
    logo: str
    plate_number: str
    colors: list[ColorInfo]
    annotated_image_base64: str
    created_at: datetime


class VehicleAnalysisListItem(BaseModel):
    id: int
    job_id: int
    source_ref: str
    frame_index: int
    track_id: int | None
    logo: str
    plate_number: str
    created_at: datetime


class VehicleAnalysisDetail(VehicleAnalysisListItem):
    bbox: dict
    colors: list[ColorInfo]
    annotated_image_base64: str
