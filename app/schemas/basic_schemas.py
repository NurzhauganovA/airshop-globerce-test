from pydantic import BaseModel
from typing import List, Optional


class PaginatedResponse(BaseModel):
    """
    model for paginated response
    """

    total_count: int
    has_next_page: bool
    has_previous_page: bool
    start: Optional[str] = None
    end: Optional[str] = None
    items: List[BaseModel]
