"""FastAPI dependency injection — предоставляет use-case объекты из контейнера."""

from collections.abc import Iterator

from fastapi import Request

from backend.composition import ApplicationContainer, ApplicationDatabase


def get_container(request: Request) -> Iterator[ApplicationContainer]:
    database: ApplicationDatabase = request.app.state.database
    # FastAPI caches this dependency for the request, including authentication.
    with database.sessions() as session:
        yield ApplicationContainer(session, database.jwt_secret)
