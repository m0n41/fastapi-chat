from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class MessageCreate(BaseModel):
    
    content: str = Field(min_length=1, max_length=2000)
    
class MessageResponse(BaseModel):
    
    id: int
    user_id: int
    username: str
    content: str
    created_at: datetime
        
    model_config = ConfigDict(from_attributes=True)