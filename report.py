import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

import config


def run_query(client, query, params):
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    job = client.query(query, job_config=job_config)
    return list(job.result())


def rows_to_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Generate a daily report from dc_news BigQuery tables.")
    parser.add_argument("--days", type=int, default=1, help="Lookback window in days (default: 1)")
    parser.add_argument("--output-dir", default="reports", help="Directory to write report files (default: reports)")
    parser.add_argument("--project-id", default=config.PROJECT_ID, help="BigQuery project id")
    parser.add_argument("--dataset-id", default=config.DATASET_ID, help="BigQuery dataset id")
    args = parser.parse_args()

    if args.days <= 0:
        raise ValueError("--days must be > 0")

    client = bigquery.Client(project=args.project_id)
    dataset = f"{args.project_id}.{args.dataset_id}"

    article_params = [bigquery.ScalarQueryParameter("days", "INT64", args.days)]
    articles_query = f"""
        SELECT
          article_id,
          title,
          source_name,
          publish_datetime,
          url,
          mentions_cooling_or_water,
          cooling_water_summary
        FROM `{dataset}.{config.TABLE_ARTICLES}`
        WHERE publish_datetime >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        ORDER BY publish_datetime DESC
    """
    article_rows_raw = run_query(client, articles_query, article_params)
    articles = []
    article_ids = set()
    relevant_count = 0
    for row in article_rows_raw:
        row_dict = {
            "article_id": row.article_id,
            "title": row.title,
            "source_name": row.source_name,
            "publish_datetime": row.publish_datetime.isoformat() if row.publish_datetime else "",
            "url": row.url,
            "mentions_cooling_or_water": bool(row.mentions_cooling_or_water),
            "cooling_water_summary": row.cooling_water_summary or "",
        }
        articles.append(row_dict)
        article_ids.add(row.article_id)
        if row_dict["mentions_cooling_or_water"]:
            relevant_count += 1

    people = []
    if article_ids:
        people_query = f"""
            SELECT
              ap.article_id,
              p.full_name,
              p.primary_title,
              p.primary_company,
              p.lead_relevance,
              ap.role_in_article
            FROM `{dataset}.{config.TABLE_ARTICLE_PEOPLE}` ap
            JOIN `{dataset}.{config.TABLE_PEOPLE}` p
              ON p.person_id = ap.person_id
            WHERE ap.article_id IN UNNEST(@article_ids)
            ORDER BY p.lead_relevance DESC, p.full_name
        """
        people_rows_raw = run_query(
            client,
            people_query,
            [bigquery.ArrayQueryParameter("article_ids", "INT64", list(article_ids))],
        )
        for row in people_rows_raw:
            people.append(
                {
                    "article_id": row.article_id,
                    "full_name": row.full_name or "",
                    "primary_title": row.primary_title or "",
                    "primary_company": row.primary_company or "",
                    "lead_relevance": row.lead_relevance or "",
                    "role_in_article": row.role_in_article or "",
                }
            )

    failures_query = f"""
        SELECT
          stage,
          COUNT(*) AS failure_count
        FROM `{dataset}.{config.TABLE_EXTRACTION_FAILURES}`
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY stage
        ORDER BY failure_count DESC
    """
    failure_rows_raw = run_query(client, failures_query, article_params)
    failures = [{"stage": row.stage, "failure_count": row.failure_count} for row in failure_rows_raw]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    md_path = out_dir / f"daily_report_{stamp}.md"
    articles_csv_path = out_dir / f"articles_{stamp}.csv"
    people_csv_path = out_dir / f"people_{stamp}.csv"
    failures_csv_path = out_dir / f"failures_{stamp}.csv"

    rows_to_csv(
        articles_csv_path,
        [
            "article_id",
            "title",
            "source_name",
            "publish_datetime",
            "url",
            "mentions_cooling_or_water",
            "cooling_water_summary",
        ],
        articles,
    )
    rows_to_csv(
        people_csv_path,
        [
            "article_id",
            "full_name",
            "primary_title",
            "primary_company",
            "lead_relevance",
            "role_in_article",
        ],
        people,
    )
    rows_to_csv(failures_csv_path, ["stage", "failure_count"], failures)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# Data Center Water News Report\n\n")
        f.write(f"- Generated UTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"- Project: `{args.project_id}`\n")
        f.write(f"- Dataset: `{args.dataset_id}`\n")
        f.write(f"- Lookback days: `{args.days}`\n")
        f.write(f"- Total articles: `{len(articles)}`\n")
        f.write(f"- Relevant articles (`mentions_cooling_or_water=true`): `{relevant_count}`\n")
        f.write(f"- People links: `{len(people)}`\n")
        f.write("\n## Top Relevant Articles\n\n")
        top_relevant = [a for a in articles if a["mentions_cooling_or_water"]][:10]
        if not top_relevant:
            f.write("No relevant articles in the selected window.\n")
        else:
            for idx, article in enumerate(top_relevant, start=1):
                f.write(f"{idx}. **{article['title']}** ({article['source_name']})\n")
                f.write(f"   - Published: {article['publish_datetime']}\n")
                f.write(f"   - URL: {article['url']}\n")
                if article["cooling_water_summary"]:
                    f.write(f"   - Note: {article['cooling_water_summary']}\n")
                f.write("\n")

        f.write("## Failure Summary\n\n")
        if not failures:
            f.write("No failures recorded in the selected window.\n")
        else:
            for item in failures:
                f.write(f"- {item['stage']}: {item['failure_count']}\n")

        f.write("\n## Output Files\n\n")
        f.write(f"- Markdown: `{md_path}`\n")
        f.write(f"- Articles CSV: `{articles_csv_path}`\n")
        f.write(f"- People CSV: `{people_csv_path}`\n")
        f.write(f"- Failures CSV: `{failures_csv_path}`\n")

    print(f"Report written: {md_path}")
    print(f"Articles CSV: {articles_csv_path}")
    print(f"People CSV: {people_csv_path}")
    print(f"Failures CSV: {failures_csv_path}")


if __name__ == "__main__":
    main()
