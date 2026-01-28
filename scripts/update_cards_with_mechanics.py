"""
Update MongoDB cards collection with mechanics and archetype data from Phase 1.5.

Reads master_analysis_full.csv and updates each card with:
- detected_mechanics: List of mechanic identifiers
- Archetype boolean flags (is_aristocrats, is_ramp, etc.)
- mechanic_count: Number of detected mechanics
- is_infinite_combo: Boolean flag

Created: January 23, 2026
Phase: Phase 2 Implementation
"""

import sys
import os
import pandas as pd
import logging
from typing import List, Dict, Set

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv('/workspaces/mtgecorec/.env')
except ImportError:
    pass  # dotenv not required if env vars are already set

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_engine.cosmos_driver import get_mongo_client, get_collection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_mechanics_from_cluster_name(cluster_name: str) -> List[str]:
    """
    Extract mechanics from cluster_name field.
    
    Examples:
        "flying_cast_tokens_4" → ['flying', 'cast', 'tokens']
        "sacrifice_aristocrats_3" → ['sacrifice', 'aristocrats']
        "generic_outliers" → ['generic']
    
    Args:
        cluster_name: Cluster name from Phase 1.5 analysis
    
    Returns:
        List of mechanic identifiers
    """
    if not cluster_name or str(cluster_name) == 'nan':
        return []
    
    # Remove cluster suffix and normalize
    clean_name = str(cluster_name).lower()
    clean_name = clean_name.replace('_cluster', '')
    
    # Split on underscores
    parts = clean_name.split('_')
    
    # Filter out numbers and very short strings
    mechanics = []
    for part in parts:
        if part and not part.isdigit() and len(part) > 2:
            mechanics.append(part)
    
    return mechanics


def parse_archetypes(archetypes_active: str) -> Set[str]:
    """
    Parse comma-separated archetypes field.
    
    Examples:
        "aristocrats,tokens" → {'aristocrats', 'tokens'}
        "ramp" → {'ramp'}
        "" → set()
    
    Args:
        archetypes_active: Comma-separated archetype names
    
    Returns:
        Set of archetype names
    """
    if not archetypes_active or str(archetypes_active) == 'nan':
        return set()
    
    # Split on commas and clean
    archetypes = str(archetypes_active).lower().split(',')
    return {arch.strip() for arch in archetypes if arch.strip()}


def create_archetype_flags(archetypes: Set[str]) -> Dict[str, bool]:
    """
    Convert archetype set to boolean flags.
    
    Creates is_* flags for all 13 Phase 1.5 archetypes.
    
    Args:
        archetypes: Set of archetype names (e.g., {'aristocrats', 'tokens'})
    
    Returns:
        Dict with is_* flags (e.g., {'is_aristocrats': True, 'is_ramp': False, ...})
    """
    # All 13 archetypes from Phase 1.5
    all_archetypes = [
        'aristocrats', 'ramp', 'removal', 'card_draw', 'board_wipe',
        'tokens', 'counters', 'graveyard', 'voltron', 'protection',
        'tutor', 'finisher', 'utility'
    ]
    
    # Create boolean flag for each archetype
    flags = {}
    for archetype in all_archetypes:
        flag_name = f'is_{archetype}'
        flags[flag_name] = archetype in archetypes
    
    return flags


def main():
    """Main update process."""
    
    # Load Phase 1.5 data
    csv_path = '/workspaces/mtgecorec/notebooks/master_analysis_full.csv'
    logger.info(f"Loading Phase 1.5 data from {csv_path}")
    
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} cards with mechanics data")
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
        return
    
    # Get MongoDB collection
    logger.info("Connecting to MongoDB cards collection...")
    try:
        client = get_mongo_client()
        db_name = os.environ.get('COSMOS_DB_NAME', 'cards')
        collection_name = 'cards'
        cards_collection = get_collection(client, db_name, collection_name)
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return
    
    # Process each card
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    logger.info("="*70)
    logger.info("STARTING CARD UPDATES")
    logger.info("="*70)
    
    for idx, row in df.iterrows():
        try:
            card_name = row['name']
            
            # Extract mechanics from cluster_name
            mechanics = parse_mechanics_from_cluster_name(row.get('cluster_name'))
            
            # Parse archetypes
            archetypes = parse_archetypes(row.get('archetypes_active'))
            
            # Create archetype boolean flags
            archetype_flags = create_archetype_flags(archetypes)
            
            # Handle is_infinite_combo field
            try:
                is_infinite_combo = bool(row.get('is_infinite_combo', False))
            except:
                is_infinite_combo = False
            
            # Build update document
            update_doc = {
                '$set': {
                    'detected_mechanics': mechanics,
                    'mechanic_count': len(mechanics),
                    'is_infinite_combo': is_infinite_combo,
                    **archetype_flags  # Spread all is_* flags
                }
            }
            
            # Update card in MongoDB
            result = cards_collection.update_one(
                {'name': card_name},
                update_doc
            )
            
            if result.matched_count > 0:
                updated_count += 1
                
                # Log progress every 1000 cards
                if (updated_count % 1000) == 0:
                    logger.info(f"Updated {updated_count} cards...")
            else:
                not_found_count += 1
                # Log first 10 not found (avoid spam)
                if not_found_count <= 10:
                    logger.warning(f"Card not found in database: {card_name}")
        
        except Exception as e:
            error_count += 1
            if error_count <= 5:  # Log first 5 errors
                logger.error(f"Error updating {row.get('name', 'Unknown')}: {e}")
    
    logger.info("="*70)
    logger.info("UPDATE COMPLETE")
    logger.info("="*70)
    logger.info(f"Cards updated: {updated_count}")
    logger.info(f"Cards not found: {not_found_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Total processed: {len(df)}")
    
    # Verify sample cards
    logger.info("\nVerifying sample cards...")
    sample_cards = ['Viscera Seer', 'Sakura-Tribe Elder', 'Doubling Season']
    
    for card_name in sample_cards:
        sample = cards_collection.find_one({'name': card_name})
        if sample:
            logger.info(f"\n✓ {card_name}:")
            logger.info(f"    detected_mechanics: {sample.get('detected_mechanics', [])}")
            logger.info(f"    mechanic_count: {sample.get('mechanic_count', 0)}")
            logger.info(f"    is_aristocrats: {sample.get('is_aristocrats', False)}")
            logger.info(f"    is_ramp: {sample.get('is_ramp', False)}")
            logger.info(f"    is_tokens: {sample.get('is_tokens', False)}")
            logger.info(f"    is_removal: {sample.get('is_removal', False)}")
        else:
            logger.warning(f"✗ {card_name} - not found in database")
    
    logger.info("\n" + "="*70)
    logger.info("✓ Cards collection updated with mechanics and archetypes")
    logger.info("="*70)


if __name__ == "__main__":
    main()
