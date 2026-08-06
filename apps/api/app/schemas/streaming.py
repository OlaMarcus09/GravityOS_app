from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ArtistStreamingLinkCreate(BaseModel):
    soundcharts_uuid: UUID
    platform: Literal["soundcharts"] = "soundcharts"
