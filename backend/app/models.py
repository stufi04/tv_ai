from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

MAX_SHOWS_PER_EPISODE = 2


class ApiModel(BaseModel):
    """Base for models exposed over HTTP: camelCase in JSON, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        frozen=True,
    )


class Show(ApiModel):
    id: str
    title: str
    year: int | None
    network: str | None
    genres: list[str]
    summary: str
    image_url: str | None = None
    # TVmaze's popularity "weight", 0-100.
    popularity: int = 0


class ShowPage(ApiModel):
    items: list[Show]
    total: int
    next_offset: int | None
    # True while the catalogue is being downloaded for the first time.
    syncing: bool = False


class EpisodeRequest(ApiModel):
    show_ids: list[str] = Field(min_length=1, max_length=MAX_SHOWS_PER_EPISODE)

    @field_validator("show_ids")
    @classmethod
    def ids_must_be_unique(cls, show_ids: list[str]) -> list[str]:
        if len(set(show_ids)) != len(show_ids):
            raise ValueError("show ids must be unique")
        return show_ids


class Episode(ApiModel):
    show_ids: list[str]
    title: str
    logline: str
    story: str


class EpisodeDraft(BaseModel):
    """Structured output we ask the text model to produce."""

    title: str = Field(description="A catchy episode title.")
    logline: str = Field(description="A one-sentence teaser for the episode.")
    story: str = Field(
        description="The episode as a short story of 250-350 words, split into paragraphs with blank lines."
    )
