#!/usr/bin/env python3
"""
Standalone CLI for generating daily recommendations from WakaTime activity.

Dependencies: Python standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Tuple

WAKATIME_BASE_URL = "https://wakatime.com/api/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = (
    "You are a concise assistant. Output MUST use only ASCII characters. "
    "No emojis, smart quotes, non-breaking spaces, or fancy dashes. "
    "Use '-' for bullets; use straight quotes ' and \". "
    "Analyze software development activity data and provide practical, clear recommendations."
)

USER_QUESTION = (
    "Here is my WakaTime JSON for the day. "
    "Can you provide detailed and practical recommendations based on this data?"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate recommendations from WakaTime data using OpenAI. "
            "Arguments: wakatime_token openai_token [date]"
        )
    )
    parser.add_argument("wakatime_token", help="WakaTime API token")
    parser.add_argument("openai_token", help="OpenAI API token")
    parser.add_argument(
        "date",
        nargs="?",
        help="Target date in YYYY-MM-DD format. Defaults to yesterday.",
    )
    return parser.parse_args()


def parse_target_date(date_text: str | None) -> dt.date:
    if not date_text:
        return dt.date.today() - dt.timedelta(days=1)

    try:
        target_date = dt.datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")

    if target_date >= dt.date.today():
        raise ValueError("Date must be in the past.")

    return target_date


def http_get_json(url: str, params: Dict[str, str], timeout: int) -> Tuple[int, str, Dict[str, Any]]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_text = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        raw_text = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while requesting {url}: {exc}")

    try:
        payload = json.loads(raw_text) if raw_text else {}
    except json.JSONDecodeError:
        payload = {}

    return status_code, raw_text, payload


def http_post_json(
    url: str,
    body: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int,
) -> Tuple[int, str, Dict[str, Any]]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_text = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        raw_text = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while requesting {url}: {exc}")

    try:
        payload = json.loads(raw_text) if raw_text else {}
    except json.JSONDecodeError:
        payload = {}

    return status_code, raw_text, payload


def fetch_wakatime_heartbeats(wakatime_token: str, target_date: dt.date) -> Tuple[str, Dict[str, Any]]:
    url = f"{WAKATIME_BASE_URL}/users/current/heartbeats"
    status, raw_text, payload = http_get_json(
        url=url,
        params={"date": target_date.isoformat(), "api_key": wakatime_token},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if status == 401:
        raise RuntimeError("WakaTime token is invalid (401 Unauthorized).")
    if not (200 <= status < 300):
        raise RuntimeError(f"WakaTime request failed with HTTP {status}: {raw_text[:300]}")

    return raw_text, payload


def build_user_message(heartbeats_payload: Dict[str, Any], target_date: dt.date) -> str:
    compact_payload = json.dumps(heartbeats_payload, ensure_ascii=False, separators=(",", ":"))
    max_chars = 120_000
    if len(compact_payload) > max_chars:
        compact_payload = compact_payload[:max_chars] + "...(truncated)"

    return (
        f"Source: wakatime\\n"
        f"Date: {target_date.isoformat()}\\n"
        f"Raw daily data (heartbeats):\\n```json\\n{compact_payload}\\n```\\n\\n"
        f"Question: {USER_QUESTION}"
    )


def call_openai(openai_token: str, user_message: str) -> Tuple[str, Dict[str, Any]]:
    url = f"{OPENAI_BASE_URL}/chat/completions"
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {
        "Authorization": f"Bearer {openai_token}",
        "Content-Type": "application/json",
    }

    status, raw_text, payload = http_post_json(
        url=url,
        body=body,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if status == 401:
        raise RuntimeError("OpenAI token is invalid (401 Unauthorized).")
    if not (200 <= status < 300):
        raise RuntimeError(f"OpenAI request failed with HTTP {status}: {raw_text[:400]}")

    return raw_text, payload


def extract_recommendations(openai_payload: Dict[str, Any]) -> str:
    choices = openai_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI response does not contain choices.")

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        # Some models may return structured content blocks.
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        text = "\n".join(parts).strip()
    else:
        text = ""

    if not text:
        raise RuntimeError("OpenAI response returned empty recommendations.")

    return text


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def main() -> int:
    args = parse_args()

    try:
        target_date = parse_target_date(args.date)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        wakatime_raw_text, wakatime_payload = fetch_wakatime_heartbeats(
            wakatime_token=args.wakatime_token,
            target_date=target_date,
        )

        print_section("RAW WAKATIME PAYLOAD")
        print(wakatime_raw_text)

        user_message = build_user_message(
            heartbeats_payload=wakatime_payload,
            target_date=target_date,
        )

        openai_raw_text, openai_payload = call_openai(
            openai_token=args.openai_token,
            user_message=user_message,
        )

        print_section("RAW OPENAI PAYLOAD")
        print(openai_raw_text)

        recommendations = extract_recommendations(openai_payload)

        print_section("FINAL RECOMMENDATIONS")
        print(recommendations)

        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
