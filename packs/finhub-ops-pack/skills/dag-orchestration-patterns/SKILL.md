---
name: dag-orchestration-patterns
description: "Guide to data pipeline orchestration: Airflow DAG design patterns, dependency management, retry strategies, idempotency guarantees and backfill strategies. Use this skill for pipeline scheduling: 'Airflow DAG', 'DAG design', 'dependencies', 'retry strategy', 'idempotency', 'backfill', 'pipeline orchestration', 'Dagster', 'Prefect'. It strengthens the DAG design capability of scheduler-engineer. Defining data quality rules and monitoring dashboards are outside the scope of this skill."
---

# DAG Orchestration Patterns — Pipeline Orchestration Pattern Guide

Airflow-centred DAG design patterns and operating strategies.

## DAG Design Patterns

### 1. Extract-Load-Transform (ELT) Pattern

```python
with DAG("elt_orders", schedule="0 2 * * *", catchup=False) as dag:
    extract = PythonOperator(task_id="extract", python_callable=extract_orders)
    load_raw = PythonOperator(task_id="load_raw", python_callable=load_to_raw)
    transform = DbtOperator(task_id="transform", select="orders")
    quality = PythonOperator(task_id="quality_check", python_callable=run_checks)
    notify = SlackOperator(task_id="notify", trigger_rule="all_done")

    extract >> load_raw >> transform >> quality >> notify
```

### 2. Fan-out/Fan-in Pattern

```python
# Parallel extraction from multiple sources → combined transformation
sources = ["mysql", "postgres", "api"]
extract_tasks = [
    PythonOperator(task_id=f"extract_{src}", python_callable=extract, op_args=[src])
    for src in sources
]
merge = PythonOperator(task_id="merge_all", python_callable=merge_sources)
transform = PythonOperator(task_id="transform", python_callable=transform_data)

extract_tasks >> merge >> transform
```

### 3. Sensor-Based Event Waiting

```python
wait_for_data = S3KeySensor(
    task_id="wait_for_file",
    bucket_name="data-lake",
    bucket_key="raw/orders/{{ ds }}/data.parquet",
    timeout=3600,  # wait up to 1 hour
    poke_interval=60,
    mode="reschedule"  # release the worker while waiting
)
```

## Idempotency Patterns

### Partition Replacement (Most Recommended)

```sql
-- Replace the entire date partition (idempotent)
DELETE FROM analytics.orders WHERE date_partition = '{{ ds }}';
INSERT INTO analytics.orders
SELECT * FROM staging.orders WHERE date_partition = '{{ ds }}';
```

### MERGE/UPSERT

```sql
MERGE INTO target AS t
USING source AS s ON t.id = s.id
WHEN MATCHED THEN UPDATE SET t.amount = s.amount, t.updated_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT (id, amount, created_at) VALUES (s.id, s.amount, CURRENT_TIMESTAMP);
```

### Idempotency Checklist

- [ ] Does running the same DAG twice produce the same result?
- [ ] Does it use the date parameter (`{{ ds }}`) to limit the range?
- [ ] Does it clear existing data before the INSERT?
- [ ] Does it use a unique request ID for external API calls?

## Retry Strategy

```python
default_args = {
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=60),
    "execution_timeout": timedelta(hours=2),
}
```

### Retry Settings by Task

| Task type | Retries | Wait time | Reason |
|----------|-----------|----------|------|
| DB extraction | 3 | 5 minutes, exponential backoff | Transient connection problems |
| API call | 5 | 30 seconds, exponential backoff | Rate limits, network |
| Transformation (SQL) | 1 | Immediate | Retrying a logic error is pointless |
| File upload | 3 | 1 minute | Unstable network |

## Backfill Strategy

```python
# Safe backfill settings
dag = DAG(
    "daily_orders",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,  # disable automatic backfill
    max_active_runs=1,  # prevent concurrent runs
)

# Manual backfill from the CLI
# airflow dags backfill daily_orders -s 2024-01-01 -e 2024-01-31
```

### Backfill Cautions

| Caution | Description | Response |
|------|------|------|
| Concurrent runs | The same data range is processed twice | `max_active_runs=1` |
| API rate limits | Large requests for historical data | Limit batch size, insert sleeps |
| Resource contention | DB/cluster overload | Limit parallelism, spread runs over time |
| Data consistency | Historical data had a different structure | Schema evolution handling logic |

## Dependency Patterns

### Cross-DAG Dependency

```python
# Wait for DAG A to complete
wait_for_upstream = ExternalTaskSensor(
    task_id="wait_for_dag_a",
    external_dag_id="dag_a",
    external_task_id="final_task",
    execution_delta=timedelta(hours=0),
    timeout=3600,
    mode="reschedule"
)
```

### Dataset-Based Dependency (Airflow 2.4+)

```python
# Producer DAG
orders_dataset = Dataset("s3://datalake/orders/")

with DAG("produce_orders", schedule="0 2 * * *") as dag:
    produce = PythonOperator(
        task_id="produce", outlets=[orders_dataset]
    )

# Consumer DAG — triggered automatically
with DAG("consume_orders", schedule=[orders_dataset]) as dag:
    consume = PythonOperator(task_id="consume", ...)
```

## Alerting Strategy

```python
def failure_callback(context):
    task = context["task_instance"]
    dag_id = context["dag"].dag_id
    execution_date = context["execution_date"]
    message = f"FAILED: {dag_id}/{task.task_id} at {execution_date}"
    send_slack(message)

default_args = {
    "on_failure_callback": failure_callback,
    "on_retry_callback": retry_callback,
}
```

| Event | Channel | Audience |
|--------|------|------|
| P0 task failure | Slack + PagerDuty | On-call engineer |
| SLA missed | Slack | Data team |
| Retry occurred | Slack (informational) | Monitoring channel |
| Backfill complete | Slack | Requester |
