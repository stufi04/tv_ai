from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.catalog import ShowCatalog, UnknownShowError
from app.dependencies import get_catalog, get_catalog_store, get_episode_generator
from app.models import Episode, EpisodeRequest, ShowPage
from app.services.catalog_store import CatalogStore
from app.services.episode_generator import EpisodeGenerator

router = APIRouter(prefix="/api")

CatalogDep = Annotated[ShowCatalog, Depends(get_catalog)]
StoreDep = Annotated[CatalogStore, Depends(get_catalog_store)]
GeneratorDep = Annotated[EpisodeGenerator, Depends(get_episode_generator)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/shows")
def list_shows(
    store: StoreDep,
    q: Annotated[str, Query(max_length=100, description="Search titles and networks.")] = "",
    genre: Annotated[str, Query(max_length=50)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    seed: Annotated[int, Query(description="Shuffles the default popular listing; keep it fixed while paging.")] = 0,
) -> ShowPage:
    page = store.catalog.search(query=q, genre=genre, offset=offset, limit=limit, seed=seed)
    return page.model_copy(update={"syncing": store.syncing})


@router.get("/genres")
def list_genres(catalog: CatalogDep) -> list[str]:
    return catalog.genres()


@router.post("/episodes")
async def create_episode(request: EpisodeRequest, catalog: CatalogDep, generator: GeneratorDep) -> Episode:
    try:
        shows = catalog.get_many(request.show_ids)
    except UnknownShowError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return await generator.generate(shows)
