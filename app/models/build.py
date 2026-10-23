from pydantic import BaseModel


class MinimumApp(BaseModel):
    ios: int
    android: int


class BuildResponse(BaseModel):
    build: str
    store: str
    model: list[str]
    classifier_model: list[str]
    minimum_app: MinimumApp
