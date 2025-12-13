#!/usr/bin/env python3
"""
MTG Card Pricing Pipeline

Production-ready pricing data collection pipeline that efficiently fetches
pricing data from Scryfall's bulk API and stores it in MongoDB.

Key Features:
- Bulk API processing (75 cards per request)
- Comprehensive pricing data (USD, EUR, MTGO, foil variants)
- Smart duplicate prevention
- Robust error handling and logging
- Azure Functions compatible

Usage:
    from core.data_engine.pricing_pipeline import MTGPricingPipeline
    
    pipeline = MTGPricingPipeline()
    result = pipeline.run_daily_pipeline()
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone, date
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

# Import the core database driver
sys.path.append('/workspaces/mtgecorec')
from core.data_engine.cosmos_driver import get_mongo_client, get_collection


class ScryfallBulkCollector:
    """
    Efficient bulk pricing collection using Scryfall's /cards/collection endpoint
    Handles up to 75 cards per request with comprehensive price data extraction
    """
    
    def __init__(self, rate_limit_delay: float = 0.1):
        """
        Initialize the bulk collector
        
        Args:
            rate_limit_delay: Delay between API calls in seconds
        """
        self.base_url = "https://api.scryfall.com/cards/collection"
        self.batch_size = 75  # Scryfall's limit
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'MTGEcoRec/2.0'
        })
        
        # Setup logging
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
    
    def extract_pricing_data(self, card_data: Dict, target_date: Optional[str] = None) -> List[Dict]:
        """Extract all available pricing information from Scryfall card data"""
        if target_date is None:
            target_date = date.today().isoformat()
            
        pricing_records = []
        card_id = card_data.get('id')
        card_name = card_data.get('name', 'Unknown')
        prices = card_data.get('prices', {})
        
        # All available price types
        price_mappings = {
            'usd': 'usd',
            'usd_foil': 'usd_foil', 
            'usd_etched': 'usd_etched',
            'eur': 'eur',
            'eur_foil': 'eur_foil',
            'tix': 'tix'  # MTGO tickets
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
                        'currency': price_key.split('_')[0],  # usd, eur, tix
                        'finish': 'foil' if 'foil' in price_key else 'etched' if 'etched' in price_key else 'nonfoil',
                        'tcgplayer_id': card_data.get('tcgplayer_id'),
                        'cardmarket_id': card_data.get('cardmarket_id'),
                        'collected_at': datetime.now(timezone.utc),
                        'source': 'scryfall_bulk'
                    }
                    
                    pricing_records.append(record)
                    
                except (ValueError, TypeError):
                    continue
        
        return pricing_records
    
    def collect_pricing_for_cards(self, cards_list: List[Dict], target_date: Optional[str] = None) -> List[Dict]:
        """Main method to collect pricing for a list of cards"""
        if target_date is None:
            target_date = date.today().isoformat()
            
        identifiers = self.create_identifiers(cards_list)
        all_pricing_records = []
        
        self.logger.info(f"Starting bulk collection for {len(identifiers)} cards")
        
        for batch_num, batch in enumerate(self.batch_identifiers(identifiers), 1):
            self.logger.info(f"Processing batch {batch_num} ({len(batch)} cards)")
            
            # Fetch batch data
            batch_response = self.fetch_batch_pricing(batch)
            
            if batch_response and 'data' in batch_response:
                # Process each card in the batch
                for card_data in batch_response['data']:
                    pricing_records = self.extract_pricing_data(card_data, target_date)
                    all_pricing_records.extend(pricing_records)
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
        
        self.logger.info(f"Collection complete: {len(all_pricing_records)} pricing records")
        return all_pricing_records


class MTGPricingPipeline:
    """
    MTG Card Pricing Data Collection Pipeline
    
    Orchestrates the collection of pricing data from Scryfall and storage in MongoDB.
    Designed for production use with Azure Functions.
    """
    
    def __init__(self, 
                 mongo_connection_string: Optional[str] = None, 
                 database_name: str = "mtgecorec",
                 rate_limit_delay: float = 0.1):
        """
        Initialize the pricing pipeline
        
        Args:
            mongo_connection_string: MongoDB connection string (from env if not provided)
            database_name: Name of the MongoDB database
            rate_limit_delay: Delay between API calls in seconds
        """
        self.database_name = database_name
        
        # Setup MongoDB connection
        if mongo_connection_string is None:
            mongo_connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        
        if not mongo_connection_string:
            raise ValueError("MongoDB connection string must be provided or set in MONGODB_CONNECTION_STRING env var")
        
        # Initialize database connections
        self._setup_database_connections()
        
        # Initialize collector
        self.collector = ScryfallBulkCollector(rate_limit_delay=rate_limit_delay)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def _setup_database_connections(self):
        """Setup database connections with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.client = get_mongo_client()
                self.cards_collection = get_collection(self.client, self.database_name, "cards")
                self.pricing_collection = get_collection(self.client, self.database_name, "card_pricing_daily")
                
                # Test connection
                self.cards_collection.count_documents({}, limit=1)
                self.logger.info(f"Connected to database: {self.database_name}")
                return
                
            except Exception as e:
                self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise ConnectionError(f"Failed to connect to database after {max_retries} attempts")
    
    def get_cards_needing_pricing(self, target_date: str, skip_existing: bool = True) -> Tuple[List[Dict], int]:
        """
        Get cards that need pricing data for the target date
        
        Args:
            target_date: Date string in YYYY-MM-DD format
            skip_existing: Skip cards that already have pricing for this date
            
        Returns:
            Tuple of (cards_list, total_count)
        """
        if skip_existing:
            # Get cards without pricing for this date
            existing_card_ids = set(
                record['scryfall_id'] 
                for record in self.pricing_collection.find(
                    {'date': target_date}, 
                    {'scryfall_id': 1}
                )
            )
            
            cards_query = {'id': {'$nin': list(existing_card_ids)}}
            self.logger.info(f"Skipping {len(existing_card_ids)} cards with existing pricing")
        else:
            cards_query = {}
        
        total_count = self.cards_collection.count_documents(cards_query)
        self.logger.info(f"Cards needing pricing: {total_count:,}")
        
        return cards_query, total_count
    
    def process_batch(self, 
                     cards_batch: List[Dict], 
                     target_date: str) -> Dict[str, int]:
        """
        Process a batch of cards for pricing data
        
        Args:
            cards_batch: List of card documents
            target_date: Target date string
            
        Returns:
            Dictionary with batch processing statistics
        """
        batch_records = self.collector.collect_pricing_for_cards(cards_batch, target_date)
        
        # Insert to database
        records_inserted = 0
        if batch_records:
            try:
                self.pricing_collection.insert_many(batch_records)
                records_inserted = len(batch_records)
            except Exception as e:
                self.logger.error(f"Error inserting batch records: {e}")
        
        return {
            'cards_processed': len(cards_batch),
            'records_created': records_inserted
        }
    
    def run_daily_pipeline(self, 
                          target_date: Optional[str] = None, 
                          batch_size: int = 1000, 
                          skip_existing: bool = True,
                          max_cards: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the daily pricing pipeline
        
        Args:
            target_date: Date string (YYYY-MM-DD) or None for today
            batch_size: Number of cards to process per database batch
            skip_existing: Skip cards that already have pricing for target_date
            max_cards: Maximum number of cards to process (for chunking)
            
        Returns:
            Dictionary with pipeline statistics
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        self.logger.info(f"Starting pricing pipeline for {target_date}")
        
        # Get cards that need pricing
        cards_query, total_cards_needed = self.get_cards_needing_pricing(target_date, skip_existing)
        
        if total_cards_needed == 0:
            self.logger.info("No cards need pricing collection")
            return {
                'status': 'complete',
                'date': target_date,
                'cards_processed': 0,
                'records_created': 0
            }
        
        # Apply max_cards limit if specified (for chunking)
        if max_cards and max_cards < total_cards_needed:
            self.logger.info(f"Limiting processing to {max_cards:,} cards (chunking mode)")
            total_cards_needed = max_cards
        
        # Process in batches
        total_records = 0
        cards_processed = 0
        start_time = time.time()
        
        cards_cursor = self.cards_collection.find(cards_query).batch_size(batch_size)
        if max_cards:
            cards_cursor = cards_cursor.limit(max_cards)
        
        current_batch = []
        
        for card in cards_cursor:
            current_batch.append(card)
            
            if len(current_batch) >= batch_size:
                # Process batch
                batch_stats = self.process_batch(current_batch, target_date)
                
                total_records += batch_stats['records_created']
                cards_processed += batch_stats['cards_processed']
                
                # Progress logging
                progress_pct = (cards_processed / total_cards_needed) * 100
                elapsed_time = time.time() - start_time
                cards_per_sec = cards_processed / elapsed_time if elapsed_time > 0 else 0
                
                self.logger.info(
                    f"Progress: {cards_processed:,}/{total_cards_needed:,} "
                    f"({progress_pct:.1f}%) | {cards_per_sec:.1f} cards/sec | "
                    f"Records: {total_records:,}"
                )
                
                current_batch = []
        
        # Process final batch
        if current_batch:
            batch_stats = self.process_batch(current_batch, target_date)
            total_records += batch_stats['records_created']
            cards_processed += batch_stats['cards_processed']
        
        # Calculate final statistics
        total_time = time.time() - start_time
        
        result = {
            'status': 'complete',
            'date': target_date,
            'cards_processed': cards_processed,
            'records_created': total_records,
            'total_time_seconds': total_time,
            'cards_per_second': cards_processed / total_time if total_time > 0 else 0,
            'avg_records_per_card': total_records / cards_processed if cards_processed > 0 else 0
        }
        
        self.logger.info(
            f"Pipeline complete: {cards_processed:,} cards, "
            f"{total_records:,} records in {total_time:.1f}s"
        )
        
        return result
    
    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get current pricing coverage statistics"""
        total_cards = self.cards_collection.count_documents({})
        
        # Cards with any pricing
        cards_with_pricing = len(
            self.pricing_collection.distinct('scryfall_id')
        )
        
        # Recent pricing by date
        pricing_by_date = list(self.pricing_collection.aggregate([
            {'$group': {'_id': '$date', 'count': {'$sum': 1}}},
            {'$sort': {'_id': -1}},
            {'$limit': 5}
        ]))
        
        # Price type distribution
        price_types = list(self.pricing_collection.aggregate([
            {'$group': {'_id': '$price_type', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]))
        
        return {
            'total_cards': total_cards,
            'cards_with_pricing': cards_with_pricing,
            'coverage_percentage': (cards_with_pricing / total_cards * 100) if total_cards > 0 else 0,
            'recent_dates': pricing_by_date,
            'price_types': price_types
        }


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration for the pipeline"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )


# Azure Functions entry point
def run_pricing_pipeline_azure_function(target_date: Optional[str] = None, 
                                       max_cards: Optional[int] = None) -> Dict[str, Any]:
    """
    Azure Functions entry point for the pricing pipeline
    
    Args:
        target_date: Date string (YYYY-MM-DD) or None for today
        max_cards: Maximum cards to process (for chunking across multiple function calls)
        
    Returns:
        Dictionary with pipeline results
    """
    setup_logging()
    
    try:
        pipeline = MTGPricingPipeline()
        result = pipeline.run_daily_pipeline(
            target_date=target_date,
            max_cards=max_cards,
            skip_existing=True
        )
        
        # Add coverage stats
        coverage_stats = pipeline.get_coverage_stats()
        result.update({
            'coverage_after': coverage_stats
        })
        
        return result
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'date': target_date or date.today().isoformat()
        }


if __name__ == "__main__":
    """Command line execution for testing"""
    setup_logging()
    
    # Test run
    result = run_pricing_pipeline_azure_function()
    
    print("\n" + "=" * 50)
    print("PIPELINE RESULTS")
    print("=" * 50)
    for key, value in result.items():
        if isinstance(value, (int, float)) and key in ['cards_processed', 'records_created']:
            print(f"{key}: {value:,}")
        else:
            print(f"{key}: {value}")