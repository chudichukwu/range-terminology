"""api: FastAPI presentation layer for the application services.

Contains no domain business logic: routers validate HTTP input via pydantic
schemas, delegate to :mod:`app_layer` services and map application errors
onto a stable JSON error envelope.
"""

from api.app import create_app

__version__ = "0.1.0"

__all__ = ["create_app", "__version__"]
