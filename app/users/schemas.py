from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)
    
class UserResponse(BaseModel):
    
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
class UserLogin(BaseModel):
    
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8)
    