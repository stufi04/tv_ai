from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.catalog import ShowCatalog, UnknownShowError
from app.dependencies import get_catalog, get_episode_generator
from app.models import Episode, EpisodeRequest, Show
from app.services.episode_generator import EpisodeGenerator

router = APIRouter(prefix="/api")

CatalogDep = Annotated[ShowCatalog, Depends(get_catalog)]
GeneratorDep = Annotated[EpisodeGenerator, Depends(get_episode_generator)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/shows")
def list_shows(catalog: CatalogDep) -> list[Show]:
    return catalog.all()


@router.post("/episodes")
async def create_episode(request: EpisodeRequest, catalog: CatalogDep, generator: GeneratorDep) -> Episode:
    try:
        shows = catalog.get_many(request.show_ids)
    except UnknownShowError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return await generator.generate(shows)
