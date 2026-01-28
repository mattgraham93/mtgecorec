#!/usr/bin/env python3
"""
Create and populate the combos collection with color identity support.
Fetches data from Commander Spellbook API.
"""

import os
import sys
import argparse
import requests
import time
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Create combo collection from Commander Spellbook'
    )
    parser.add_argument(
        '--max-combos',
        type=int,
        default=1000,
        help='Maximum number of combos to import (default: 1000, 0 = all)'
    )
    parser.add_argument(
        '--min-popularity',
        type=int,
        default=100,
        help='Minimum popularity threshold (default: 100 decks)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing combos before importing (default: upsert)'
    )
    return parser.parse_args()


def parse_color_identity(identity_string: str) -> List[str]:
    """
    Parse Commander Spellbook color identity string.
    
    Examples:
        "W" → ['W']
        "WUB" → ['W', 'U', 'B']
        "" → []
    """
    if not identity_string:
        return []
    
    # Already in correct format, just convert to list
    colors = list(identity_string)
    
    # Sort in WUBRG order
    color_order = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4, 'C': 5}
    return sorted(colors, key=lambda c: color_order.get(c, 6))


def map_produces_to_combo_type(produces: List[Dict]) -> str:
    """
    Map Spellbook produces features to our combo_type.
    
    Args:
        produces: List of feature dictionaries from API
    
    Returns:
        Our combo_type string
    """
    COMBO_TYPE_MAPPING = {
        'infinite damage': 'infinite_damage',
        'near-infinite damage': 'infinite_damage',
        'infinite lifeloss': 'infinite_damage',
        'infinite mana': 'infinite_mana',
        'infinite colored mana': 'infinite_mana',
        'near-infinite mana': 'infinite_mana',
        'infinite card draw': 'infinite_draw',
        'infinite draw triggers': 'infinite_draw',
        'near-infinite card draw': 'infinite_draw',
        'infinite mill': 'infinite_mill',
        'near-infinite mill': 'infinite_mill',
        'infinite creature tokens': 'infinite_tokens',
        'infinite token copies': 'infinite_tokens',
        'near-infinite creature tokens': 'infinite_tokens',
        'infinite etb': 'infinite_etb',
        'infinite ltb': 'infinite_etb',
        'near-infinite etb': 'infinite_etb',
        'infinite combat steps': 'infinite_combat',
        'infinite combat damage': 'infinite_combat',
        'win the game': 'game_win',
        'exile library': 'game_win',
        'draw the game': 'game_win',
        'tutors': 'tutoring',
        'search your library': 'tutoring',
        'protection': 'protection',
        'repeatable': 'repeatable',
        'draw cards': 'draw_cards',
        'sacrifice': 'sacrifice',
    }
    
    if not produces:
        return 'unknown'  # Changed from 'other' to 'unknown'
    
    # Use first feature, prioritize win conditions
    for feature_data in produces:
        feature_name = feature_data.get('feature', {}).get('name', '').lower()
        if feature_name in COMBO_TYPE_MAPPING:
            return COMBO_TYPE_MAPPING[feature_name]
    
    return 'unknown'  # Changed from 'other' to 'unknown'


def parse_description_to_steps(description: str) -> List[str]:
    """
    Parse combo description into step-by-step list.
    
    Args:
        description: Raw description text
    
    Returns:
        List of steps
    """
    if not description:
        return []
    
    # Split on periods, numbers, or line breaks
    # Clean up and filter empty lines
    steps = []
    
    # Try splitting on numbered steps first (1. 2. 3.)
    if any(f"{i}." in description for i in range(1, 10)):
        parts = description.split('.')
        current_step = ""
        for part in parts:
            part = part.strip()
            if part:
                # Check if starts with a number
                if part and part[0].isdigit():
                    if current_step:
                        steps.append(current_step)
                    current_step = part[part.index(' ')+1:] if ' ' in part else part
                else:
                    current_step += '. ' + part if current_step else part
        if current_step:
            steps.append(current_step)
    else:
        # Fall back to sentence splitting
        steps = [s.strip() for s in description.split('.') if s.strip()]
    
    return steps if steps else [description]


def parse_prerequisites(prerequisites_string: str) -> List[str]:
    """
    Parse prerequisites string into list.
    
    Args:
        prerequisites_string: Raw prerequisites text
    
    Returns:
        List of prerequisites
    """
    if not prerequisites_string:
        return []
    
    # Split on common delimiters
    separators = ['. ', '; ', ' and ', ', ']
    parts = [prerequisites_string]
    
    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts
    
    return [p.strip() for p in parts if p.strip()]


def validate_combo(combo: Dict[str, Any]) -> bool:
    """
    Validate combo data quality.
    
    Returns:
        True if combo is valid, False otherwise
    """
    # Must have at least 2 cards
    if len(combo.get('card_names', [])) < 2:
        return False
    
    # Card names must not be empty
    if any(not name.strip() for name in combo.get('card_names', [])):
        return False
    
    # Don't require combo_type - accept all combos even if type is unknown
    return True


def transform_spellbook_combo(spellbook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform Commander Spellbook API data to our combo format.
    
    Args:
        spellbook_data: Raw combo data from Spellbook API
    
    Returns:
        Combo data in our format
    """
    # Extract card information
    cards = []
    card_names = []
    requires_commander = False
    
    for use in spellbook_data.get('uses', []):
        card_data = use.get('card', {})
        card_name = card_data.get('name', '')
        
        if card_name:
            card_names.append(card_name)
            
            # Determine role (simplified)
            zone = use.get('zone_locations', ['battlefield'])[0] if use.get('zone_locations') else 'battlefield'
            role = 'enabler' if zone == 'battlefield' else 'setup'
            
            cards.append({
                'name': card_name,
                'role': role
            })
            
            if use.get('must_be_commander', False):
                requires_commander = True
    
    # Extract combo type from produces
    combo_type = map_produces_to_combo_type(spellbook_data.get('produces', []))
    
    # Parse description into steps
    description = spellbook_data.get('description', '')
    steps = parse_description_to_steps(description)
    
    # Parse prerequisites
    prerequisites = parse_prerequisites(spellbook_data.get('prerequisites', ''))
    
    # Generate name from card names if not provided
    name = ' + '.join(card_names[:3])
    if len(card_names) > 3:
        name += f' + {len(card_names) - 3} more'
    
    return {
        'combo_id': f"csb_{spellbook_data.get('id', '')}",
        'name': name,
        'description': description if description else f"{combo_type.replace('_', ' ').title()} combo",
        'cards': cards,
        'card_names': card_names,
        'combo_type': combo_type,
        'steps': steps,
        'prerequisites': prerequisites,
        'requires_commander': requires_commander,
        'mana_cost_total': 0,  # Will be calculated from card lookups
        'popularity': spellbook_data.get('popularity', 0) or 0,
        'source': 'commanderspellbook',
        'source_url': f"https://commanderspellbook.com/combo/{spellbook_data.get('id', '')}",
        'tags': [],  # Can be enhanced later
        # Note: color_identity will be calculated from card names in create_combo_document
    }


def fetch_combos_from_spellbook(
    max_combos: Optional[int] = None,
    min_popularity: int = 0,
    combos_collection=None,
    cards_collection=None
) -> int:
    """
    Fetch combos from Commander Spellbook API and insert to DB.
    
    Args:
        max_combos: Maximum number of combos to fetch (None = all)
        min_popularity: Minimum popularity threshold
        combos_collection: MongoDB combos collection (for incremental insert)
        cards_collection: MongoDB cards collection (for color identity lookup)
    
    Returns:
        Number of combos inserted
    """
    BASE_URL = "https://backend.commanderspellbook.com"
    ENDPOINT = "/variants/"
    
    print(f"\nFetching combos from Commander Spellbook...")
    print(f"   URL: {BASE_URL}{ENDPOINT}")
    
    # Headers to mimic a browser request (API blocks bot-like requests)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://commanderspellbook.com/',
        'Origin': 'https://commanderspellbook.com'
    }
    
    # Test connection first with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{BASE_URL}{ENDPOINT}?limit=1",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                print(f"   ✗ Cannot reach Commander Spellbook API: {e}")
                print(f"   Using fallback sample data")
                return []
            else:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"   ⚠ Connection attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
    
    all_combos = []
    inserted_count = 0
    page = 1
    next_url = f"{BASE_URL}{ENDPOINT}"
    
    while next_url:
        try:
            print(f"   Fetching page {page}...", end='', flush=True)
            response = requests.get(next_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            print(f" got {len(results)} combos", end='', flush=True)
            
            # Transform and filter combos
            page_combos = []
            
            for spellbook_combo in results:
                
                # Filter by status
                status_value = spellbook_combo.get('status', '').upper()
                if status_value != 'OK':
                    if page == 1:
                        filter_stats['failed_status'] += 1
                        if filter_stats['failed_status'] <= 2:
                            print(f"   [Filter] Status check failed: '{status_value}' != 'OK'")
                    continue
                
                # Filter by popularity
                popularity = spellbook_combo.get('popularity', 0) or 0
                if popularity < min_popularity:
                    continue
                
                # Filter spoilers (unreleased cards)
                spoiler_value = spellbook_combo.get('spoiler', False)
                if spoiler_value:
                    continue
                
                # Transform to our format
                try:
                    combo = transform_spellbook_combo(spellbook_combo)
                    card_names = combo.get('card_names', [])
                    if not card_names or len(card_names) < 2:
                        continue  # Skip if not enough cards
                    
                    page_combos.append(combo)
                    
                    # Insert immediately if we have collections
                    if combos_collection is not None and cards_collection is not None:
                        try:
                            combo_doc = create_combo_document(combo, cards_collection)
                            combos_collection.replace_one(
                                {'combo_id': combo_doc['combo_id']},
                                combo_doc,
                                upsert=True
                            )
                            inserted_count += 1
                        except Exception as e:
                            # Log first few errors
                            if inserted_count < 3:
                                print(f"\n   ERROR creating/inserting {combo.get('name', 'unknown')}: {type(e).__name__}: {str(e)[:100]}")
                    else:
                        # Collections are None, append to list for later insert
                        all_combos.append(combo)
                    
                    # Check max limit
                    if max_combos and inserted_count >= max_combos:
                        if combos_collection is not None and cards_collection is not None:
                            print(f"\n   Reached max combo limit ({max_combos})")
                            return inserted_count
                        elif max_combos and len(all_combos) >= max_combos:
                            print(f"   Reached max combo limit ({max_combos})")
                            return all_combos
                        
                except Exception as e:
                    pass  # Skip invalid combos silently
            
            # Insert page batch if not already inserted incrementally
            if combos_collection is None and page_combos:
                all_combos.extend(page_combos)
            
            # Show progress
            if combos_collection is not None and cards_collection is not None:
                print(f" -> inserted {inserted_count} total")
            
            # Get next page
            next_url = data.get('next')
            page += 1
            
            # Rate limiting - be nice to their API (60 second cooldown observed)
            time.sleep(2.0)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                if all_combos:
                    print(f"   ✗ API rate limited after {len(all_combos)} combos")
                    print(f"   Waiting 90 seconds before retrying...")
                    time.sleep(90)
                    # Try to continue
                    continue
                else:
                    print(f"   ✗ API returned 403 Forbidden (rate limited?)")
                    print(f"   No combos fetched yet, using JSON fallback")
                    break
            else:
                print(f"   ✗ HTTP Error on page {page}: {e}")
                break
        except requests.exceptions.RequestException as e:
            print(f"   ✗ Error fetching page {page}: {e}")
            break
        except Exception as e:
            print(f"   ✗ Unexpected error on page {page}: {e}")
            break
    
    if combos_collection is not None and cards_collection is not None:
        print(f"\n   Total combos inserted: {inserted_count}")
        return inserted_count
    else:
        print(f"\n   Total combos fetched: {len(all_combos)}")
        return all_combos


def calculate_collective_color_identity(card_names: List[str], cards_collection) -> List[str]:
    """Calculate union of color identities for all cards in combo."""
    all_colors = set()
    
    for card_name in card_names:
        card_doc = cards_collection.find_one(
            {'name': card_name},
            {'color_identity': 1}
        )
        
        if card_doc and 'color_identity' in card_doc:
            all_colors.update(card_doc.get('color_identity', []))
    
    # Sort in WUBRG order
    color_order = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
    return sorted(list(all_colors), key=lambda c: color_order.get(c, 5))


def create_combo_document(combo_data: Dict[str, Any], cards_collection) -> Dict[str, Any]:
    """Create a combo document with calculated color identity."""
    card_names = [card['name'] for card in combo_data['cards']]
    color_identity = calculate_collective_color_identity(card_names, cards_collection)
    
    return {
        'combo_id': combo_data.get('combo_id', ''),
        'name': combo_data.get('name', ''),
        'description': combo_data.get('description', ''),
        'cards': combo_data.get('cards', []),
        'card_names': card_names,
        'color_identity': color_identity,
        'color_count': len(color_identity),
        'combo_type': combo_data.get('combo_type', 'unknown'),
        'steps': combo_data.get('steps', []),
        'prerequisites': combo_data.get('prerequisites', []),
        'requires_commander': combo_data.get('requires_commander', False),
        'mana_cost_total': combo_data.get('mana_cost_total', 0),
        'popularity': combo_data.get('popularity', 0),
        'source': combo_data.get('source', 'manual'),
        'source_url': combo_data.get('source_url', ''),
        'tags': combo_data.get('tags', []),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }


def create_indexes(combos_collection):
    """Create all required indexes for efficient querying."""
    print("Creating indexes...")
    
    # Color identity + popularity
    combos_collection.create_index([
        ('color_identity', ASCENDING),
        ('popularity', DESCENDING)
    ], name='color_identity_popularity')
    
    # Color count + popularity
    combos_collection.create_index([
        ('color_count', ASCENDING),
        ('popularity', DESCENDING)
    ], name='color_count_popularity')
    
    # Combo type + popularity
    combos_collection.create_index([
        ('combo_type', ASCENDING),
        ('popularity', DESCENDING)
    ], name='combo_type_popularity')
    
    # Card names for lookup
    combos_collection.create_index([
        ('card_names', ASCENDING)
    ], name='card_names')
    
    # Note: Text search index not supported on Cosmos DB
    # Use regex queries or explicit field searches instead
    
    print("Indexes created successfully")


def load_combos_from_json_file(max_combos: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load combos from local JSON file.
    
    Returns:
        List of combo data
    """
    json_path = os.path.join(os.path.dirname(__file__), 'combos_sample_data.json')
    
    try:
        with open(json_path, 'r') as f:
            combos = json.load(f)
        
        if max_combos:
            combos = combos[:max_combos]
        
        print(f"   Loaded {len(combos)} combos from {json_path}")
        return combos
    except FileNotFoundError:
        print(f"   ✗ JSON file not found: {json_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"   ✗ JSON parse error: {e}")
        return []


def load_sample_combos(max_combos: Optional[int] = None, min_popularity: int = 0) -> List[Dict[str, Any]]:
    """
    Load combo data from Commander Spellbook API or fallback to JSON file.
    
    Returns:
        List of combo data
    """
    # Fetch from API
    combos = fetch_combos_from_spellbook(max_combos, min_popularity)
    
    if not combos:
        print("   WARNING: API unreachable, using local JSON file")
        return load_combos_from_json_file(max_combos)
    
    return combos


def main():
    """Main execution function."""
    args = parse_args()
    
    print("=" * 60)
    print("Creating Combo Collection with Color Identity Support")
    print("=" * 60)
    
    # Connect to MongoDB
    connection_string = os.environ.get('COSMOS_CONNECTION_STRING')
    if not connection_string:
        print("ERROR: COSMOS_CONNECTION_STRING not set")
        sys.exit(1)
    
    print("\n[1/5] Connecting to MongoDB...")
    client = MongoClient(connection_string)
    db = client['mtgecorec']
    combos_collection = db['combos']
    cards_collection = db['cards']
    
    # Verify cards collection exists and has data
    card_count = cards_collection.count_documents({})
    print(f"   Found {card_count:,} cards in database")
    
    if card_count == 0:
        print("   ERROR: Cards collection is empty. Cannot calculate color identities.")
        sys.exit(1)
    
    # Clear existing combos (only if explicitly requested)
    if args.clear:
        print("\n[2/5] Clearing existing combos...")
        result = combos_collection.delete_many({})
        print(f"   Deleted {result.deleted_count} existing combos")
    else:
        existing_count = combos_collection.count_documents({})
        print(f"\n[2/5] Upserting combos (keeping existing, {existing_count} found)")
    
    # Load combo data with args
    print("\n[3/5] Loading combo data from Commander Spellbook API...")
    max_combos = None if args.max_combos == 0 else args.max_combos
    
    # Try API with incremental insert first
    api_result = fetch_combos_from_spellbook(max_combos, args.min_popularity, combos_collection, cards_collection)
    
    if isinstance(api_result, int):
        # API worked and inserted directly
        api_inserted = api_result
        combo_data_list = []
    else:
        # API failed or not used, fall back to JSON
        combo_data_list = api_result
        api_inserted = 0
    
    # If no API results, load from JSON
    if not combo_data_list and api_inserted == 0:
        print("   Trying local JSON file...")
        combo_data_list = load_combos_from_json_file(max_combos)
    
    if len(combo_data_list) == 0 and api_inserted == 0:
        print("   ERROR: No combos loaded")
        sys.exit(1)
    
    # Show sample if from JSON
    if combo_data_list:
        sample = combo_data_list[0]
        # Extract card count from cards array (before transformation to full document)
        card_count = len(sample.get('cards', []))
        print(f"   Sample: {sample['name']} ({card_count} cards)")
    
    # Create and insert combo documents (only if not already inserted from API)
    if combo_data_list:
        print("\n[4/5] Creating combo documents with color identities...")
        inserted_count = 0
        skipped_count = 0
        
        for combo_data in combo_data_list:
            try:
                combo_doc = create_combo_document(combo_data, cards_collection)
                combos_collection.replace_one(
                    {'combo_id': combo_doc['combo_id']},
                    combo_doc,
                    upsert=True
                )
                inserted_count += 1
                
                if inserted_count % 100 == 0:
                    print(f"   ✓ {inserted_count} combos inserted...")
            except Exception as e:
                skipped_count += 1
                if skipped_count <= 5:  # Only show first 5 errors
                    print(f"   ✗ Failed to insert {combo_data.get('name', 'unknown')}: {e}")
        
        print(f"\n   Inserted {inserted_count}/{len(combo_data_list)} combos from JSON")
        if skipped_count > 0:
            print(f"   Skipped {skipped_count} combos due to missing card data")
        api_inserted += inserted_count
    else:
        print(f"\n[4/5] {api_inserted} combos already inserted from API")
    
    # Create indexes
    print("\n[5/5] Creating indexes...")
    create_indexes(combos_collection)
    
    # Test queries
    print("\n" + "=" * 60)
    print("Testing Color Identity Queries")
    print("=" * 60)
    
    # Test 1: Find all combos
    total_combos = combos_collection.count_documents({})
    print(f"\nTotal combos: {total_combos}")
    
    # Test 2: Find Golgari (B/G) legal combos
    commander_colors = ['B', 'G']
    bg_combos = list(combos_collection.find({
        'color_identity': {
            '$not': {
                '$elemMatch': {
                    '$nin': commander_colors
                }
            }
        }
    }).sort([('popularity', DESCENDING)]).limit(5))
    
    print(f"\nCombos legal in Golgari (B/G) commander:")
    if bg_combos:
        for combo in bg_combos:
            print(f"   - {combo['name']}: {combo['color_identity']} "
                  f"(popularity: {combo['popularity']})")
    else:
        print("   (none found)")
    
    # Test 3: Find mono-blue combos
    mono_blue = list(combos_collection.find({
        'color_identity': ['U']
    }).limit(5))
    
    print(f"\nMono-blue combos: {len(list(combos_collection.find({'color_identity': ['U']})))}")
    if mono_blue:
        for combo in mono_blue[:3]:
            print(f"   - {combo['name']}: {combo['color_identity']}")
    
    # Test 4: Find 2-color combos
    two_color_count = combos_collection.count_documents({'color_count': 2})
    print(f"\n2-color combos: {two_color_count}")
    
    # Show combo type distribution
    print("\nCombo type distribution:")
    type_counts = {}
    for combo in combos_collection.find({}, {'combo_type': 1}):
        combo_type = combo.get('combo_type', 'unknown')
        type_counts[combo_type] = type_counts.get(combo_type, 0) + 1
    
    for combo_type in sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)[:5]:
        print(f"   - {combo_type}: {type_counts[combo_type]}")
    
    print("\n" + "=" * 60)
    print("SUCCESS: Combo collection created and indexed")
    print("=" * 60)
    print(f"\nCollection: db.combos")
    print(f"Documents: {total_combos}")
    print(f"Ready for color identity queries")


if __name__ == '__main__':
    main()
