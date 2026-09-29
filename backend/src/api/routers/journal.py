"""Private, authenticated notes; even owners only access their own journal."""
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from api.dependencies import ContainerDep, CurrentUser

router = APIRouter(prefix="/journal", tags=["journal"])

class EntryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=30000)
    category: Literal["idea", "trade_plan", "reflection"] = "idea"
    symbol: str = Field(default="", max_length=60)
    timeframe: Literal["", "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"] = ""

@router.get("")
def list_entries(user: CurrentUser, container: ContainerDep):
    return container.store.list_journal_entries(user.id)

@router.post("", status_code=201)
def create_entry(payload: EntryInput, user: CurrentUser, container: ContainerDep):
    return container.store.save_journal_entry(user.id, str(uuid4()), payload.model_dump(), create=True)

@router.put("/{entry_id}")
def update_entry(entry_id: str, payload: EntryInput, user: CurrentUser, container: ContainerDep):
    return container.store.save_journal_entry(user.id, entry_id, payload.model_dump())

@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: str, user: CurrentUser, container: ContainerDep):
    container.store.delete_journal_entry(user.id, entry_id)
