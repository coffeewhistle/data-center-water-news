import config
from db import DB
from news_fetcher import NewsFetcher
from extractor import Extractor
from datetime import datetime, timedelta, timezone
import hashlib
import asyncio
import httpx
from logging_utils import log_event, classify_error, utc_now_iso
from pipeline_utils import normalize_url, as_date, build_run_plan
from batching_utils import company_key, person_key, dedupe_companies, dedupe_people


def stable_int_id(*parts):
    joined = "|".join([(p or "").strip().lower() for p in parts])
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:15]
    return int(digest, 16)


async def run_pipeline_window(db, fetcher, extractor, mode, window_start, window_end, run_id):
    log_event(
        "pipeline_window_start",
        run_id=run_id,
        mode=mode,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
    )

    timeout = httpx.Timeout(config.HTTP_TIMEOUT_SECONDS)
    limits = httpx.Limits(max_connections=30, max_keepalive_connections=10)
    # Google News "before:" is exclusive, so use next day to include window_end.
    google_start = window_start.isoformat()
    google_end_exclusive = (window_end + timedelta(days=1)).isoformat()

    async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
        articles_metadata = await fetcher.fetch_articles(
            limit=config.PIPELINE_FETCH_LIMIT,
            client=client,
            start_date=google_start,
            end_date=google_end_exclusive,
        )
    log_event(
        "pipeline_fetch_done",
        run_id=run_id,
        mode=mode,
        fetched=len(articles_metadata),
    )

    stats = {
        "mode": mode,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "people_added": 0,
        "companies_added": 0,
        "skipped": 0
    }
    
    result_report = []
    failure_rows = []

    articles_to_extract = []
    for art_meta in articles_metadata:
        stats["processed"] += 1
        raw_url = art_meta.get("url")
        url = normalize_url(raw_url)
        if not url:
            stats["skipped"] += 1
            log_event("pipeline_skip_missing_url", run_id=run_id, level="WARNING")
            continue
        
        # Deduplication Check
        existing_article = db.get_article_by_url(url)
        if existing_article:
            log_event("pipeline_article_exists", run_id=run_id, url=url)
            stats["updated"] += 1
            continue

        art_meta["url"] = url
        articles_to_extract.append(art_meta)

    async def _extract_one(article, client, semaphore):
        async with semaphore:
            try:
                log_event(
                    "pipeline_extract_start",
                    run_id=run_id,
                    title=article.get("title", "Untitled"),
                    url=article.get("url"),
                )
                extracted = await extractor.extract_article_data(article, client=client)
                return {"ok": True, "article": article, "extracted": extracted}
            except Exception as exc:
                return {"ok": False, "article": article, "error": exc}

    extraction_results = []
    if articles_to_extract:
        semaphore = asyncio.Semaphore(config.EXTRACTION_CONCURRENCY)
        async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
            tasks = [_extract_one(article, client, semaphore) for article in articles_to_extract]
            extraction_results = await asyncio.gather(*tasks, return_exceptions=False)

    # 3. Persist
    candidate_records = []
    for item in extraction_results:
        if not item.get("ok"):
            stats["skipped"] += 1
            art = item.get("article") or {}
            exc = item.get("error")
            failure_rows.append(
                {
                    "failure_id": stable_int_id("failure", run_id, art.get("url"), "extract"),
                    "article_url": art.get("url"),
                    "article_title": art.get("title"),
                    "stage": "extract",
                    "error_type": type(exc).__name__ if exc else None,
                    "error_kind": classify_error(exc) if exc else "unknown",
                    "error_message": str(exc) if exc else "unknown",
                    "run_id": run_id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            continue
        art_meta = item["article"]
        extracted_data = item["extracted"]
        url = art_meta.get("url")
        if not url:
            stats["skipped"] += 1
            continue

        # Deterministic IDs avoid race conditions from MAX(id)+1.
        new_article_id = stable_int_id("article", url)
        
        # Prepare Article Row
        article_row = {
            "article_id": new_article_id,
            "title": art_meta.get("title", "Untitled"),
            "author": None, # RSS doesn't usually give this
            "summary": extracted_data.get('summary') or art_meta.get("summary") or art_meta.get("title", "Untitled"),
            "url": url,
            "source_name": art_meta.get("source_name", "Unknown"),
            "publish_datetime": art_meta['publish_datetime'].isoformat() if art_meta.get('publish_datetime') else None,
            "language": "en",
            "country": extracted_data.get("country"),
            "full_text": extracted_data.get("full_text"),
            "mentions_cooling_or_water": bool(extracted_data.get('mentions_cooling_or_water')),
            "cooling_water_summary": extracted_data.get('cooling_water_summary'),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        candidate_records.append(
            {
                "article_id": new_article_id,
                "article_row": article_row,
                "art_meta": art_meta,
                "extracted_data": extracted_data,
            }
        )

    article_rows = [record["article_row"] for record in candidate_records]
    insert_success = db.insert_rows_detailed(config.TABLE_ARTICLES, article_rows)

    successful_records = []
    for idx, record in enumerate(candidate_records):
        if not insert_success[idx]:
            stats["skipped"] += 1
            art_meta = record["art_meta"]
            failure_rows.append(
                {
                    "failure_id": stable_int_id("failure", run_id, art_meta.get("url"), "article_insert"),
                    "article_url": art_meta.get("url"),
                    "article_title": art_meta.get("title"),
                    "stage": "article_insert",
                    "error_type": "InsertError",
                    "error_kind": "permanent_write",
                    "error_message": "Failed to insert article row into BigQuery.",
                    "run_id": run_id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            continue

        art_meta = record["art_meta"]
        stats["inserted"] += 1
        result_report.append(f"Inserted Article: {art_meta.get('title', 'Untitled')}")
        successful_records.append(record)

    # Collect all people/companies from successfully inserted articles.
    all_companies = []
    all_people = []
    article_person_links = []
    for record in successful_records:
        art_meta = record["art_meta"]
        extracted_data = record["extracted_data"]
        article_id = record["article_id"]
        for comp in extracted_data.get("companies", []):
            if not isinstance(comp, dict):
                continue
            comp_copy = dict(comp)
            comp_copy["_source_article_url"] = art_meta.get("url")
            comp_copy["_source_article_title"] = art_meta.get("title")
            all_companies.append(comp_copy)

        for person in extracted_data.get("people", []):
            if not isinstance(person, dict):
                continue
            person_copy = dict(person)
            person_copy["_source_article_url"] = art_meta.get("url")
            person_copy["_source_article_title"] = art_meta.get("title")
            all_people.append(person_copy)

            p_key = person_key(person.get("full_name"), person.get("primary_company"))
            if not p_key:
                continue
            article_person_links.append(
                {
                    "article_id": article_id,
                    "person_key": p_key,
                    "role_in_article": person.get("role_in_article", "Mentioned"),
                    "relation_description": person.get("notes"),
                    "article_url": art_meta.get("url"),
                    "article_title": art_meta.get("title"),
                }
            )

    deduped_companies = dedupe_companies(all_companies)
    deduped_people = dedupe_people(all_people)

    company_ids = {}
    companies_to_insert = []
    company_insert_keys = []
    for c_key, comp in deduped_companies.items():
        company_name = comp.get("name")
        existing_c_id = db.get_company(company_name)
        if existing_c_id:
            company_ids[c_key] = existing_c_id
            continue
        c_id = stable_int_id("company", company_name)
        company_ids[c_key] = c_id
        companies_to_insert.append(
            {
                "company_id": c_id,
                "name": company_name,
                "sector": comp.get("sector"),
                "country": comp.get("country"),
                "notes": comp.get("notes"),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        )
        company_insert_keys.append(c_key)

    if companies_to_insert:
        company_insert_success = db.insert_rows_detailed(config.TABLE_COMPANIES, companies_to_insert)
        for idx, ok in enumerate(company_insert_success):
            if ok:
                stats["companies_added"] += 1
                continue
            failed_key = company_insert_keys[idx]
            failed = deduped_companies[failed_key]
            failure_rows.append(
                {
                    "failure_id": stable_int_id("failure", run_id, failed.get("name"), "company_insert"),
                    "article_url": failed.get("_source_article_url"),
                    "article_title": failed.get("_source_article_title"),
                    "stage": "company_insert",
                    "error_type": "InsertError",
                    "error_kind": "permanent_write",
                    "error_message": "Failed to insert company row into BigQuery.",
                    "run_id": run_id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            company_ids.pop(failed_key, None)

    person_ids = {}
    people_to_insert = []
    person_insert_keys = []
    for p_key, person in deduped_people.items():
        person_name = person.get("full_name")
        person_company = person.get("primary_company")
        existing_p_id = db.get_person(person_name, person_company)
        if existing_p_id:
            person_ids[p_key] = existing_p_id
            continue
        p_id = stable_int_id("person", person_name, person_company)
        person_ids[p_key] = p_id
        people_to_insert.append(
            {
                "person_id": p_id,
                "full_name": person_name,
                "primary_title": person.get("primary_title"),
                "primary_company": person_company,
                "email_if_public": None,
                "linkedin_if_public": None,
                "lead_relevance": person.get("lead_relevance", "Low"),
                "notes": person.get("notes"),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        )
        person_insert_keys.append(p_key)

    if people_to_insert:
        person_insert_success = db.insert_rows_detailed(config.TABLE_PEOPLE, people_to_insert)
        for idx, ok in enumerate(person_insert_success):
            if ok:
                stats["people_added"] += 1
                continue
            failed_key = person_insert_keys[idx]
            failed = deduped_people[failed_key]
            failure_rows.append(
                {
                    "failure_id": stable_int_id("failure", run_id, failed.get("full_name"), "person_insert"),
                    "article_url": failed.get("_source_article_url"),
                    "article_title": failed.get("_source_article_title"),
                    "stage": "person_insert",
                    "error_type": "InsertError",
                    "error_kind": "permanent_write",
                    "error_message": "Failed to insert person row into BigQuery.",
                    "run_id": run_id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            person_ids.pop(failed_key, None)

    # Link Article-Person after person IDs are resolved.
    seen_relations = set()
    for link in article_person_links:
        relation_key = (link["article_id"], link["person_key"])
        if relation_key in seen_relations:
            continue
        seen_relations.add(relation_key)

        p_id = person_ids.get(link["person_key"])
        if not p_id:
            failure_rows.append(
                {
                    "failure_id": stable_int_id("failure", run_id, link.get("article_url"), link.get("person_key"), "relation_link"),
                    "article_url": link.get("article_url"),
                    "article_title": link.get("article_title"),
                    "stage": "relation_link",
                    "error_type": "MissingPersonId",
                    "error_kind": "dependent_write",
                    "error_message": "Skipped article-person relation because person ID was unavailable.",
                    "run_id": run_id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            continue

        db.upsert_article_person_relation(
            article_id=link["article_id"],
            person_id=p_id,
            role_in_article=link["role_in_article"],
            relation_description=link["relation_description"],
            created_at=datetime.now().isoformat(),
        )

    if failure_rows:
        db.insert_rows(config.TABLE_EXTRACTION_FAILURES, failure_rows)
        log_event("pipeline_failures_recorded", run_id=run_id, count=len(failure_rows))

    # 4. Report
    log_event("pipeline_run_report", run_id=run_id, stats=stats)
    for item in result_report:
        log_event("pipeline_inserted_article", run_id=run_id, detail=item)
    log_event("pipeline_window_done", run_id=run_id, mode=mode)
    return stats


async def run_pipeline():
    run_id = f"run_{utc_now_iso()}"
    log_event("pipeline_start", run_id=run_id)
    config.validate_config()
    lock_acquired = False

    try:
        db = DB()
        db.create_dataset()
        db.create_tables()
        lock_acquired = db.try_acquire_pipeline_lock(
            owner=run_id,
            lease_seconds=config.PIPELINE_LOCK_LEASE_SECONDS,
        )
        if not lock_acquired:
            log_event("pipeline_lock_busy", run_id=run_id, level="WARNING")
            return

        fetcher = NewsFetcher()
        extractor = Extractor()

        state = db.get_ingestion_state()
        if not state:
            log_event("pipeline_state_missing", run_id=run_id, level="ERROR")
            raise RuntimeError("Unable to load ingestion state.")

        plan = build_run_plan(state)
        mode = plan["mode"]
        window_start = plan["window_start"]
        window_end = plan["window_end"]

        run_started_at = datetime.now(timezone.utc)

        if mode == "backfill" and plan["mark_backfill_complete"]:
            log_event("pipeline_backfill_mark_complete", run_id=run_id)
            db.update_ingestion_state(backfill_complete=True)
            return

        if window_start is None or window_end is None:
            log_event("pipeline_no_window", run_id=run_id, mode=mode)
            return

        try:
            await run_pipeline_window(db, fetcher, extractor, mode, window_start, window_end, run_id=run_id)
        except Exception as exc:
            log_event(
                "pipeline_window_failed",
                run_id=run_id,
                level="ERROR",
                mode=mode,
                error_type=type(exc).__name__,
                error_kind=classify_error(exc),
                error=str(exc),
            )
            raise

        if mode == "backfill":
            backfill_end_date = as_date(state.get("backfill_end_date"))
            next_cutoff = window_end + timedelta(days=1)
            is_complete = next_cutoff > backfill_end_date
            db.update_ingestion_state(
                backfill_progress_cutoff=next_cutoff.isoformat(),
                backfill_complete=is_complete,
            )
            log_event(
                "pipeline_backfill_state_advanced",
                run_id=run_id,
                next_cutoff=next_cutoff.isoformat(),
                backfill_complete=is_complete,
            )
        else:
            processed_end = datetime.combine(
                window_end,
                datetime.max.time().replace(microsecond=0),
                tzinfo=timezone.utc,
            )
            db.update_ingestion_state(
                last_daily_run_start=run_started_at,
                last_daily_run_end=processed_end,
            )
            log_event(
                "pipeline_daily_state_advanced",
                run_id=run_id,
                last_daily_run_start=run_started_at.isoformat(),
                last_daily_run_end=processed_end.isoformat(),
            )
    finally:
        if lock_acquired:
            released = db.release_pipeline_lock(owner=run_id)
            if not released:
                log_event("pipeline_lock_release_missed", run_id=run_id, level="WARNING")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
