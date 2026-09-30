"""Private labelled examples. Browser snapshots are observations, not trusted signals."""
from typing import Literal
from uuid import uuid4
from statistics import median
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from api.dependencies import CurrentUser, ContainerDep
from api.schemas.analysis import AnalysisOut
from app_layer.errors import NotFoundError

router = APIRouter(prefix='/observed-ranges', tags=['observed ranges'])

class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
    low: float = Field(gt=0)
    high: float = Field(gt=0)
    notes: str = Field(default='', max_length=4000)
    reason: Literal['outer_boundaries', 'internal_consolidation', 'support_resistance', 'reclaim', 'other'] = 'outer_boundaries'
    snapshot: AnalysisOut

    @model_validator(mode='after')
    def validate_observation(self):
        if self.high <= self.low:
            raise ValueError('High must exceed low')
        if not 1 <= len(self.snapshot.candles) <= 1500:
            raise ValueError('Save with 1–1500 loaded candles')
        return self


def owned(container, user, entry_id):
    entry = next((r for r in container.store.observed_ranges(user.id) if r['id'] == entry_id), None)
    if entry is None:
        raise NotFoundError('saved range not found')
    return entry


def summary(entry):
    snap = entry.get('snapshot')
    if snap is None:
        return {k:v for k,v in entry.items() if k != 'snapshot'} | dict(candle_count=0, asof=None, automatic_low=None, automatic_high=None)
    return {k: v for k, v in entry.items() if k != 'snapshot'} | dict(
        symbol=snap['symbol'], timeframe=snap['timeframe'], venue=snap.get('venue'),
        candle_count=len(snap['candles']), asof=snap['freshness'].get('last_closed_timestamp_ms'),
        automatic_low=snap['range']['low'], automatic_high=snap['range']['high'])

@router.get('')
def list_ranges(user: CurrentUser, container: ContainerDep):
    return [summary(e) for e in container.store.observed_ranges(user.id)]

@router.get('/review')
def review(user: CurrentUser, container: ContainerDep):
    # Group comparable examples. Do not mix prices across symbols, venues or timeframes.
    groups = {}
    for e in container.store.observed_ranges(user.id):
        s = e.get('snapshot')
        if s is None:  # Screenshot labels lack verified historical candles.
            continue
        r = s['range']; lo, hi = r['low'], r['high']
        if lo is None or hi is None or hi <= lo:
            continue
        key = (s['symbol'], s.get('venue'), s['timeframe'])
        groups.setdefault(key, []).append((e, (e['low']-lo)/(hi-lo), (e['high']-hi)/(hi-lo)))
    results=[]
    for (symbol, venue, timeframe), rows in groups.items():
        # Duplicate labels of the same observation are not independent examples.
        unique={r[0]['snapshot']['freshness'].get('last_closed_timestamp_ms'):r for r in reversed(rows)}
        sample=list(unique.values())
        evaluation = None
        if len(sample) >= 10:
            ordered = sorted(sample, key=lambda r: r[0]['created_at_ms'])
            cut = max(5, int(len(ordered) * .7))
            train, test = ordered[:cut], ordered[cut:]
            low_offset, high_offset = median(r[1] for r in train), median(r[2] for r in train)
            baseline = sum(abs(r[1]) + abs(r[2]) for r in test) / (2 * len(test))
            adjusted = sum(abs(r[1]-low_offset) + abs(r[2]-high_offset) for r in test) / (2 * len(test))
            evaluation = dict(training_examples=len(train), held_out_examples=len(test),
                baseline_error=baseline, adjusted_error=adjusted,
                improves=adjusted < baseline, low_offset=low_offset, high_offset=high_offset)
        results.append(dict(symbol=symbol,venue=venue,timeframe=timeframe,samples=len(sample),
            evaluation=evaluation, median_low_shift=median(r[1] for r in sample),median_high_shift=median(r[2] for r in sample)))
    return dict(status='collecting_examples', automatic_adaptation=False, groups=results)

@router.post('', status_code=201)
def save(payload: Observation, user: CurrentUser, container: ContainerDep):
    entry_id = str(uuid4())
    data = payload.model_dump(mode='json')
    data['provenance'] = 'user_supplied_chart_snapshot'
    container.store.save_observed_range(user.id, entry_id, data)
    return summary(owned(container,user,entry_id))

@router.get('/{entry_id}')
def get(entry_id: str, user: CurrentUser, container: ContainerDep):
    return owned(container,user,entry_id)

@router.delete('/{entry_id}', status_code=204)
def delete(entry_id: str, user: CurrentUser, container: ContainerDep):
    container.store.delete_observed_range(user.id,entry_id)
