from pydantic import BaseModel


class OperationCancelResponse(BaseModel):
    status: str
    accepted: bool
