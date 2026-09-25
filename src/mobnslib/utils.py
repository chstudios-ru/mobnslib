from __future__ import annotations
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional
import httpx
from .exceptions import NotJSONResponse

class HTMLTruncateHandler(logging.FileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        original_msg = record.msg
        msg_lower = str(record.msg).lower()
        if "<!doctype html>" in msg_lower:
            record.msg = "<!DOCTYPE html>..."

        if len(str(record.msg)) > 1000:
            record.msg = str(record.msg)[:1000] + "..."
        super().emit(record)
        self.flush()

def check_response(response: httpx.Response, log: logging.Logger) -> Any:
    if response.is_error:
        sent_payload = response.request.content.decode('utf-8') if hasattr(response.request, 'content') else ""
        log.error(f"HTTP error: {response.status_code} - {response.text}")
        log.debug(f"Sent payload: {sent_payload}")
        response.raise_for_status()

    try:
        return response.json()
    except (json.JSONDecodeError, ValueError) as e:
        log.error("Response is not valid JSON", exc_info=True)
        raise NotJSONResponse() from e

def get_week_range(pattern: str, day: Optional[str | datetime | date] = None) -> tuple[str, str]:
    if not day:
        date_obj = datetime.now()
    elif hasattr(day, 'strftime'):
        date_obj = day
    else:
        date_obj = datetime.strptime(day, pattern)

    start_of_week = date_obj - timedelta(days=date_obj.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    return start_of_week.strftime(pattern), end_of_week.strftime(pattern)