from pydantic import BaseModel


class BuildResponse(BaseModel):
    build: str
    store: str
    model: list[str]
    classifier_model: list[str]
