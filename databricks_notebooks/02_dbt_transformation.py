# Databricks notebook source
# MAGIC %md
# MAGIC # dbt Transformation: MongoDB → Delta Lake
# MAGIC 
# MAGIC **Purpose**: Run dbt models to transform pricing data from MongoDB to Delta Lake
# MAGIC 
# MAGIC **Flow**:
# MAGIC 1. Load raw pricing from MongoDB (staging)
# MAGIC 2. Pivot 6 rows → 1 row per card (intermediate)
# MAGIC 3. Write to Delta Lake partitioned by date (marts)
# MAGIC 
# MAGIC **Schedule**: Daily at 1:30 AM UTC (after ingestion job)
# MAGIC 
# MAGIC **Runtime**: ~2-3 minutes

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup dbt Environment

# COMMAND ----------

import subprocess
import os

# Set dbt project directory
DBT_PROJECT_DIR = "/Workspace/mtgecorec/dbt_pricing"

# Set environment variables for dbt (from Databricks secrets)
os.environ["DATABRICKS_HOST"] = dbutils.secrets.get(scope="mtgecorec", key="databricks-host")
os.environ["DATABRICKS_HTTP_PATH"] = dbutils.secrets.get(scope="mtgecorec", key="databricks-http-path")
os.environ["DATABRICKS_TOKEN"] = dbutils.secrets.get(scope="mtgecorec", key="databricks-token")

print(f"✅ dbt project directory: {DBT_PROJECT_DIR}")
print(f"✅ Environment configured")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install dbt Dependencies

# COMMAND ----------

# Install dbt packages (dbt_utils, etc.)
print("📦 Installing dbt packages...")

result = subprocess.run(
    ["dbt", "deps", "--project-dir", DBT_PROJECT_DIR],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("✅ dbt packages installed")
    print(result.stdout)
else:
    print("❌ Failed to install dbt packages")
    print(result.stderr)
    dbutils.notebook.exit("FAILED: dbt deps")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run dbt Models (Incremental)

# COMMAND ----------

# Run dbt in incremental mode (only process new data)
print("🚀 Running dbt models...")

result = subprocess.run(
    [
        "dbt", "run",
        "--project-dir", DBT_PROJECT_DIR,
        "--target", "prod",  # Use production catalog
        "--select", "models/",  # Run all models
    ],
    capture_output=True,
    text=True
)

print(result.stdout)

if result.returncode != 0:
    print("❌ dbt run failed")
    print(result.stderr)
    dbutils.notebook.exit("FAILED: dbt run")

print("✅ dbt models executed successfully")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Data Quality Tests

# COMMAND ----------

# Run dbt tests to validate data quality
print("🧪 Running data quality tests...")

result = subprocess.run(
    [
        "dbt", "test",
        "--project-dir", DBT_PROJECT_DIR,
        "--target", "prod",
    ],
    capture_output=True,
    text=True
)

print(result.stdout)

if result.returncode != 0:
    print("⚠️ Some data quality tests failed")
    print(result.stderr)
    # Don't exit - log warning but continue
else:
    print("✅ All data quality tests passed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optimize Delta Tables

# COMMAND ----------

# Run Delta Lake optimizations (OPTIMIZE + ZORDER)
print("⚡ Optimizing Delta tables...")

spark.sql("""
  OPTIMIZE mtgecorec_prod.pricing.pricing_daily
  ZORDER BY (card_name)
""")

print("✅ Delta table optimized")

# Clean up old files (keep 7 days)
spark.sql("""
  VACUUM mtgecorec_prod.pricing.pricing_daily
  RETAIN 168 HOURS
""")

print("✅ Old Delta files cleaned up")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary Statistics

# COMMAND ----------

# Get table statistics
spark.sql("USE CATALOG mtgecorec_prod")
spark.sql("USE SCHEMA pricing")

# Row counts
pricing_daily_count = spark.table("pricing_daily").count()
pricing_latest_count = spark.table("pricing_latest").count()

print("\nDelta Lake Statistics")
print("=" * 60)
print(f"pricing_daily (all history): {pricing_daily_count:,} rows")
print(f"pricing_latest (today only):  {pricing_latest_count:,} rows")

# Partition information
print("\n📅 Partition Distribution (Last 7 Days)")
partition_stats = spark.sql("""
  SELECT 
    ds,
    COUNT(*) as row_count,
    COUNT(DISTINCT scryfall_id) as unique_cards,
    ROUND(AVG(usd), 2) as avg_usd_price
  FROM pricing_daily
  WHERE ds >= DATE_SUB(CURRENT_DATE(), 7)
  GROUP BY ds
  ORDER BY ds DESC
""").collect()

print(f"{'Date':<12} {'Rows':<10} {'Cards':<10} {'Avg USD Price':<15}")
print("-" * 60)
for row in partition_stats:
    print(f"{row.ds:<12} {row.row_count:<10,} {row.unique_cards:<10,} ${row.avg_usd_price:<15.2f}")

print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate dbt Documentation

# COMMAND ----------

# Generate dbt docs (optional - useful for debugging)
print("📚 Generating dbt documentation...")

result = subprocess.run(
    [
        "dbt", "docs", "generate",
        "--project-dir", DBT_PROJECT_DIR,
        "--target", "prod",
    ],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("dbt documentation generated")
    print("   View at: /Workspace/mtgecorec/dbt_pricing/target/index.html")
else:
    print("Documentation generation failed (non-critical)")

# COMMAND ----------

print("\nTransformation pipeline complete!")
print("Data available at: mtgecorec_prod.pricing.pricing_latest")
print("Query example: SELECT * FROM mtgecorec_prod.pricing.pricing_latest LIMIT 10")
