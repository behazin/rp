from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Dict, Any

# --- Source Schemas ---
class SourceBase(BaseModel):
    name: str
    url: HttpUrl

class SourceCreate(SourceBase):
    pass

class SourceInDB(SourceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Destination Schemas ---
class DestinationBase(BaseModel):
    name: str
    platform: str
    credentials: Dict[str, Any]

class DestinationCreate(DestinationBase):
    pass

class DestinationInDB(DestinationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)