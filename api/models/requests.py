from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    session_id: str
    query: str = Field(..., max_length=500)
    top_k: int = Field(5, le=10)
    user_id: str = ""

class AdminApprovalRequest(BaseModel):
    approval_id: str
    decision: str
    reason: str = ""
