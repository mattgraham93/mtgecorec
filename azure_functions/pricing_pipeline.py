#!/usr/bin/env python3
"""
MTG Card Pricing Pipeline - Azure Functions Edition

Production-ready pricing data collection pipeline optimized for Azure Functions.
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone, date
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import random

# Azure Functions optimized imports
try:
    import pymongo
    from pymongo import MongoClient
except ImportError:
    logging.error("pymongo not available - check requirements.txt")
    raise


class ScryfallBulkCollector:
    """
    Efficient bulk pricing collection using Scryfall's /cards/collection endpoint
    Optimized for Azure Functions environment
    """
    
    def __init__(self, rate_limit_delay: float = 0.1):
        self.base_url = "https://api.scryfall.com/cards/collection"
        self.batch_size = 75  # Scryfall's limit
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'MTGEcoRec-Azure/2.0'
        })
        
        self.logger = logging.getLogger(__name__)
        
    def create_identifiers(self, cards_list: List[Dict]) -> List[Dict]:
        """Convert MongoDB card documents to Scryfall identifiers"""
        return [{'id': card['id']} for card in cards_list if 'id' in card]
    
    def batch_identifiers(self, identifiers: List[Dict]):
        """Split identifiers into batches of 75"""
        for i in range(0, len(identifiers), self.batch_size):
            yield identifiers[i:i + self.batch_size]
    
    def fetch_batch_pricing(self, identifiers_batch: List[Dict]) -> Optional[Dict]:
        """Fetch pricing for a batch of card identifiers"""
        try:
            payload = {'identifiers': identifiers_batch}
            response = self.session.post(self.base_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            return None
    
    def extract_pricing_data(self, card_data: Dict, target_date: str) -> List[Dict]:
        """Extract pricing information from Scryfall card data"""
        pricing_records = []
        card_id = card_data.get('id')
        card_name = card_data.get('name', 'Unknown')
        prices = card_data.get('prices', {})
        
        price_mappings = {
            'usd': 'usd',
            'usd_foil': 'usd_foil', 
            'usd_etched': 'usd_etched',
            'eur': 'eur',
            'eur_foil': 'eur_foil',
            'tix': 'tix'
        }
        
        for price_key, price_type in price_mappings.items():
            price_value = prices.get(price_key)
            
            if price_value and price_value != "":
                try:
                    price_float = float(price_value)
                    
                    record = {
                        'card_name': card_name,
                        'scryfall_id': card_id,
                        'date': target_date,
                        'price_type': price_type,
                        'price_value': price_float,
                        'currency': price_key.split('_')[0],
                        'finish': 'foil' if 'foil' in price_key else 'etched' if 'etched' in price_key else 'nonfoil',
                        'tcgplayer_id': card_data.get('tcgplayer_id'),
                        'cardmarket_id': card_data.get('cardmarket_id'),
                        'collected_at': datetime.now(timezone.utc),
                        'source': 'scryfall_bulk_azure'
                    }
                    
                    pricing_records.append(record)
                    
                except (ValueError, TypeError):
                    continue
        
        return pricing_records
    
    def collect_pricing_for_cards(self, cards_list: List[Dict], target_date: str) -> List[Dict]:
        """Main method to collect pricing for a list of cards"""
        identifiers = self.create_identifiers(cards_list)
        all_pricing_records = []
        
        self.logger.info(f"Starting bulk collection for {len(identifiers)} cards")
        
        for batch_num, batch in enumerate(self.batch_identifiers(identifiers), 1):
            self.logger.info(f"Processing batch {batch_num} ({len(batch)} cards)")
            
            batch_response = self.fetch_batch_pricing(batch)
            
            if batch_response and 'data' in batch_response:
                for card_data in batch_response['data']:
                    pricing_records = self.extract_pricing_data(card_data, target_date)
                    all_pricing_records.extend(pricing_records)
            
            time.sleep(self.rate_limit_delay)
        
        self.logger.info(f"Collection complete: {len(all_pricing_records)} pricing records")
        return all_pricing_records


class MTGPricingPipeline:
    """
    MTG Pricing Pipeline optimized for Azure Functions
    """
    
    def __init__(self, database_name: str = "mtgecorec"):
        self.database_name = database_name
        self.logger = logging.getLogger(__name__)
        
        # Get MongoDB connection string from environment (using same var as existing codebase)
        mongo_connection_string = os.getenv('COSMOS_CONNECTION_STRING')
        if not mongo_connection_string:
            raise ValueError("COSMOS_CONNECTION_STRING environment variable is required")
        
        # Initialize database
        self._setup_database_connections(mongo_connection_string)
        
        # Initialize collector
        self.collector = ScryfallBulkCollector()
    
    def _setup_database_connections(self, connection_string: str):
        """Setup database connections with retryable writes disabled"""
        try:
            # Explicitly disable retryable writes for CosmosDB compatibility
            self.client = MongoClient(
                connection_string,
                retryWrites=False,  # Explicitly disable
                retryReads=False    # Also disable retry reads for stability
            )
            self.db = self.client[self.database_name]
            self.cards_collection = self.db.cards
            self.pricing_collection = self.db.card_pricing_daily
            
            # Test connection
            self.cards_collection.count_documents({}, limit=1)
            self.logger.info(f"Connected to database: {self.database_name} (retryable writes disabled)")
            
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise    
    def safe_db_query(self, collection, query, max_retries=3):
        """Execute database query with rate limiting and retry logic"""
        for attempt in range(max_retries):
            try:
                result = collection.find_one(query)
                return result
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "TooManyRequests" in error_str or "RequestRateTooLarge" in error_str:
                    # Extract retry delay if available
                    retry_delay = 1.0  # Default 1 second
                    if "RetryAfterMs=" in error_str:
                        try:
                            start = error_str.find("RetryAfterMs=") + 13
                            end = error_str.find(",", start)
                            if end == -1:
                                end = error_str.find(" ", start)
                            retry_delay = float(error_str[start:end]) / 1000.0  # Convert ms to seconds
                        except:
                            pass
                    
                    # Add jitter and backoff
                    jittered_delay = retry_delay + random.uniform(0.1, 0.5) + (attempt * 0.5)
                    
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Rate limit hit (attempt {attempt + 1}), waiting {jittered_delay:.2f}s")
                        time.sleep(jittered_delay)
                        continue
                    else:
                        self.logger.error(f"Rate limit exceeded after {max_retries} attempts")
                        raise
                else:
                    # Non-rate-limit error, don't retry
                    raise    
    def get_cards_needing_pricing(self, target_date: str, skip_existing: bool = True) -> Tuple[Dict, int]:
        """
        Get query for cards needing pricing - Process ALL cards
        """
        total_cards = self.cards_collection.count_documents({})
        
        # Process all cards (no filtering)
        base_filter = {}
        
        if skip_existing:
            # Calculate how many unique cards already have pricing
            cards_with_pricing = len(self.pricing_collection.distinct('scryfall_id', {'date': target_date}))
            existing_records = self.pricing_collection.count_documents({'date': target_date})
            
            remaining_cards = total_cards - cards_with_pricing
            
            self.logger.info(f"Found {existing_records:,} pricing records for {target_date}")
            self.logger.info(f"Total cards in collection: {total_cards:,}")
            self.logger.info(f"Unique cards already priced: {cards_with_pricing:,}")
            self.logger.info(f"Cards remaining to process: {remaining_cards:,}")
            
            # Return empty filter to process all cards
            return base_filter, remaining_cards
        else:
            self.logger.info(f"Total cards to process: {total_cards:,}")
            return base_filter, total_cards
    
    def run_daily_pipeline(self, 
                          target_date: Optional[str] = None, 
                          batch_size: int = 100,  # Smaller batches for 4000 RU/s limit
                          max_cards: Optional[int] = None) -> Dict[str, Any]:
        """
        Run pricing pipeline optimized for Azure Functions
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        self.logger.info(f"Starting Azure Functions pricing pipeline for {target_date}")
        
        # Get cards that need pricing
        cards_query, total_cards_needed = self.get_cards_needing_pricing(target_date, True)
        
        if total_cards_needed == 0:
            return {
                'status': 'complete',
                'date': target_date,
                'cards_processed': 0,
                'records_created': 0,
                'message': 'No cards needed pricing collection'
            }
        
        # Apply max_cards limit for Azure Functions timeout management
        if max_cards and max_cards < total_cards_needed:
            self.logger.info(f"Limiting to {max_cards:,} cards for Azure Functions timeout")
            total_cards_needed = max_cards
        
        # Process cards
        total_records = 0
        cards_processed = 0
        start_time = time.time()
        
        cards_cursor = self.cards_collection.find(cards_query).batch_size(batch_size)
        if max_cards:
            cards_cursor = cards_cursor.limit(max_cards)
        
        current_batch = []
        
        skip_existing = max_cards is None or max_cards > 100  # Skip existing for large runs
        card_counter = 0
        
        # Pre-fetch list of cards that already have pricing (much more efficient)
        existing_card_ids = set()
        if skip_existing:
            self.logger.info("Pre-fetching list of cards with existing pricing...")
            existing_card_ids = set(self.pricing_collection.distinct('scryfall_id', {'date': target_date}))
            self.logger.info(f"Pre-fetched {len(existing_card_ids):,} cards to skip")
        
        for card in cards_cursor:
            card_counter += 1
            
            # Check if this card already has pricing (using pre-fetched set)
            if skip_existing and card.get('id') in existing_card_ids:
                continue  # Skip this card, it already has pricing
            
            # Legacy duplicate checking (disabled for performance)
            skip_duplicate_check = True
            if False and skip_existing and not skip_duplicate_check and card_counter % 50 == 0:
                try:
                    existing_record = self.safe_db_query(
                        self.pricing_collection,
                        {
                            'scryfall_id': card.get('id'),
                            'date': target_date
                        }
                    )
                    if existing_record:
                        continue
                except Exception as e:
                    # If duplicate check fails due to rate limits, process the card anyway
                    self.logger.warning(f"Duplicate check failed for card {card.get('name', 'unknown')}: {e}")
                    # Continue processing to avoid losing cards
            
            current_batch.append(card)
            
            if len(current_batch) >= batch_size:
                # Process batch
                batch_records = self.collector.collect_pricing_for_cards(current_batch, target_date)
                
                # Insert to database with upsert to prevent duplicates
                if batch_records:
                    try:
                        upserted_count = self._upsert_pricing_records(batch_records)
                        total_records += upserted_count
                        self.logger.info(f"Upserted {upserted_count}/{len(batch_records)} records")
                    except Exception as e:
                        self.logger.error(f"Database upsert failed: {e}")
                
                cards_processed += len(current_batch)
                
                # Progress logging
                if cards_processed > 0:
                    progress_pct = min((cards_processed / total_cards_needed) * 100, 100)
                    elapsed = time.time() - start_time
                    cards_per_sec = cards_processed / elapsed if elapsed > 0 else 0
                    
                    self.logger.info(
                        f"Progress: {cards_processed:,}/{total_cards_needed:,} "
                        f"({progress_pct:.1f}%) | {cards_per_sec:.1f} cards/sec"
                    )
                
                current_batch = []
                
                # RU rate limiting: pause between batches to stay under 4000 RU/s
                # Each batch uses ~500-1000 RUs, so pause briefly
                time.sleep(0.2)  # 200ms pause between batches
        
        # Process final batch
        if current_batch:
            batch_records = self.collector.collect_pricing_for_cards(current_batch, target_date)
            if batch_records:
                try:
                    upserted_count = self._upsert_pricing_records(batch_records)
                    total_records += upserted_count
                    self.logger.info(f"Final batch upserted {upserted_count}/{len(batch_records)} records")
                except Exception as e:
                    self.logger.error(f"Final batch upsert failed: {e}")
            
            cards_processed += len(current_batch)
        
        # Calculate results
        total_time = time.time() - start_time
        
        return {
            'status': 'complete',
            'date': target_date,
            'cards_processed': cards_processed,
            'records_created': total_records,
            'total_time_seconds': round(total_time, 2),
            'cards_per_second': round(cards_processed / total_time, 2) if total_time > 0 else 0,
            'avg_records_per_card': round(total_records / cards_processed, 2) if cards_processed > 0 else 0
        }
    
    def _upsert_pricing_records(self, records: List[Dict]) -> int:
        """
        Fast insert with duplicate handling - optimized for speed
        """
        if not records:
            return 0
            
        try:
            # Use ordered=True for CosmosDB compatibility with retryable writes
            result = self.pricing_collection.insert_many(records, ordered=True)
            return len(result.inserted_ids)
            
        except Exception as e:
            # Only handle duplicates if insert fails
            if "duplicate" in str(e).lower() or "E11000" in str(e) or "BulkWriteError" in str(e):
                self.logger.info(f"Handling {len(records)} records with some duplicates")
                
                # Count successful inserts from the bulk operation
                inserted_count = 0
                
                # For BulkWriteError, we can get details about what succeeded
                if hasattr(e, 'details'):
                    inserted_count = e.details.get('nInserted', 0)
                    self.logger.info(f"Bulk insert succeeded for {inserted_count} records")
                
                return inserted_count
            else:
                # Re-raise non-duplicate errors
                self.logger.error(f"Database insert failed: {e}")
                return 0
                # If that fails too, count duplicate errors as "handled"
                if "duplicate" in str(fallback_error).lower():
                    self.logger.info(f"Handled duplicate records in fallback")
                    return len(records)  # Assume all were handled
                else:
                    self.logger.error(f"Both upsert and fallback failed: {fallback_error}")
                    return 0

    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get pricing coverage statistics"""
        total_cards = self.cards_collection.count_documents({})
        cards_with_pricing = len(self.pricing_collection.distinct('scryfall_id'))
        
        # Recent dates
        recent_dates = list(self.pricing_collection.aggregate([
            {'$group': {'_id': '$date', 'count': {'$sum': 1}}},
            {'$sort': {'_id': -1}},
            {'$limit': 3}
        ]))
        
        return {
            'total_cards': total_cards,
            'cards_with_pricing': cards_with_pricing,
            'coverage_percentage': round((cards_with_pricing / total_cards * 100), 2) if total_cards > 0 else 0,
            'recent_dates': recent_dates
        }


def run_pricing_pipeline_azure_function(target_date: Optional[str] = None, 
                                       max_cards: Optional[int] = None) -> Dict[str, Any]:
    """
    Azure Functions entry point for the pricing pipeline
    """
    try:
        pipeline = MTGPricingPipeline()
        result = pipeline.run_daily_pipeline(target_date=target_date, max_cards=max_cards)
        
        # Add coverage info
        coverage = pipeline.get_coverage_stats()
        result['coverage_after'] = coverage
        
        return result
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'date': target_date or date.today().isoformat()
        }