# Databricks Notebooks - MTG Pricing Pipeline

## Overview

These notebooks replace the Azure Functions pricing pipeline with a Databricks-based solution.

**Daily Pipeline Flow**:
```
1. Scryfall API → MongoDB (01_ingest_scryfall_pricing.py)
   ↓
2. MongoDB → Delta Lake (02_dbt_transformation.py)
   ↓
3. Web App queries Delta Lake (REST API)
```

---

## Notebooks

### 01_ingest_scryfall_pricing.py

**Purpose**: Fetch pricing data from Scryfall API and write to MongoDB

**Schedule**: Daily at 1:00 AM UTC

**Runtime**: 3-5 minutes (78k cards)

**Features**:
- Batched API calls (75 cards per request)
- Rate limiting (100ms delay)
- Unpivoted format (6 rows per card)
- Bulk insert to MongoDB
- Auto-cleanup (keep 7 days only)

**Outputs**: MongoDB `card_pricing_daily` collection

---

### 02_dbt_transformation.py

**Purpose**: Transform MongoDB data to Delta Lake (partitioned, pivoted)

**Schedule**: Daily at 1:30 AM UTC (after ingestion)

**Runtime**: 2-3 minutes

**Features**:
- Runs dbt models (staging → intermediate → marts)
- Incremental processing (only new dates)
- Data quality tests
- Delta Lake optimization (ZORDER by card_name)
- Automatic VACUUM (7-day retention)

**Outputs**: 
- `mtgecorec_prod.pricing.pricing_daily` (partitioned by ds)
- `mtgecorec_prod.pricing.pricing_latest` (view of latest date)

---

## Setup Instructions

### 1. Upload Notebooks to Databricks

**Option A: Databricks UI**
1. Open Databricks workspace
2. Click **Workspace** → **Users** → Your user
3. Click **Create** → **Import**
4. Upload both `.py` files

**Option B: Databricks CLI**
```bash
# Upload notebooks
databricks workspace import \
  databricks_notebooks/01_ingest_scryfall_pricing.py \
  /Workspace/mtgecorec/notebooks/01_ingest_scryfall_pricing.py \
  --language PYTHON

databricks workspace import \
  databricks_notebooks/02_dbt_transformation.py \
  /Workspace/mtgecorec/notebooks/02_dbt_transformation.py \
  --language PYTHON
```

---

### 2. Upload dbt Project to Databricks

```bash
# Upload entire dbt_pricing folder
databricks workspace import-dir \
  dbt_pricing/ \
  /Workspace/mtgecorec/dbt_pricing
```

---

### 3. Create Secret Scope (Store Credentials)

```bash
# Create secret scope
databricks secrets create-scope --scope mtgecorec

# Add MongoDB connection string
databricks secrets put --scope mtgecorec --key cosmos-connection-string
# Paste your COSMOS_CONNECTION_STRING value

# Add Databricks credentials (for dbt)
databricks secrets put --scope mtgecorec --key databricks-host
# Example: adb-1234567890123456.7.azuredatabricks.net

databricks secrets put --scope mtgecorec --key databricks-http-path
# Example: /sql/1.0/warehouses/abc123def456

databricks secrets put --scope mtgecorec --key databricks-token
# Your Databricks personal access token
```

---

### 4. Create Databricks Job (Scheduled Workflow)

**Job Configuration** (YAML):

```yaml
name: mtg_pricing_daily_pipeline

schedule:
  quartz_cron_expression: "0 0 1 * * ?"  # 1:00 AM UTC daily
  timezone_id: "UTC"

tasks:
  - task_key: ingest_scryfall
    notebook_task:
      notebook_path: /Workspace/mtgecorec/notebooks/01_ingest_scryfall_pricing
      source: WORKSPACE
    existing_cluster_id: your-cluster-id  # Or use job_cluster_key
    timeout_seconds: 1800  # 30 minutes max
    
  - task_key: dbt_transform
    depends_on:
      - task_key: ingest_scryfall
    notebook_task:
      notebook_path: /Workspace/mtgecorec/notebooks/02_dbt_transformation
      source: WORKSPACE
    existing_cluster_id: your-cluster-id
    timeout_seconds: 900  # 15 minutes max

max_concurrent_runs: 1
```

**Create via UI**:
1. Click **Workflows** → **Create Job**
2. Add **Task 1**: `01_ingest_scryfall_pricing`
   - Cluster: Use existing or create job cluster
   - Schedule: Daily at 1:00 AM UTC
3. Add **Task 2**: `02_dbt_transformation`
   - Depends on: Task 1
   - Cluster: Same as Task 1
4. Save and enable

---

## Manual Testing

### Test Ingestion Notebook

```bash
# Run manually from Databricks UI
# Or via CLI:
databricks jobs run-now --job-id YOUR_JOB_ID --notebook-params '{}'
```

### Test dbt Transformation

```bash
# From your dev container:
cd dbt_pricing
dbt run --target dev
dbt test
```

---

## Monitoring

### Check Job Status

```bash
# List recent runs
databricks jobs runs list --job-id YOUR_JOB_ID --limit 10

# Get run details
databricks jobs runs get --run-id RUN_ID
```

### Check Data in Delta Lake

```sql
-- In Databricks SQL Editor
USE CATALOG mtgecorec_prod;
USE SCHEMA pricing;

-- Check latest partition
SELECT ds, COUNT(*) as row_count
FROM pricing_daily
GROUP BY ds
ORDER BY ds DESC
LIMIT 7;

-- Check latest prices
SELECT * FROM pricing_latest
WHERE card_name = 'Sol Ring';
```

---

## Troubleshooting

### Ingestion Notebook Fails

**Error**: `Connection to MongoDB failed`

**Solution**:
```bash
# Verify secret is set
databricks secrets list --scope mtgecorec

# Test connection
mongo "YOUR_CONNECTION_STRING" --eval "db.cards.count()"
```

### dbt Transformation Fails

**Error**: `Catalog mtgecorec_prod does not exist`

**Solution**:
```sql
-- Create catalogs in Databricks SQL
CREATE CATALOG mtgecorec_prod;
CREATE SCHEMA mtgecorec_prod.pricing;
```

**Error**: `Table or view not found: card_pricing_daily`

**Solution**:
```python
# Verify MongoDB source is accessible
# In notebook cell:
df = spark.read.format("mongo") \
  .option("uri", mongo_uri) \
  .option("database", "mtgecorec") \
  .option("collection", "card_pricing_daily") \
  .load()

df.show(5)
```

---

## Cost Optimization

### Compute Costs

- **Job Cluster** (auto-terminate): ~$0.15/DBU-hour
- **Runtime**: 5-8 minutes/day
- **Monthly cost**: ~$5-10

### Storage Costs

- **Delta Lake (ADLS Gen2)**: ~$0.02/GB/month
- **Data size**: ~1.5GB compressed (30 days)
- **Monthly cost**: ~$0.03

### Total Estimated Cost

**Pipeline**: $5-10/month (compute) + $0.03/month (storage) = **$5-10/month**

**Compared to Azure Functions**: $80-140/month → **90% savings** 🎉

---

## Next Steps

After notebooks are running:

1. ✅ **Monitor first few runs** (check logs for errors)
2. ✅ **Validate data quality** (row counts, price ranges)
3. ✅ **Update web app** to query Delta Lake
4. ✅ **Disable Azure Functions** pricing pipeline
5. ✅ **Archive MongoDB pricing** (keep 7 days)
6. ✅ **Setup alerting** for job failures

---

## Support

- **Databricks docs**: https://docs.databricks.com
- **dbt docs**: https://docs.getdbt.com
- **Scryfall API**: https://scryfall.com/docs/api
