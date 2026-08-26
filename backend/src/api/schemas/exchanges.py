from pydantic import BaseModel, Field, SecretStr


class ExchangeConnectRequest(BaseModel):
    venue_id: str = Field(min_length=2, max_length=30, examples=["binance"])
    display_name: str = Field(min_length=1, max_length=60)
    api_key: SecretStr = Field(min_length=4, max_length=200)
    secret: SecretStr = Field(min_length=4, max_length=4000)
    password: SecretStr | None = Field(default=None, max_length=400)
    sandbox: bool = False


class ExchangeConnectionOut(BaseModel):
    """Metadata only — credential material can never appear here."""

    id: str
    venue_id: str
    display_name: str
    status: str
    sandbox: bool
    created_at_ms: int
    updated_at_ms: int
