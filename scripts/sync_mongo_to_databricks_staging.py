"""
Sync MongoDB Pricing Data to Databricks Staging Table
Reads unpivoted data from MongoDB, pivots it, and loads into Databricks

Features:
- Retry logic with exponential backoff for rate limits
- Chunked MongoDB fetching to avoid timeouts
- Progress tracking throughout
- Dry-run mode for testing
"""
import os
import sys
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ExecutionTimeout
from databricks import sql
import pandas as pd
from datetime import datetime, timedelta
import argparse

# Load environment
load_dotenv('/workspaces/mtgecorec/.env')

class MongoToDatabricksSync:
    """Sync pricing data from MongoDB to Databricks staging"""
    
    def __init__(self):
        # MongoDB connection
        self.mongo_uri = os.getenv('COSMOS_CONNECTION_STRING')
        self.mongo_client = None
        self.mongo_db = None
        
        # Databricks connection
        self.databricks_host = os.getenv('DATABRICKS_HOST')
        self.databricks_http_path = os.getenv('DATABRICKS_HTTP_PATH')
        self.databricks_token = os.getenv('DATABRICKS_TOKEN')
        
        self._validate_config()
    
    def _validate_config(self):
        """Check all required environment variables"""
        missing = []
        if not self.mongo_uri:
            missing.append('COSMOS_CONNECTION_STRING')
        if not self.databricks_host:
            missing.append('DATABRICKS_HOST')
        if not self.databricks_http_path:
            missing.append('DATABRICKS_HTTP_PATH')
        if not self.databricks_token:
            missing.append('DATABRICKS_TOKEN')
        
        if missing:
            print(f"❌ Missing environment variables: {', '.join(missing)}")
            print("   Check /workspaces/mtgecorec/.env file")
            sys.exit(1)
    
    def _retry_with_backoff(self, func, max_retries=5, initial_delay=2):
        """
        Retry a function with exponential backoff
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            
        Returns:
            Result of function call
        """
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return func()
            except (OperationFailure, ExecutionTimeout) as e:
                error_msg = str(e)
                # Check if it's a rate limit error or timeout
                if 'Request timed out' in error_msg or 'rate limiting' in error_msg.lower() or 'ExecutionTimeout' in str(type(e)):
                    if attempt < max_retries - 1:
                        print(f"   ⚠️  Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        print(f"   ❌ Max retries reached. Cosmos DB RUs may be too low.")
                        raise
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
        
        return None
    
    def connect_mongodb(self):
        """Connect to MongoDB"""
        try:
            self.mongo_client = MongoClient(
                self.mongo_uri, 
                serverSelectionTimeoutMS=5000
            )
            self.mongo_db = self.mongo_client['mtgecorec']
            self.mongo_db.command('ping')
            print("✅ Connected to MongoDB")
            return True
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            return False
    
    def fetch_pricing_data(self, date=None, chunk_size=10000, limit=None):
        """
        Fetch pricing data from MongoDB for a specific date or limited number of records
        
        Args:
            date: Date string (YYYY-MM-DD) or None for latest
            chunk_size: Number of documents to fetch per chunk (default: 10000)
            limit: Maximum number of records to fetch (overrides date if set)
            
        Returns:
            DataFrame with unpivoted pricing data
        """
        collection = self.mongo_db['card_pricing_daily']
        
        # Determine query and count
        if limit:
            print(f"\n📥 Fetching first {limit:,} records (ignoring date)")
            query = {}  # No date filter
            total_docs = limit
        else:
            # Get latest date if not specified
            if date is None:
                # Use aggregation instead of sort (Cosmos DB indexing limitation)
                pipeline = [
                    {"$group": {"_id": "$date"}},
                    {"$sort": {"_id": -1}},
                    {"$limit": 1}
                ]
                
                def get_latest_date():
                    return list(collection.aggregate(pipeline))
                
                try:
                    latest_result = self._retry_with_backoff(get_latest_date)
                except Exception as e:
                    print(f"❌ Failed to get latest date: {e}")
                    return None
                
                if not latest_result:
                    print("❌ No data found in MongoDB")
                    return None
                date = latest_result[0]['_id']
            
            print(f"\n📥 Fetching data for date: {date}")
            query = {"date": date}
            total_docs = None  # Will get count via retry
        
        print(f"   Chunk size: {chunk_size:,} documents")
        
        # Projection
        projection = {
            '_id': 0,
            'scryfall_id': 1,
            'card_name': 1,
            'date': 1,
            'price_type': 1,
            'price_value': 1
        }
        
        # Fetch data in chunks to avoid Cosmos DB rate limits
        print(f"   Fetching in chunks to avoid rate limits...")
        all_data = []
        
        # Get total count if not using limit (with retry)
        if not limit:
            def count_docs():
                return collection.count_documents(query)
            
            try:
                total_docs = self._retry_with_backoff(count_docs)
                print(f"   Total documents to fetch: {total_docs:,}")
            except Exception as e:
                print(f"   ⚠️  Could not get count (rate limited), fetching all data...")
                total_docs = None
        
        # Fetch in chunks
        skip = 0
        fetched = 0
        while True:
            # If we're using a limit, stop when we reach it
            if limit and fetched >= limit:
                break
            
            # Adjust chunk size if we're near the limit
            current_chunk_size = chunk_size
            if limit and (fetched + chunk_size) > limit:
                current_chunk_size = limit - fetched
            
            def fetch_chunk():
                return list(collection.find(query, projection).skip(skip).limit(current_chunk_size))
            
            try:
                chunk = self._retry_with_backoff(fetch_chunk)
            except Exception as e:
                print(f"   ❌ Failed to fetch chunk at offset {skip}: {e}")
                if all_data:  # If we got some data, continue with what we have
                    print(f"   ⚠️  Continuing with {len(all_data):,} records fetched so far...")
                    break
                else:
                    raise
            
            if not chunk:
                break
            
            all_data.extend(chunk)
            fetched += len(chunk)
            skip += chunk_size
            
            # Progress indicator
            if total_docs:
                progress = (fetched / total_docs) * 100
                print(f"   Progress: {fetched:,}/{total_docs:,} ({progress:.1f}%)")
            else:
                print(f"   Fetched: {fetched:,} records...")
            
            if len(chunk) < chunk_size:
                break  # Last chunk
        
        df = pd.DataFrame(all_data)
        
        if df.empty:
            print(f"❌ No data found for date: {date}")
            return None
        
        print(f"   ✅ Fetched {len(df):,} unpivoted records")
        return df
    
    def pivot_pricing_data(self, df):
        """
        Transform unpivoted data to pivoted format
        
        Input format (6 rows per card):
            scryfall_id | card_name | date | price_type | price_value
            
        Output format (1 row per card):
            scryfall_id | card_name | ds | usd | usd_foil | usd_etched | eur | eur_foil | tix
        """
        print("\n🔄 Pivoting data...")
        
        # Pivot transformation
        pivoted = df.pivot_table(
            index=['scryfall_id', 'card_name', 'date'],
            columns='price_type',
            values='price_value',
            aggfunc='first'
        ).reset_index()
        
        # Rename date column to ds (date string)
        pivoted.rename(columns={'date': 'ds'}, inplace=True)
        
        # Ensure all expected price columns exist
        expected_columns = ['usd', 'usd_foil', 'usd_etched', 'eur', 'eur_foil', 'tix']
        for col in expected_columns:
            if col not in pivoted.columns:
                pivoted[col] = None
        
        # Reorder columns
        final_columns = ['scryfall_id', 'card_name', 'ds'] + expected_columns
        pivoted = pivoted[final_columns]
        
        print(f"   Pivoted to {len(pivoted):,} rows (1 per card)")
        print(f"   Reduction: {len(df):,} → {len(pivoted):,} ({(1 - len(pivoted)/len(df)) * 100:.1f}% smaller)")
        
        return pivoted
    
    def write_to_databricks(self, df, catalog='mtgecorec_dev', schema='staging', batch_size=100):
        """Write pivoted data to Databricks staging table"""
        
        table_name = f"{catalog}.{schema}.card_pricing_daily_staging"
        print(f"\n📤 Writing to Databricks: {table_name}")
        print(f"   Batch size: {batch_size} rows")
        
        try:
            with sql.connect(
                server_hostname=self.databricks_host,
                http_path=self.databricks_http_path,
                access_token=self.databricks_token
            ) as connection:
                
                with connection.cursor() as cursor:
                    # Drop and recreate table (full refresh for now)
                    print("   Dropping existing table...")
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    
                    # Create table from DataFrame
                    print("   Creating new table...")
                    
                    # Convert DataFrame to SQL INSERT statements
                    # Note: For production, use Delta Lake COPY INTO or spark.write
                    # This is a simple approach for Phase 1
                    
                    create_sql = f"""
                    CREATE TABLE {table_name} (
                        scryfall_id STRING,
                        card_name STRING,
                        ds STRING,
                        usd DOUBLE,
                        usd_foil DOUBLE,
                        usd_etched DOUBLE,
                        eur DOUBLE,
                        eur_foil DOUBLE,
                        tix DOUBLE
                    )
                    USING DELTA
                    """
                    cursor.execute(create_sql)
                    
                    print(f"   Inserting {len(df):,} rows (this may take a few minutes)...")
                    
                    # Batch insert with smaller batch size
                    for i in range(0, len(df), batch_size):
                        batch = df.iloc[i:i+batch_size]
                        
                        # Build VALUES clause
                        values = []
                        for _, row in batch.iterrows():
                            # Escape single quotes in card names
                            card_name_escaped = str(row['card_name']).replace("'", "''")
                            
                            value_tuple = (
                                f"'{row['scryfall_id']}'",
                                f"'{card_name_escaped}'",
                                f"'{row['ds']}'",
                                str(row['usd']) if pd.notna(row['usd']) else 'NULL',
                                str(row['usd_foil']) if pd.notna(row['usd_foil']) else 'NULL',
                                str(row['usd_etched']) if pd.notna(row['usd_etched']) else 'NULL',
                                str(row['eur']) if pd.notna(row['eur']) else 'NULL',
                                str(row['eur_foil']) if pd.notna(row['eur_foil']) else 'NULL',
                                str(row['tix']) if pd.notna(row['tix']) else 'NULL'
                            )
                            values.append(f"({', '.join(value_tuple)})")
                        
                        insert_sql = f"""
                        INSERT INTO {table_name} 
                        VALUES {', '.join(values)}
                        """
                        cursor.execute(insert_sql)
                        
                        # Show progress every 1000 rows (10 batches)
                        if (i + batch_size) % 1000 == 0 or (i + batch_size) >= len(df):
                            progress = ((i + batch_size) / len(df)) * 100
                            print(f"      {i + batch_size:,}/{len(df):,} rows ({progress:.1f}%)")
                    
                    # Verify row count
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
                    result = cursor.fetchone()
                    final_count = result[0]
                    
                    print(f"   ✅ Successfully loaded {final_count:,} rows")
                    
                    # Show sample
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                    print("\n   Sample data:")
                    for row in cursor.fetchall():
                        print(f"      {row[1]}: usd=${row[3]}, usd_foil=${row[4]}")
                    
                    # Show summary statistics
                    print("\n   📊 Summary Statistics:")
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total_cards,
                            COUNT(DISTINCT ds) as unique_dates,
                            SUM(CASE WHEN usd IS NOT NULL THEN 1 ELSE 0 END) as cards_with_usd,
                            SUM(CASE WHEN usd_foil IS NOT NULL THEN 1 ELSE 0 END) as cards_with_foil,
                            AVG(usd) as avg_usd_price
                        FROM {table_name}
                    """)
                    stats = cursor.fetchone()
                    print(f"      Total cards: {stats[0]:,}")
                    print(f"      Unique dates: {stats[1]:,}")
                    print(f"      Cards with USD price: {stats[2]:,}")
                    print(f"      Cards with foil price: {stats[3]:,}")
                    if stats[4]:
                        print(f"      Average USD price: ${stats[4]:.2f}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error writing to Databricks")
            print(f"   Error: {str(e)[:200]}")  # First 200 chars
            print(f"\n💡 Troubleshooting:")
            print(f"   • Verify SQL Warehouse is running in Databricks")
            print(f"   • Check DATABRICKS_TOKEN hasn't expired")
            print(f"   • Ensure catalog/schema permissions are set")
            print(f"   • Try with fewer rows: --date <specific-date>")
            return False
    
    def sync(self, date=None, catalog='mtgecorec_dev', chunk_size=10000, batch_size=100, dry_run=False, limit=None):
        """Run full sync process"""
        
        print("=" * 60)
        print("MongoDB → Databricks Staging Sync")
        print("=" * 60)
        
        # Connect to MongoDB
        if not self.connect_mongodb():
            return False
        
        # Fetch data
        df = self.fetch_pricing_data(date, chunk_size=chunk_size, limit=limit)
        if df is None:
            return False
        
        # Pivot data
        pivoted_df = self.pivot_pricing_data(df)
        
        # Skip write if dry run
        if dry_run:
            print("\n🔍 Dry run complete - data NOT written to Databricks")
            return True
        
        # Write to Databricks
        success = self.write_to_databricks(pivoted_df, catalog=catalog, batch_size=batch_size)
        
        if success:
            print("\n✅ Sync complete! Data ready for dbt transformation")
            print(f"   Next step: cd /workspaces/mtgecorec/dbt_pricing && dbt run --target dev")
        
        return success

def main():
    parser = argparse.ArgumentParser(description='Sync MongoDB pricing to Databricks')
    parser.add_argument('--date', type=str, help='Date to sync (YYYY-MM-DD), default is latest')
    parser.add_argument('--catalog', type=str, default='mtgecorec_dev', help='Databricks catalog')
    parser.add_argument('--chunk-size', type=int, default=10000, 
                       help='MongoDB fetch chunk size (default: 10000)')
    parser.add_argument('--batch-size', type=int, default=100, 
                       help='Databricks insert batch size (default: 100)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum number of records to fetch (overrides --date)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Fetch and pivot data but do not write to Databricks')
    
    args = parser.parse_args()
    
    syncer = MongoToDatabricksSync()
    success = syncer.sync(
        date=args.date, 
        catalog=args.catalog,
        chunk_size=args.chunk_size,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        limit=args.limit
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
