"""Durable per-user alert rules and deduplicated events; public market polling."""

import json
import os
import sqlite3
import threading
import time
import urllib.request
import uuid

from app_layer.services.analysis import PairAnalysisService
from app_layer.services.providers import public_source


class AlertService:
    def __init__(self, path: str):
        from persistence.factory import is_postgres
        if is_postgres(path):
            from persistence.postgres import Connection
            self._db = Connection(path)
        else:
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._db:
            self._db.executescript("""
              CREATE TABLE IF NOT EXISTS alert_rules (
                owner TEXT NOT NULL, watchlist TEXT NOT NULL, payload TEXT NOT NULL,
                last_scan INTEGER, error TEXT, PRIMARY KEY(owner, watchlist));
              CREATE TABLE IF NOT EXISTS alert_events (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, event_key TEXT NOT NULL,
                payload TEXT NOT NULL, created INTEGER NOT NULL, seen INTEGER NOT NULL DEFAULT 0,
                telegram_status TEXT NOT NULL DEFAULT 'disabled', UNIQUE(owner, event_key));
              CREATE TABLE IF NOT EXISTS alert_states (
                owner TEXT NOT NULL, state_key TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY(owner, state_key));
            """)

    def close(self):
        with self._lock:
            self._db.close()

    def rules(self, owner=None):
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM alert_rules" + (" WHERE owner=?" if owner else ""),
                (owner,) if owner else (),
            ).fetchall()
        return [
            {
                **json.loads(r["payload"]),
                "owner": r["owner"],
                "watchlist_id": r["watchlist"],
                "last_scan": r["last_scan"],
                "error": r["error"],
            }
            for r in rows
        ]

    def save_rule(self, owner, watchlist, payload):
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO alert_rules(owner,watchlist,payload) VALUES(?,?,?)
                ON CONFLICT(owner,watchlist) DO UPDATE SET payload=excluded.payload, error=NULL""",
                (owner, watchlist, json.dumps(payload)),
            )

    def events(self, owner):
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM alert_events WHERE owner=? ORDER BY created DESC LIMIT 200", (owner,)
            ).fetchall()
        return [
            {
                **json.loads(r["payload"]),
                "id": r["id"],
                "created_at_ms": r["created"],
                "seen": bool(r["seen"]),
                "telegram_status": r["telegram_status"],
            }
            for r in rows
        ]

    def mark_seen(self, owner):
        with self._lock, self._db:
            self._db.execute("UPDATE alert_events SET seen=1 WHERE owner=?", (owner,))

    def record(self, owner, key, payload, telegram=False):
        event_id = uuid.uuid4().hex
        with self._lock, self._db:
            cur = self._db.execute(
                """INSERT INTO alert_events
                (id,owner,event_key,payload,created,telegram_status) VALUES(?,?,?,?,?,?) ON CONFLICT(owner,event_key) DO NOTHING""",
                (
                    event_id,
                    owner,
                    key,
                    json.dumps(payload),
                    time.time_ns() // 1_000_000,
                    "pending" if telegram else "disabled",
                ),
            )
        return event_id if cur.rowcount else None

    def changed(self, owner, key, value):
        with self._lock, self._db:
            old = self._db.execute(
                "SELECT value FROM alert_states WHERE owner=? AND state_key=?", (owner, key)
            ).fetchone()
            self._db.execute(
                "INSERT INTO alert_states VALUES(?,?,?) ON CONFLICT(owner,state_key) DO UPDATE SET value=excluded.value", (owner, key, value)
            )
        return old is None or old["value"] != value

    def tick(self, container):
        for rule in self.rules():
            if not rule["enabled"]:
                continue
            owner = rule["owner"]
            error = None
            try:
                user = container.store.get_user(owner)
                if user is None or not user.active:
                    continue
                _, items = container.watchlists.get(user, rule["watchlist_id"])
                for item in items:
                    if not item.enabled:
                        continue
                    for tf in rule["timeframes"]:
                        try:
                            source = public_source(item.venue_id)
                            with source.lock:
                                analysis = PairAnalysisService(
                                    source.facade, container.strategies
                                ).analyze(
                                    user, item.symbol, tf, strategy_id=rule.get("strategy_id")
                                )
                            if (
                                not analysis["is_analysis_safe"]
                                or analysis["freshness"]["is_stale"]
                            ):
                                error = f"Stale or incomplete history for {item.symbol} ({tf})."
                                continue
                            prefix = (
                                f"{rule['watchlist_id']}:{item.id}:{tf}:{rule.get('strategy_id')}"
                            )
                            base = {
                                "symbol": item.symbol,
                                "venue": item.venue_id,
                                "timeframe": tf,
                                "watchlist_id": rule["watchlist_id"],
                                "strategy_id": rule.get("strategy_id"),
                            }
                            candidates = []
                            signal = analysis["signal"]
                            if signal["direction"] != "none":
                                ts = (
                                    signal["metadata"].get("signal_timestamp")
                                    or analysis["candles"][-1]["timestamp"]
                                )
                                candidates.append(
                                    (
                                        f"{prefix}:edge:{ts}:{signal['direction']}",
                                        {
                                            **base,
                                            "kind": "confirmed_entry"
                                            if analysis.get("market_state")
                                            else "range_touch",
                                            "message": (
                                                f"{signal['direction'].title()} confirmed: "
                                                f"{signal['reason']}"
                                                if analysis.get("market_state")
                                                else f"{signal['direction'].title()} edge touched"
                                            ),
                                            "price": signal["price"],
                                        },
                                    )
                                )
                            for failure in analysis["swing_failures"]:
                                if (
                                    failure["timestamp"]
                                    == analysis["freshness"]["last_closed_timestamp_ms"]
                                ):
                                    candidates.append(
                                        (
                                            f"{prefix}:sfp:{failure['timestamp']}:{failure['direction']}",
                                            {
                                                **base,
                                                "kind": "swing_failure",
                                                "message": (
                                                    f"{failure['direction'].title()} swing failure"
                                                ),
                                                "price": failure["level"],
                                            },
                                        )
                                    )
                            if analysis.get("market_state"):
                                extreme = bool(signal["metadata"].get("at_extreme"))
                                if (
                                    self.changed(owner, prefix + ":extreme", str(extreme))
                                    and extreme
                                ):
                                    candidates.append(
                                        (
                                            f"{prefix}:extreme:{analysis['candles'][-1]['timestamp']}",
                                            {
                                                **base,
                                                "kind": "range_extreme",
                                                "message": "Range extreme reached — "
                                                "wait for confirmation",
                                                "price": analysis["ticker_last"],
                                            },
                                        )
                                    )
                            regime = analysis.get("market_state") or analysis["regime"]["value"]
                            if (
                                self.changed(owner, prefix + ":regime", regime)
                                and regime != "insufficient_data"
                            ):
                                candidates.append(
                                    (
                                        f"{prefix}:regime:{analysis['freshness']['last_closed_timestamp_ms']}:{regime}",
                                        {
                                            **base,
                                            "kind": "breakout"
                                            if regime == "breakout"
                                            else "regime",
                                            "message": "Breakout — range invalidated"
                                            if regime == "breakout"
                                            else "Trending — don’t fade extremes"
                                            if regime.startswith("trending")
                                            else regime.replace("_", " ").title(),
                                            "price": analysis["ticker_last"],
                                        },
                                    )
                                )
                            for key, event in candidates:
                                eid = self.record(owner, key, event, rule["telegram"])
                                if eid and rule["telegram"]:
                                    self._telegram(eid, rule["telegram_chat_id"], event)
                        except Exception:
                            error = (
                                f"Could not scan {item.symbol} on {item.venue_id} ({tf}). "
                                "Check source, symbol and history."
                            )
            except Exception:
                error = "Watchlist or strategy is unavailable. Update this monitor."
            with self._lock, self._db:
                self._db.execute(
                    "UPDATE alert_rules SET last_scan=?,error=? WHERE owner=? AND watchlist=?",
                    (time.time_ns() // 1_000_000, error, owner, rule["watchlist_id"]),
                )

    def _telegram(self, event_id, chat_id, event):
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        status = "not_configured"
        if token and chat_id:
            try:
                body = json.dumps(
                    {
                        "chat_id": chat_id,
                        "text": (
                            f"{event['symbol']} · {event['timeframe']} · {event['venue']}\n"
                            f"{event['message']}\nPrice: {event['price']}"
                        ),
                    }
                ).encode()
                request = urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    status = "sent" if json.load(response).get("ok") else "failed"
            except Exception:
                status = "failed"
        with self._lock, self._db:
            self._db.execute(
                "UPDATE alert_events SET telegram_status=? WHERE id=?", (status, event_id)
            )
