from google.cloud import bigquery
from google.api_core.exceptions import NotFound
import config
from datetime import datetime, date
from logging_utils import log_event, classify_error

class DB:
    def __init__(self, project_id=config.PROJECT_ID):
        self.client = bigquery.Client(project=project_id)
        self.dataset_id = f"{project_id}.{config.DATASET_ID}"

    def create_dataset(self):
        try:
            self.client.get_dataset(self.dataset_id)
            log_event("db_dataset_exists", dataset=self.dataset_id)
        except NotFound:
            dataset = bigquery.Dataset(self.dataset_id)
            dataset.location = "US"  # Modify location if needed
            self.client.create_dataset(dataset, timeout=30)
            log_event("db_dataset_created", dataset=self.dataset_id)

    def create_tables(self):
        # 1. Articles
        schema_articles = [
            bigquery.SchemaField("article_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("author", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("summary", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("url", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("publish_datetime", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("language", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("full_text", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("mentions_cooling_or_water", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("cooling_water_summary", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        self._create_table_if_not_exists(config.TABLE_ARTICLES, schema_articles)

        # 2. People
        schema_people = [
            bigquery.SchemaField("person_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("full_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("primary_title", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("primary_company", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("email_if_public", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("linkedin_if_public", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("lead_relevance", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("notes", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        self._create_table_if_not_exists(config.TABLE_PEOPLE, schema_people)

        # 3. Companies
        schema_companies = [
            bigquery.SchemaField("company_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("notes", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        self._create_table_if_not_exists(config.TABLE_COMPANIES, schema_companies)

        # 4. Article People Relation
        schema_article_people = [
            bigquery.SchemaField("article_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("person_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("role_in_article", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("relation_description", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        self._create_table_if_not_exists(config.TABLE_ARTICLE_PEOPLE, schema_article_people)

        # 5. Ingestion State
        schema_ingestion = [
            bigquery.SchemaField("state_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("backfill_start_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("backfill_end_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("backfill_progress_cutoff", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("backfill_complete", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("last_daily_run_start", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("last_daily_run_end", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("lock_owner", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("lock_expires_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        self._create_table_if_not_exists(config.TABLE_INGESTION_STATE, schema_ingestion)
        self._ensure_table_columns(
            config.TABLE_INGESTION_STATE,
            [
                bigquery.SchemaField("lock_owner", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("lock_expires_at", "TIMESTAMP", mode="NULLABLE"),
            ],
        )

        # 6. Extraction Failures (dead-letter queue)
        schema_failures = [
            bigquery.SchemaField("failure_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("article_url", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("article_title", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("stage", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("error_type", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("error_kind", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("run_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("window_start", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("window_end", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        self._create_table_if_not_exists(config.TABLE_EXTRACTION_FAILURES, schema_failures)
        
        # Initialize ingestion state if empty
        self._initialize_ingestion_state()

    def _create_table_if_not_exists(self, table_name, schema):
        table_id = f"{self.dataset_id}.{table_name}"
        try:
            self.client.get_table(table_id)
            log_event("db_table_exists", table=table_id)
        except NotFound:
            table = bigquery.Table(table_id, schema=schema)
            self.client.create_table(table)
            log_event("db_table_created", table=table_id)

    def _ensure_table_columns(self, table_name, required_columns):
        table_id = f"{self.dataset_id}.{table_name}"
        try:
            table = self.client.get_table(table_id)
            existing = {field.name for field in table.schema}
            missing = [field for field in required_columns if field.name not in existing]
            if not missing:
                return
            table.schema = list(table.schema) + missing
            self.client.update_table(table, ["schema"])
            log_event(
                "db_table_columns_added",
                table=table_id,
                columns=[field.name for field in missing],
            )
        except Exception as e:
            log_event(
                "db_table_columns_ensure_error",
                level="ERROR",
                table=table_id,
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )

    def _initialize_ingestion_state(self):
        query = f"SELECT count(*) as cnt FROM `{self.dataset_id}.{config.TABLE_INGESTION_STATE}`"
        try:
            job = self.client.query(query)
            result = job.result()
            row = next(result)
            if row.cnt == 0:
                log_event("db_ingestion_state_init_start")
                # Assuming backfill ends usually 'yesterday', but we can set it dynamically or fixed for now
                rows_to_insert = [{
                    "state_id": 1,
                    "backfill_start_date": config.BACKFILL_START_DATE,
                    "backfill_end_date": datetime.now().strftime("%Y-%m-%d"),
                    "backfill_progress_cutoff": config.BACKFILL_START_DATE,
                    "backfill_complete": False,
                    "last_daily_run_start": None,
                    "last_daily_run_end": None,
                    "lock_owner": None,
                    "lock_expires_at": None,
                    "updated_at": datetime.now().isoformat()
                }]

                self.client.insert_rows_json(f"{self.dataset_id}.{config.TABLE_INGESTION_STATE}", rows_to_insert)
                log_event("db_ingestion_state_init_done")
        except Exception as e:
            log_event(
                "db_ingestion_state_init_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )

    def get_ingestion_state(self):
        query = f"""
            SELECT
                state_id,
                backfill_start_date,
                backfill_end_date,
                backfill_progress_cutoff,
                backfill_complete,
                last_daily_run_start,
                last_daily_run_end,
                lock_owner,
                lock_expires_at,
                updated_at
            FROM `{self.dataset_id}.{config.TABLE_INGESTION_STATE}`
            WHERE state_id = 1
            LIMIT 1
        """
        try:
            job = self.client.query(query)
            rows = list(job.result())
            if not rows:
                return None
            row = rows[0]
            return {
                "state_id": row.state_id,
                "backfill_start_date": row.backfill_start_date,
                "backfill_end_date": row.backfill_end_date,
                "backfill_progress_cutoff": row.backfill_progress_cutoff,
                "backfill_complete": row.backfill_complete,
                "last_daily_run_start": row.last_daily_run_start,
                "last_daily_run_end": row.last_daily_run_end,
                "lock_owner": row.lock_owner,
                "lock_expires_at": row.lock_expires_at,
                "updated_at": row.updated_at,
            }
        except Exception as e:
            log_event(
                "db_ingestion_state_read_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return None

    def update_ingestion_state(
        self,
        backfill_progress_cutoff=None,
        backfill_complete=None,
        last_daily_run_start=None,
        last_daily_run_end=None,
    ):
        assignments = ["updated_at = @updated_at"]
        params = [bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", datetime.utcnow())]

        if backfill_progress_cutoff is not None:
            cutoff_value = (
                date.fromisoformat(backfill_progress_cutoff)
                if isinstance(backfill_progress_cutoff, str)
                else backfill_progress_cutoff
            )
            assignments.append("backfill_progress_cutoff = @backfill_progress_cutoff")
            params.append(
                bigquery.ScalarQueryParameter("backfill_progress_cutoff", "DATE", cutoff_value)
            )

        if backfill_complete is not None:
            assignments.append("backfill_complete = @backfill_complete")
            params.append(bigquery.ScalarQueryParameter("backfill_complete", "BOOL", backfill_complete))

        if last_daily_run_start is not None:
            assignments.append("last_daily_run_start = @last_daily_run_start")
            params.append(
                bigquery.ScalarQueryParameter("last_daily_run_start", "TIMESTAMP", last_daily_run_start)
            )

        if last_daily_run_end is not None:
            assignments.append("last_daily_run_end = @last_daily_run_end")
            params.append(
                bigquery.ScalarQueryParameter("last_daily_run_end", "TIMESTAMP", last_daily_run_end)
            )

        query = f"""
            UPDATE `{self.dataset_id}.{config.TABLE_INGESTION_STATE}`
            SET {", ".join(assignments)}
            WHERE state_id = 1
        """
        try:
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            job = self.client.query(query, job_config=job_config)
            job.result()
            return True
        except Exception as e:
            log_event(
                "db_ingestion_state_update_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return False

    def try_acquire_pipeline_lock(self, owner, lease_seconds=3600):
        query = f"""
            UPDATE `{self.dataset_id}.{config.TABLE_INGESTION_STATE}`
            SET
                lock_owner = @owner,
                lock_expires_at = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL @lease_seconds SECOND),
                updated_at = CURRENT_TIMESTAMP()
            WHERE state_id = 1
              AND (
                lock_expires_at IS NULL
                OR lock_expires_at < CURRENT_TIMESTAMP()
                OR lock_owner = @owner
              )
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("owner", "STRING", owner),
                bigquery.ScalarQueryParameter("lease_seconds", "INT64", lease_seconds),
            ]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            job.result()
            affected = int(getattr(job, "num_dml_affected_rows", 0) or 0)
            return affected > 0
        except Exception as e:
            log_event(
                "db_pipeline_lock_acquire_error",
                level="ERROR",
                owner=owner,
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return False

    def release_pipeline_lock(self, owner):
        query = f"""
            UPDATE `{self.dataset_id}.{config.TABLE_INGESTION_STATE}`
            SET
                lock_owner = NULL,
                lock_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP()
            WHERE state_id = 1 AND lock_owner = @owner
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("owner", "STRING", owner)]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            job.result()
            affected = int(getattr(job, "num_dml_affected_rows", 0) or 0)
            return affected > 0
        except Exception as e:
            log_event(
                "db_pipeline_lock_release_error",
                level="ERROR",
                owner=owner,
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return False

    def insert_rows(self, table_name, rows):
        table_id = f"{self.dataset_id}.{table_name}"
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            log_event("db_insert_rows_error", level="ERROR", table=table_id, errors=errors)
            return False
        else:
            log_event("db_insert_rows_ok", table=table_id, row_count=len(rows))
            return True

    def insert_rows_detailed(self, table_name, rows):
        table_id = f"{self.dataset_id}.{table_name}"
        if not rows:
            return []

        errors = self.client.insert_rows_json(table_id, rows)
        success = [True] * len(rows)

        if errors:
            log_event("db_insert_rows_detailed_error", level="ERROR", table=table_id, errors=errors)
            for err in errors:
                idx = err.get("index")
                if isinstance(idx, int) and 0 <= idx < len(success):
                    success[idx] = False
        else:
            log_event("db_insert_rows_detailed_ok", table=table_id, row_count=len(rows))

        return success

    def get_article_by_url(self, url):
        query = f"SELECT article_id, title, source_name, publish_datetime FROM `{self.dataset_id}.{config.TABLE_ARTICLES}` WHERE url = @url"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("url", "STRING", url)
            ]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            result = list(job.result())
            return result[0] if result else None
        except Exception as e:
            log_event(
                "db_get_article_by_url_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return None

    def get_person(self, full_name, company):
        query = f"""
            SELECT person_id FROM `{self.dataset_id}.{config.TABLE_PEOPLE}`
            WHERE LOWER(full_name) = LOWER(@full_name)
            AND (LOWER(primary_company) = LOWER(@company) OR (@company IS NULL AND primary_company IS NULL))
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("full_name", "STRING", full_name),
                bigquery.ScalarQueryParameter("company", "STRING", company)
            ]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            result = list(job.result())
            return result[0].person_id if result else None
        except Exception as e:
            log_event(
                "db_get_person_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return None

    def get_company(self, name):
        query = f"SELECT company_id FROM `{self.dataset_id}.{config.TABLE_COMPANIES}` WHERE LOWER(name) = LOWER(@name)"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("name", "STRING", name)
            ]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            result = list(job.result())
            return result[0].company_id if result else None
        except Exception as e:
            log_event(
                "db_get_company_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return None

    def article_person_relation_exists(self, article_id, person_id):
        query = f"""
            SELECT 1
            FROM `{self.dataset_id}.{config.TABLE_ARTICLE_PEOPLE}`
            WHERE article_id = @article_id
              AND person_id = @person_id
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("article_id", "INT64", article_id),
                bigquery.ScalarQueryParameter("person_id", "INT64", person_id),
            ]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            result = list(job.result())
            return len(result) > 0
        except Exception as e:
            log_event(
                "db_article_person_relation_exists_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return False

    def upsert_article_person_relation(self, article_id, person_id, role_in_article, relation_description, created_at):
        query = f"""
            MERGE `{self.dataset_id}.{config.TABLE_ARTICLE_PEOPLE}` T
            USING (
                SELECT
                    @article_id AS article_id,
                    @person_id AS person_id,
                    @role_in_article AS role_in_article,
                    @relation_description AS relation_description,
                    @created_at AS created_at
            ) S
            ON T.article_id = S.article_id AND T.person_id = S.person_id
            WHEN NOT MATCHED THEN
              INSERT (article_id, person_id, role_in_article, relation_description, created_at)
              VALUES (S.article_id, S.person_id, S.role_in_article, S.relation_description, S.created_at)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("article_id", "INT64", article_id),
                bigquery.ScalarQueryParameter("person_id", "INT64", person_id),
                bigquery.ScalarQueryParameter("role_in_article", "STRING", role_in_article),
                bigquery.ScalarQueryParameter("relation_description", "STRING", relation_description),
                bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", created_at),
            ]
        )
        try:
            job = self.client.query(query, job_config=job_config)
            job.result()
            return True
        except Exception as e:
            log_event(
                "db_article_person_relation_upsert_error",
                level="ERROR",
                error_type=type(e).__name__,
                error_kind=classify_error(e),
                error=str(e),
            )
            return False

if __name__ == "__main__":
    # Test Setup
    db = DB()
    db.create_dataset()
    db.create_tables()
