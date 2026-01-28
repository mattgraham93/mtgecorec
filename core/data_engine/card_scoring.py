"""
card_scoring.py - Commander Card Scoring Engine

Scores all cards for fit with a given commander/strategy using a multi-component
algorithm combining mechanic synergy, archetype alignment, combo potential, 
color identity, mana curve, and card type balance.

Created: January 23, 2026
Phase: Phase 2 Core Feature
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import os
import logging
import json
from dotenv import load_dotenv
from .cosmos_driver import get_mongo_client, get_collection

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class CardScorer:
    """
    Multi-component scoring engine for Commander deck recommendations.
    
    Scores cards 0-100 based on:
    - Mechanic synergy with commander (30%)
    - Archetype fit with strategy (25%)
    - Base card quality/power (15%)
    - Combo potential (15%)
    - Mana curve optimization (10%)
    - Card type balance (5%)
    - Color identity match (multiplier)
    """
    
    def __init__(self, data_path: str = '/workspaces/mtgecorec/notebooks/'):
        """
        Initialize scorer with Phase 1.5 data files.
        
        Args:
            data_path: Path to directory containing CSV data files
        """
        self.data_path = data_path
        logger.info(f"Initializing CardScorer from {data_path}")
        
        # Load Phase 1.5 data files
        self._load_data_files()
        
        # Build lookup tables for performance
        self._build_lookup_tables()
        
        # Default mana curve targets (cards per CMC slot)
        self.default_curve_targets = {
            1: 10, 2: 15, 3: 12, 4: 10, 5: 5, 6: 3, 7: 2, 8: 1
        }
        
        # Default card type targets (Commander deck of 100)
        self.default_type_targets = {
            'creature': 35,
            'instant': 8,
            'sorcery': 8,
            'artifact': 8,
            'enchantment': 8,
            'planeswalker': 2,
            'land': 37
        }
        
        logger.info("CardScorer initialized successfully")
    
    def _load_data_files(self):
        """Load all Phase 1.5 data files."""
        try:
            # Main card database
            self.all_cards = pd.read_csv(
                os.path.join(self.data_path, 'master_analysis_full.csv'),
                dtype={'cmc': float, 'mechanic_count': float}
            )
            logger.info(f"Loaded {len(self.all_cards)} cards from master_analysis_full.csv")
            
            # Mechanic synergy weights
            self.mechanic_weights = pd.read_csv(
                os.path.join(self.data_path, 'mechanic_synergy_weights.csv')
            )
            logger.info(f"Loaded {len(self.mechanic_weights)} mechanic weights")
            
            # Archetype-mechanic alignment
            self.archetype_weights = pd.read_csv(
                os.path.join(self.data_path, 'archetype_mechanic_weights.csv')
            )
            logger.info(f"Loaded {len(self.archetype_weights)} archetype-mechanic mappings")
            
            # Combo card database
            self.combo_cards = pd.read_csv(
                os.path.join(self.data_path, 'combo_cards_list.csv')
            )
            logger.info(f"Loaded {len(self.combo_cards)} combo cards")
            
            # Mechanic co-occurrence matrix
            self.cooccurrence_matrix = pd.read_csv(
                os.path.join(self.data_path, 'mechanic_cooccurrence_matrix.csv'),
                index_col=0
            )
            logger.info(f"Loaded mechanic co-occurrence matrix")
            
            # Load color identity from Scryfall data
            self._load_scryfall_color_data()
            
        except FileNotFoundError as e:
            logger.error(f"Data file not found: {e}")
            raise
    
    def _load_scryfall_color_data(self):
        """
        Load color_identity from CosmosDB cards collection.
        
        CRITICAL: Uses MongoDB/CosmosDB cards collection which has color_identity
        field from original Scryfall data import. This is the authoritative source.
        
        Builds lookup table: card_name → Set[str] of color symbols
        """
        try:
            logger.info("Loading color identity from CosmosDB cards collection...")
            
            # Get connection and collection
            client = get_mongo_client()
            # Note: parameter order is (client, database_name, collection_name)
            # Default database is 'cards' if COSMOS_DB_NAME env var not set
            db_name = os.environ.get('COSMOS_DB_NAME', 'cards')
            collection_name = 'cards'  # Collection name where card data is stored
            
            cards_collection = get_collection(client, db_name, collection_name)
            
            # Test connection first
            count = cards_collection.count_documents({}, limit=1)
            logger.debug(f"CosmosDB cards collection accessible (contains data: {count > 0})")
            
            # Query just name and color_identity fields (efficient)
            projection = {'name': 1, 'color_identity': 1}
            cards_cursor = cards_collection.find({}, projection)
            
            # Build lookup: card_name → color_identity (Set[str])
            self.color_identity_lookup = {}
            card_count = 0
            
            for card in cards_cursor:
                name = card.get('name')
                color_id = card.get('color_identity', [])  # MongoDB has this from Scryfall: ['B', 'G']
                if name:
                    # Store with normalized (trimmed) name to handle whitespace differences
                    normalized_name = name.strip()
                    self.color_identity_lookup[normalized_name] = set(color_id)
                    card_count += 1
            
            logger.info(f"Loaded color identity for {card_count} cards from CosmosDB")
            
            # Also load full card data from CosmosDB to replace/supplement CSV
            self._load_all_cards_from_cosmosdb()
            
        except Exception as e:
            logger.warning(f"Could not load color identity from CosmosDB: {e}")
            logger.warning("Will gracefully degrade - all cards treated as colorless")
            self.color_identity_lookup = {}
    
    def _load_all_cards_from_cosmosdb(self):
        """
        Load full card data from CosmosDB as DataFrame.
        
        Includes:
        - Basic fields (name, type_line, oracle_text, cmc, rarity)
        - Mechanics data (detected_mechanics, mechanic_count, is_infinite_combo)
        - Archetype flags (is_aristocrats, is_ramp, etc.)
        
        This provides complete card dataset (35k+ cards) with Phase 1.5 data.
        """
        try:
            logger.info("Loading all card data from CosmosDB...")
            
            client = get_mongo_client()
            db_name = os.environ.get('COSMOS_DB_NAME', 'cards')
            collection_name = 'cards'
            
            cards_collection = get_collection(client, db_name, collection_name)
            
            # Load all cards with key fields including mechanics and archetypes
            cursor = cards_collection.find({}, {
                'name': 1,
                'color_identity': 1,
                'type_line': 1,
                'oracle_text': 1,
                'cmc': 1,
                'set': 1,
                'rarity': 1,
                # Phase 1.5 mechanics and archetypes
                'detected_mechanics': 1,
                'mechanic_count': 1,
                'is_infinite_combo': 1,
                # Archetype boolean flags (13 total)
                'is_aristocrats': 1,
                'is_ramp': 1,
                'is_removal': 1,
                'is_card_draw': 1,
                'is_board_wipe': 1,
                'is_tokens': 1,
                'is_counters': 1,
                'is_graveyard': 1,
                'is_voltron': 1,
                'is_protection': 1,
                'is_tutor': 1,
                'is_finisher': 1,
                'is_utility': 1,
            })
            
            # Convert to list of dicts, then DataFrame
            cards_list = list(cursor)
            
            if cards_list:
                df = pd.DataFrame(cards_list)
                
                # Normalize name (trim whitespace)
                df['name'] = df['name'].str.strip()
                
                # Fill missing values appropriately
                df['cmc'] = df['cmc'].fillna(0).astype(float)
                df['type_line'] = df['type_line'].fillna('')
                df['oracle_text'] = df['oracle_text'].fillna('')
                df['rarity'] = df['rarity'].fillna('common')
                
                # Fill mechanics/archetype fields with defaults
                df['detected_mechanics'] = df['detected_mechanics'].fillna('').apply(
                    lambda x: list(x) if isinstance(x, list) else []
                )
                df['mechanic_count'] = df['mechanic_count'].fillna(0).astype(int)
                df['is_infinite_combo'] = df['is_infinite_combo'].fillna(False).astype(bool)
                
                # Fill archetype flags with False
                archetype_flags = [
                    'is_aristocrats', 'is_ramp', 'is_removal', 'is_card_draw',
                    'is_board_wipe', 'is_tokens', 'is_counters', 'is_graveyard',
                    'is_voltron', 'is_protection', 'is_tutor', 'is_finisher', 'is_utility'
                ]
                for flag in archetype_flags:
                    if flag in df.columns:
                        df[flag] = df[flag].fillna(False).astype(bool)
                    else:
                        df[flag] = False
                
                # Replace CSV data with CosmosDB data
                self.all_cards = df
                logger.info(f"Loaded {len(df)} cards from CosmosDB (replacing CSV data)")
                
                # Log mechanic coverage
                cards_with_mechanics = len(df[df['mechanic_count'] > 0])
                logger.info(f"  - {cards_with_mechanics} cards with detected mechanics")
                
                # Log archetype coverage
                cards_with_archetypes = len(df[[col for col in archetype_flags if col in df.columns]].any(axis=1))
                logger.info(f"  - {cards_with_archetypes} cards with archetype assignments")
            else:
                logger.warning("No cards found in CosmosDB, keeping CSV data")
                
        except Exception as e:
            logger.warning(f"Could not load full card data from CosmosDB: {e}")
            logger.warning("Keeping existing CSV data")
    
    def _build_lookup_tables(self):
        """Build lookup dictionaries for performance."""
        # Map mechanic names to their weights
        self.mechanic_weight_lookup = {}
        for _, row in self.mechanic_weights.iterrows():
            mechanic_id = row.get('mechanic_id') or row.get('mechanic_name')
            weight = row.get('composite_weight', 50)
            self.mechanic_weight_lookup[mechanic_id] = weight
        
        # Map card names to full card data (avoid repeated lookups)
        self.card_name_lookup = {}
        for _, row in self.all_cards.iterrows():
            name = row['name']
            self.card_name_lookup[name] = row.to_dict()
        
        # Map combo card names to combo status
        self.combo_card_set = set(self.combo_cards['name'].unique())
        self.infinite_combo_set = set(
            self.combo_cards[self.combo_cards['is_infinite_combo'] == True]['name'].unique()
        )
        
        logger.info("Lookup tables built")
    
    def extract_color_identity(self, card: Dict[str, Any]) -> Set[str]:
        """
        Extract color identity from CosmosDB lookup.
        
        Uses the color_identity data loaded from CosmosDB cards collection.
        This is authoritative and includes colors from mana cost AND rules text.
        
        Args:
            card: Card data dict with 'name' field
        
        Returns:
            Set of MTG color symbols {'W', 'U', 'B', 'R', 'G'}
            Empty set if card not found (colorless)
        """
        card_name = card.get('name', '')
        
        # Try exact lookup first
        if card_name in self.color_identity_lookup:
            return self.color_identity_lookup[card_name]
        
        # Try case-insensitive, trimmed lookup (addresses whitespace/case differences between sources)
        card_name_normalized = card_name.lower().strip()
        for lookup_key, color_set in self.color_identity_lookup.items():
            if lookup_key.lower().strip() == card_name_normalized:
                return color_set
        
        # Fallback to empty set (colorless)
        return set()
    
    def score_card(self,
                   card: Dict[str, Any],
                   commander: Dict[str, Any],
                   current_deck: List[Dict[str, Any]] = None) -> Tuple[float, Dict[str, float]]:
        """
        Score a single card for commander fit.
        
        Args:
            card: Card data dict with keys: name, cmc, type_line, oracle_text, 
                  color_identity, mechanic_count, is_infinite_combo, etc.
            commander: Commander card data dict
            current_deck: List of card dicts already in deck (for curve context)
        
        Returns:
            Tuple of (total_score: float, components: Dict[str, float])
            - total_score: 0-100
            - components: dict with individual component scores and multiplier
        """
        if current_deck is None:
            current_deck = []
        
        # Extract card properties, with safe defaults
        card_name = card.get('name', '')
        card_cmc = float(card.get('cmc', 0))
        card_type = str(card.get('type_line', '')).lower()
        card_oracle = str(card.get('oracle_text', '')).lower()
        
        # CRITICAL: Extract actual color identity from Scryfall data
        card_colors = self.extract_color_identity(card)
        commander_colors = self.extract_color_identity(commander)
        
        # Calculate component scores
        base_power = self._calculate_base_power(card)
        mechanic_synergy = self._calculate_mechanic_synergy(card, commander, current_deck)
        archetype_fit = self._calculate_archetype_fit(card, commander)
        combo_bonus = self._calculate_combo_bonus(card, current_deck)
        curve_fit = self._calculate_curve_fit(card_cmc, current_deck)
        type_balance = self._calculate_type_balance(card_type, current_deck)
        color_multiplier = self._calculate_color_multiplier(card_colors, commander_colors)
        
        # Combine with weights (component weights from spec)
        total_score = (
            base_power * 0.15 +
            mechanic_synergy * 0.30 +
            archetype_fit * 0.25 +
            combo_bonus * 0.15 +
            curve_fit * 0.10 +
            type_balance * 0.05
        ) * color_multiplier
        
        # Clamp to 0-100
        total_score = max(0, min(100, total_score))
        
        # Component breakdown for transparency
        components = {
            'base_power': base_power,
            'mechanic_synergy': mechanic_synergy,
            'archetype_fit': archetype_fit,
            'combo_bonus': combo_bonus,
            'curve_fit': curve_fit,
            'type_balance': type_balance,
            'color_multiplier': color_multiplier,
            'total_score': total_score
        }
        
        return total_score, components
    
    def score_all_cards(self,
                       commander: Dict[str, Any],
                       current_deck: List[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Score all legal cards for this commander.
        
        CRITICAL IMPROVEMENTS:
        1. Deduplicates cards by name (keeps first occurrence)
        2. Filters out illegal cards (color_multiplier = 0.0)
        3. Logs deduplication and filtering impact
        
        Args:
            commander: Commander card data
            current_deck: Cards already in deck
        
        Returns:
            DataFrame sorted by total_score (descending) with all components
        """
        if current_deck is None:
            current_deck = []
        
        logger.info(f"Scoring all cards for {commander.get('name', 'Unknown')}")
        
        # STEP 1: Deduplicate cards by name (keep first occurrence)
        unique_cards = self.all_cards.drop_duplicates(subset=['name'], keep='first')
        logger.info(f"After deduplication: {len(unique_cards)} unique cards (from {len(self.all_cards)} total)")
        
        results = []
        illegal_count = 0
        
        for idx, (_, card_row) in enumerate(unique_cards.iterrows()):
            card = card_row.to_dict()
            
            score, components = self.score_card(card, commander, current_deck)
            
            # STEP 2: Filter out illegal cards (color_multiplier = 0.0)
            if components['color_multiplier'] == 0.0:
                illegal_count += 1
                continue  # Skip illegal cards entirely
            
            results.append({
                'card_name': card.get('name', ''),
                'total_score': score,
                'base_power': components['base_power'],
                'mechanic_synergy': components['mechanic_synergy'],
                'archetype_fit': components['archetype_fit'],
                'combo_bonus': components['combo_bonus'],
                'curve_fit': components['curve_fit'],
                'type_balance': components['type_balance'],
                'color_multiplier': components['color_multiplier'],
            })
            
            if (idx + 1) % 10000 == 0:
                logger.debug(f"Scored {idx + 1} cards...")
        
        logger.info(f"Color identity enforcement: {illegal_count} illegal cards filtered out")
        logger.info(f"Scoring complete: {len(results)} legal cards scored")
        
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('total_score', ascending=False)
        
        return df_results
    
    def score_all_cards_parallel(self,
                                 commander: Dict[str, Any],
                                 current_deck: List[Dict[str, Any]] = None,
                                 n_jobs: int = -1) -> pd.DataFrame:
        """
        Score all legal cards for this commander using parallel processing.
        
        This is a parallelized version of score_all_cards() that uses
        multiprocessing to score cards across multiple CPU cores.
        Expected speedup: 4-8x faster on typical machines (4-8 cores).
        
        Args:
            commander: Commander card data
            current_deck: Cards already in deck
            n_jobs: Number of parallel jobs (-1 = use all CPU cores)
        
        Returns:
            DataFrame sorted by total_score (descending) with all components
        """
        from multiprocessing import Pool, cpu_count
        import time
        
        if current_deck is None:
            current_deck = []
        
        # Determine number of workers
        if n_jobs == -1:
            n_jobs = cpu_count()
        
        commander_name = commander.get('name', 'Unknown')
        logger.info(f"Scoring all cards for {commander_name} using {n_jobs} parallel workers")
        
        start_time = time.time()
        
        # STEP 1: Deduplicate cards by name (keep first occurrence)
        unique_cards = self.all_cards.drop_duplicates(subset=['name'], keep='first')
        logger.info(f"After deduplication: {len(unique_cards)} unique cards (from {len(self.all_cards)} total)")
        
        # Extract commander colors once (used by all workers)
        commander_colors = self.extract_color_identity(commander)
        
        # Split cards into chunks for each worker
        cards_list = unique_cards.to_dict('records')
        chunk_size = max(1, len(cards_list) // n_jobs + 1)
        chunks = [cards_list[i:i + chunk_size] for i in range(0, len(cards_list), chunk_size)]
        
        logger.info(f"Split into {len(chunks)} chunks of ~{chunk_size} cards each")
        
        # Create worker arguments
        worker_args = [
            (chunk, commander, commander_colors, current_deck, self.data_path)
            for chunk in chunks
        ]
        
        # Score chunks in parallel
        with Pool(processes=n_jobs) as pool:
            chunk_results = pool.starmap(_score_cards_chunk, worker_args)
        
        # Combine results from all chunks
        all_results = []
        illegal_count = 0
        
        for chunk_result in chunk_results:
            for result in chunk_result:
                if result is not None:
                    all_results.append(result)
                else:
                    illegal_count += 1
        
        logger.info(f"Color identity enforcement: {illegal_count} illegal cards filtered out")
        logger.info(f"Parallel scoring complete: {len(all_results)} legal cards scored")
        
        # Convert to DataFrame and sort
        df_results = pd.DataFrame(all_results)
        df_results = df_results.sort_values('total_score', ascending=False).reset_index(drop=True)
        
        elapsed = time.time() - start_time
        cards_per_sec = len(all_results) / elapsed if elapsed > 0 else 0
        logger.info(f"Time: {elapsed:.2f}s ({cards_per_sec:.0f} cards/sec)")
        
        return df_results
    
    def get_top_recommendations(self,
                               commander: Dict[str, Any],
                               current_deck: List[Dict[str, Any]] = None,
                               n: int = 50) -> pd.DataFrame:
        """
        Get top N recommended cards for commander.
        
        Args:
            commander: Commander card data
            current_deck: Cards already in deck
            n: Number of top recommendations to return
        
        Returns:
            Top N cards with scores
        """
        all_scores = self.score_all_cards(commander, current_deck)
        return all_scores.head(n)
    
    def test_mechanic_extraction(self):
        """
        Test mechanic extraction on known commanders.
        Useful for debugging synergy calculation.
        """
        test_commanders = [
            'Meren of Clan Nel Toth',
            'Atraxa, Praetors\' Voice', 
            'The Gitrog Monster'
        ]
        
        print("\n" + "="*70)
        print("MECHANIC EXTRACTION TEST")
        print("="*70)
        
        for commander_name in test_commanders:
            card_matches = self.all_cards[self.all_cards['name'] == commander_name]
            if len(card_matches) > 0:
                card = card_matches.iloc[0].to_dict()
                mechanics_count = float(card.get('mechanic_count', 0))
                print(f"\n{commander_name}:")
                print(f"  Mechanic count: {mechanics_count}")
                print(f"  Cluster: {card.get('cluster_name', 'N/A')}")
                print(f"  Archetypes: {card.get('archetypes_active', 'N/A')}")
            else:
                print(f"\n{commander_name}: NOT FOUND in database")
        
        print("\n" + "="*70 + "\n")
    
    def test_color_identity_enforcement(self):
        """
        Test color identity strict enforcement.
        Verify illegal cards get multiplier = 0.0
        """
        print("\n" + "="*70)
        print("COLOR IDENTITY STRICT ENFORCEMENT TEST")
        print("="*70)
        
        # Test commander: Meren (Black/Green)
        meren_matches = self.all_cards[self.all_cards['name'] == 'Meren of Clan Nel Toth']
        if len(meren_matches) == 0:
            print("ERROR: Meren not found in database")
            return
        
        meren = meren_matches.iloc[0].to_dict()
        meren_colors = self.extract_color_identity(meren)
        print(f"\nMeren color identity: {meren_colors}")
        print(f"Legal colors: Black (B), Green (G), Colorless")
        
        # Test specific cards
        test_cards = [
            ('Lightning Bolt', 'ILLEGAL - Red not in Meren'),
            ('Counterspell', 'ILLEGAL - Blue not in Meren'),
            ('Sol Ring', 'LEGAL - Colorless'),
            ('Llanowar Elves', 'LEGAL - Green in Meren'),
        ]
        
        print("\nTesting color identity enforcement:")
        all_passed = True
        
        for card_name, expected_result in test_cards:
            card_matches = self.all_cards[self.all_cards['name'].str.contains(card_name, case=False, na=False)]
            
            if len(card_matches) > 0:
                card = card_matches.iloc[0].to_dict()
                card_colors = self.extract_color_identity(card)
                multiplier = self._calculate_color_multiplier(card_colors, meren_colors)
                
                # Check if result matches expectation
                is_legal = multiplier > 0.0
                expected_legal = 'LEGAL' in expected_result
                
                status = "✓ PASS" if (is_legal == expected_legal) else "✗ FAIL"
                if is_legal != expected_legal:
                    all_passed = False
                
                print(f"  {status} {card_name:30s} colors={str(card_colors or set()):20s} multiplier={multiplier:.2f}")
            else:
                print(f"  ⚠ SKIP {card_name:30s} (not in database)")
        
        print("\n" + "="*70)
        if all_passed:
            print("✓✓✓ COLOR IDENTITY TEST PASSED ✓✓✓")
        else:
            print("✗✗✗ COLOR IDENTITY TEST FAILED ✗✗✗")
        print("="*70 + "\n")
    
    # ============================================================================
    # Component Scoring Methods
    # ============================================================================
    
    def _calculate_base_power(self, card: Dict[str, Any]) -> float:
        """
        Base power from rarity, popularity, and complexity (0-100).
        
        Represents inherent card quality independent of synergy.
        """
        rarity = str(card.get('rarity', 'common')).lower()
        mechanic_count = float(card.get('mechanic_count', 1))
        
        # Rarity score mapping
        rarity_scores = {
            'common': 30,
            'uncommon': 50,
            'rare': 70,
            'mythic': 90
        }
        rarity_score = rarity_scores.get(rarity, 50)
        
        # Mechanic complexity bonus (more mechanics = more value)
        complexity_score = min(mechanic_count * 5, 30)
        
        # Combine: 60% rarity, 40% complexity
        base_power = (rarity_score * 0.6) + (complexity_score * 0.4)
        
        return min(base_power, 100)
    
    def _calculate_mechanic_synergy(self,
                                   card: Dict[str, Any],
                                   commander: Dict[str, Any],
                                   deck: List[Dict[str, Any]]) -> float:
        """
        Mechanic overlap with commander and deck (0-100).
        
        Uses Phase 1.5 mechanic detection from database (detected_mechanics array).
        Calculates actual overlap between card mechanics and commander mechanics.
        """
        card_name = card.get('name', 'Unknown')
        commander_name = commander.get('name', 'Unknown')
        
        # Extract mechanics from database (detected_mechanics array)
        card_mechanics = set(card.get('detected_mechanics', []))
        commander_mechanics = set(commander.get('detected_mechanics', []))
        
        # DIAGNOSTIC: Log extraction details
        logger.debug(f"\n=== SYNERGY DEBUG: {card_name} vs {commander_name} ===")
        logger.debug(f"Card mechanics: {card_mechanics}")
        logger.debug(f"Commander mechanics: {commander_mechanics}")
        
        # Calculate mechanic overlap
        if not commander_mechanics:
            # No commander mechanics = neutral base score
            base_synergy = 50.0
        else:
            # Calculate overlap as percentage of commander's mechanics
            overlap = card_mechanics & commander_mechanics
            overlap_score = (len(overlap) / len(commander_mechanics)) * 100
            base_synergy = overlap_score
        
        logger.debug(f"Mechanic overlap score: {base_synergy:.1f}")
        
        # Bonus: card has ALL of commander's mechanics (perfect match)
        if commander_mechanics and commander_mechanics.issubset(card_mechanics):
            base_synergy = min(base_synergy + 15, 100)
            logger.debug(f"Perfect mechanic match bonus applied: {base_synergy:.1f}")
        
        # Deck context: boost if synergizes with multiple deck cards
        if deck:
            synergistic_cards = 0
            for deck_card in deck:
                deck_card_mechanics = set(deck_card.get('detected_mechanics', []))
                if card_mechanics & deck_card_mechanics:  # Any overlap
                    synergistic_cards += 1
            
            if synergistic_cards > 0:
                deck_synergy_bonus = min((synergistic_cards / max(len(deck), 1)) * 20, 20)
                base_synergy = min(base_synergy + deck_synergy_bonus, 100)
                logger.debug(f"Deck synergy bonus ({synergistic_cards} cards): {base_synergy:.1f}")
        
        final_synergy = min(base_synergy, 100)
        logger.debug(f"Final synergy: {final_synergy:.1f}")
        
        return final_synergy
    
    def _calculate_archetype_fit(self,
                                card: Dict[str, Any],
                                commander: Dict[str, Any]) -> float:
        """
        Alignment with commander's strategic archetype (0-100).
        
        Uses archetype boolean flags from database:
        is_aristocrats, is_ramp, is_removal, is_card_draw, is_board_wipe,
        is_tokens, is_counters, is_graveyard, is_voltron, is_protection,
        is_tutor, is_finisher, is_utility
        """
        # All 13 archetype flags from Phase 1.5
        archetype_flags = [
            'is_aristocrats', 'is_ramp', 'is_removal', 'is_card_draw',
            'is_board_wipe', 'is_tokens', 'is_counters', 'is_graveyard',
            'is_voltron', 'is_protection', 'is_tutor', 'is_finisher', 'is_utility'
        ]
        
        # Get active archetypes for card and commander
        card_archetypes = [flag for flag in archetype_flags if card.get(flag) == True]
        commander_archetypes = [flag for flag in archetype_flags if commander.get(flag) == True]
        
        # If commander has no archetype data, return neutral
        if not commander_archetypes:
            return 50.0
        
        # If card has no archetype data, return lower score
        if not card_archetypes:
            return 30.0
        
        # Calculate archetype overlap
        matching_archetypes = set(card_archetypes) & set(commander_archetypes)
        
        if not matching_archetypes:
            # No matching archetypes - card doesn't fit strategy
            return 0.0
        
        # Score based on match ratio (matches / commander's archetypes)
        match_score = (len(matching_archetypes) / len(commander_archetypes)) * 100
        
        return min(match_score, 100)
    
    def _calculate_combo_bonus(self,
                              card: Dict[str, Any],
                              deck: List[Dict[str, Any]]) -> float:
        """
        Bonus for cards that enable or complete infinite combos (0-100).
        """
        card_name = card.get('name', '')
        is_infinite = card.get('is_infinite_combo', False)
        
        combo_score = 0
        
        # Is this card a known combo piece?
        if card_name in self.infinite_combo_set:
            combo_score += 30
        elif card_name in self.combo_card_set:
            combo_score += 15
        
        # Check for combo completion with deck cards
        if deck:
            deck_names = {c.get('name', '') for c in deck}
            # Count how many combo cards are already in deck
            overlapping_combos = len(deck_names & self.combo_card_set)
            if overlapping_combos > 0:
                # Each overlapping combo piece adds potential
                combo_score += min(overlapping_combos * 15, 35)
        
        return min(combo_score, 100)
    
    def _calculate_curve_fit(self,
                            card_cmc: float,
                            deck: List[Dict[str, Any]]) -> float:
        """
        Mana curve optimization (0-100).
        
        Higher score if this CMC slot needs more cards.
        """
        card_cmc = int(card_cmc)
        
        # Count cards in deck by CMC
        current_curve = defaultdict(int)
        for card in deck:
            cmc = int(float(card.get('cmc', 0)))
            current_curve[cmc] += 1
        
        # Use default curve targets
        target_count = self.default_curve_targets.get(card_cmc, 1)
        current_count = current_curve.get(card_cmc, 0)
        
        # Score based on deficit/surplus
        if current_count < target_count:
            # Deficit - we want this CMC
            deficit = target_count - current_count
            curve_score = min(50 + (deficit * 10), 100)
        elif current_count == target_count:
            # At target
            curve_score = 50
        else:
            # Surplus - we have too many at this CMC
            surplus = current_count - target_count
            curve_score = max(50 - (surplus * 10), 0)
        
        return curve_score
    
    def _calculate_type_balance(self,
                               card_type: str,
                               deck: List[Dict[str, Any]]) -> float:
        """
        Card type distribution balance (0-100).
        
        Maintains healthy creature/spell/artifact ratio.
        """
        card_type = card_type.lower()
        
        # Determine card type category
        type_category = 'synergy'  # default
        if 'creature' in card_type:
            type_category = 'creature'
        elif 'instant' in card_type:
            type_category = 'instant'
        elif 'sorcery' in card_type:
            type_category = 'sorcery'
        elif 'artifact' in card_type:
            type_category = 'artifact'
        elif 'enchantment' in card_type:
            type_category = 'enchantment'
        elif 'land' in card_type:
            type_category = 'land'
        elif 'planeswalker' in card_type:
            type_category = 'planeswalker'
        
        # Count cards in deck by type
        current_types = defaultdict(int)
        for card in deck:
            c_type = str(card.get('type_line', '')).lower()
            
            if 'creature' in c_type:
                current_types['creature'] += 1
            elif 'instant' in c_type:
                current_types['instant'] += 1
            elif 'sorcery' in c_type:
                current_types['sorcery'] += 1
            elif 'artifact' in c_type:
                current_types['artifact'] += 1
            elif 'enchantment' in c_type:
                current_types['enchantment'] += 1
            elif 'land' in c_type:
                current_types['land'] += 1
            elif 'planeswalker' in c_type:
                current_types['planeswalker'] += 1
        
        total_cards = len(deck) if deck else 1
        
        # Get target percentage for this type
        target_count = self.default_type_targets.get(type_category, 5)
        target_pct = (target_count / 100) * 100 if total_cards == 0 else target_count
        
        current_count = current_types.get(type_category, 0)
        current_pct = (current_count / total_cards * 100) if total_cards > 0 else 0
        
        # Score based on deficit/surplus
        diff = target_pct - current_pct
        
        if diff > 0:
            # Under target - boost
            balance_score = min(50 + (diff * 2), 100)
        else:
            # Over target - penalize
            balance_score = max(50 + (diff * 2), 0)
        
        return balance_score
    
    def _calculate_color_multiplier(self,
                                   card_colors: Set[str],
                                   commander_colors: Set[str]) -> float:
        """
        Strict color identity enforcement (0.0 - 1.0).
        
        Commander format rule: Card colors must be SUBSET of commander colors.
        Scryfall color_identity field is authoritative (includes mana cost + rules text).
        
        Args:
            card_colors: Set of card's color identity symbols (e.g., {'B', 'G'})
            commander_colors: Set of commander's color identity symbols
        
        Returns:
            0.0 = ILLEGAL (card has colors not in commander colors) - HARD VETO
            1.0 = LEGAL (card's colors are subset of commander's colors)
        
        Examples:
            Commander: {B, G} (Golgari)
            Card {R} → 0.0 (RED NOT IN COMMANDER COLORS - ILLEGAL)
            Card {B} → 1.0 (legal, matches commander)
            Card {B, G} → 1.0 (perfect match)
            Card {} (colorless) → 1.0 (colorless always legal)
        """
        # Clean up color sets (remove empty strings, whitespace)
        card_colors = {c.strip() for c in card_colors if c and str(c).strip()}
        commander_colors = {c.strip() for c in commander_colors if c and str(c).strip()}
        
        # CRITICAL: Strict color identity check (Commander format rule)
        # If card has ANY color not in commander's identity → ILLEGAL
        if not card_colors.issubset(commander_colors):
            return 0.0  # HARD VETO - Card is illegal
        
        # Card is legal - return 1.0
        # (Both colorless cards and all other legal combinations return 1.0)
        return 1.0


# Example usage / testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Initialize scorer
    scorer = CardScorer()
    
    # Example: Find Meren in database
    meren = scorer.card_name_lookup.get('Meren of Clan Nel Toth')
    if meren:
        print(f"Found commander: {meren.get('name')}")
        
        # Score all cards for Meren
        top_cards = scorer.get_top_recommendations(meren, n=10)
        print("\nTop 10 recommendations for Meren:")
        print(top_cards[['card_name', 'total_score', 'mechanic_synergy', 'archetype_fit', 'combo_bonus']])
    else:
        print("Meren not found in card database")

# ============================================================================
# Module-level worker function for multiprocessing
# ============================================================================
# CRITICAL: This function MUST be at module level (not inside the class) 
# because Python's multiprocessing uses pickle for serialization.

def _score_cards_chunk(
    cards_chunk: List[Dict[str, Any]],
    commander: Dict[str, Any],
    commander_colors: Set[str],
    current_deck: List[Dict[str, Any]],
    data_path: str
) -> List[Optional[Dict[str, Any]]]:
    """
    Score a chunk of cards (worker function for multiprocessing).
    
    Creates a temporary CardScorer instance for this worker process.
    Each process needs its own instance due to multiprocessing constraints.
    
    Args:
        cards_chunk: List of card dictionaries to score
        commander: Commander card dictionary
        commander_colors: Pre-extracted commander color identity (Set of strings)
        current_deck: List of cards already in deck
        data_path: Path to data files for CardScorer initialization
    
    Returns:
        List of score result dictionaries (or None for illegal/duplicate cards)
    """
    # Create a temporary CardScorer instance for this worker
    scorer = CardScorer(data_path=data_path)
    
    results = []
    seen_names = set()
    
    for card in cards_chunk:
        card_name = card.get('name', '').strip()
        
        # Skip duplicates (same card, different printings)
        if card_name in seen_names:
            results.append(None)
            continue
        
        seen_names.add(card_name)
        
        # Skip cards already in deck
        if any(deck_card.get('name', '').strip() == card_name for deck_card in current_deck):
            results.append(None)
            continue
        
        # Extract card colors
        card_colors = scorer.extract_color_identity(card)
        
        # Calculate color multiplier (0.0 for illegal cards)
        color_multiplier = scorer._calculate_color_multiplier(card_colors, commander_colors)
        
        # Skip illegal cards early (don't waste time scoring them)
        if color_multiplier == 0.0:
            results.append(None)
            continue
        
        # Calculate all scoring components
        base_power = scorer._calculate_base_power(card)
        mechanic_synergy = scorer._calculate_mechanic_synergy(card, commander, current_deck)
        archetype_fit = scorer._calculate_archetype_fit(card, commander)
        combo_bonus = scorer._calculate_combo_bonus(card, current_deck)
        curve_fit = scorer._calculate_curve_fit(card.get('cmc', 0), current_deck)
        type_balance = scorer._calculate_type_balance(card.get('type_line', ''), current_deck)
        
        # Calculate weighted total score
        total_score = (
            base_power * 0.15 +
            mechanic_synergy * 0.30 +
            archetype_fit * 0.25 +
            combo_bonus * 0.15 +
            curve_fit * 0.10 +
            type_balance * 0.05
        ) * color_multiplier
        
        # Clamp to 0-100
        total_score = max(0, min(100, total_score))
        
        results.append({
            'card_name': card_name,
            'total_score': total_score,
            'base_power': base_power,
            'mechanic_synergy': mechanic_synergy,
            'archetype_fit': archetype_fit,
            'combo_bonus': combo_bonus,
            'curve_fit': curve_fit,
            'type_balance': type_balance,
            'color_multiplier': color_multiplier
        })
    
    return results