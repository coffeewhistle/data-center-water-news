from datetime import datetime, timedelta, timezone, date
import urllib.parse
import config


def normalize_url(url):
    if not url:
        return url
    parsed = urllib.parse.urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    drop_prefixes = ("utm_",)
    drop_exact = {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src"}
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    kept_pairs = []
    for key, value in query_pairs:
        key_lower = key.lower()
        if key_lower in drop_exact or any(key_lower.startswith(prefix) for prefix in drop_prefixes):
            continue
        kept_pairs.append((key, value))
    query = urllib.parse.urlencode(sorted(kept_pairs))
    return urllib.parse.urlunparse((scheme, netloc, path, "", query, ""))


def as_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        if "T" in value:
            return datetime.fromisoformat(value).date()
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value}")


def build_run_plan(state):
    today_utc = datetime.now(timezone.utc).date()
    yesterday_utc = today_utc - timedelta(days=1)

    if not state.get("backfill_complete", False):
        start_date = as_date(state.get("backfill_progress_cutoff")) or as_date(state.get("backfill_start_date"))
        backfill_end_date = as_date(state.get("backfill_end_date"))
        if start_date is None or backfill_end_date is None:
            raise ValueError("Invalid ingestion state: missing backfill dates.")

        if start_date > backfill_end_date:
            return {
                "mode": "backfill",
                "window_start": None,
                "window_end": None,
                "mark_backfill_complete": True,
            }

        window_end = min(
            start_date + timedelta(days=config.BACKFILL_WINDOW_DAYS - 1),
            backfill_end_date,
        )
        return {
            "mode": "backfill",
            "window_start": start_date,
            "window_end": window_end,
            "mark_backfill_complete": False,
        }

    last_daily_end = state.get("last_daily_run_end")
    if last_daily_end:
        window_start = as_date(last_daily_end) + timedelta(days=1)
    else:
        window_start = yesterday_utc

    if window_start > yesterday_utc:
        return {
            "mode": "daily",
            "window_start": None,
            "window_end": None,
            "mark_backfill_complete": False,
        }

    window_end = min(
        window_start + timedelta(days=config.DAILY_CATCHUP_MAX_DAYS - 1),
        yesterday_utc,
    )
    return {
        "mode": "daily",
        "window_start": window_start,
        "window_end": window_end,
        "mark_backfill_complete": False,
    }
