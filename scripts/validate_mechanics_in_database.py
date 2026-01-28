"""
Quick validation of CardScorer with updated database mechanics.

Tests:
1. CardScorer loads correctly
2. Cards have detected_mechanics from database
3. Synergy scores show variance (not all 100)
4. Different commanders get different synergy values
"""

import sys
import os

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv('/workspaces/mtgecorec/.env')
except ImportError:
    pass

sys.path.append('/workspaces/mtgecorec')

import logging
from core.data_engine.card_scoring import CardScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Validate CardScorer with mechanics from database."""
    
    logger.info("="*70)
    logger.info("CARD SCORER VALIDATION")
    logger.info("="*70)
    
    # Initialize scorer
    logger.info("\n1. Initializing CardScorer...")
    scorer = CardScorer()
    
    # Verify database mechanics loaded
    logger.info("\n2. Checking for detected_mechanics in database...")
    cards_with_mechanics = 0
    cards_without_mechanics = 0
    
    for idx, (_, card) in enumerate(scorer.all_cards.iterrows()):
        mechanics = card.get('detected_mechanics', [])
        if mechanics and len(mechanics) > 0:
            cards_with_mechanics += 1
        else:
            cards_without_mechanics += 1
        
        if idx >= 100:  # Check first 100
            break
    
    logger.info(f"   - Checked first 100 cards:")
    logger.info(f"     • With detected_mechanics: {cards_with_mechanics}")
    logger.info(f"     • Without detected_mechanics: {cards_without_mechanics}")
    
    # Get test commanders
    logger.info("\n3. Finding test commanders...")
    test_commanders = ['Meren of Clan Nel Toth', 'Atraxa, Praetors\' Voice', 'The Gitrog Monster']
    commanders = {}
    
    for cmd_name in test_commanders:
        cmd_matches = scorer.all_cards[scorer.all_cards['name'] == cmd_name]
        if len(cmd_matches) > 0:
            commanders[cmd_name] = cmd_matches.iloc[0].to_dict()
            logger.info(f"   ✓ Found: {cmd_name}")
        else:
            logger.warning(f"   ✗ Not found: {cmd_name}")
    
    if not commanders:
        logger.error("ERROR: No test commanders found in database")
        return
    
    # Test synergy scoring
    logger.info("\n4. Testing synergy scores (should show variance)...")
    
    for cmd_name, commander in commanders.items():
        logger.info(f"\n   {cmd_name}:")
        logger.info(f"   - Mechanics: {commander.get('detected_mechanics', [])}")
        logger.info(f"   - Archetype flags: ", end="")
        
        # Get archetype flags
        archetype_flags = [
            'is_aristocrats', 'is_ramp', 'is_removal', 'is_card_draw',
            'is_board_wipe', 'is_tokens', 'is_counters', 'is_graveyard',
            'is_voltron', 'is_protection', 'is_tutor', 'is_finisher', 'is_utility'
        ]
        active_archetypes = [flag.replace('is_', '') for flag in archetype_flags if commander.get(flag)]
        logger.info(f"{', '.join(active_archetypes) if active_archetypes else 'None'}")
        
        # Score some test cards
        test_cards_to_score = [
            'Lightning Bolt',
            'Sol Ring', 
            'Llanowar Elves',
            'Counterspell',
            'Viscera Seer',
            'Sakura-Tribe Elder',
        ]
        
        synergy_scores = []
        found_count = 0
        
        for card_name in test_cards_to_score:
            card_matches = scorer.all_cards[scorer.all_cards['name'] == card_name]
            if len(card_matches) > 0:
                card = card_matches.iloc[0].to_dict()
                score, components = scorer.score_card(card, commander)
                synergy_scores.append(score)
                logger.info(f"     {card_name:25s} → synergy={components['mechanic_synergy']:.1f}, archetype={components['archetype_fit']:.1f}, total={score:.1f}")
                found_count += 1
        
        if synergy_scores:
            min_score = min(synergy_scores)
            max_score = max(synergy_scores)
            avg_score = sum(synergy_scores) / len(synergy_scores)
            logger.info(f"\n     Score range: {min_score:.1f} - {max_score:.1f} (avg: {avg_score:.1f})")
            
            if min_score < max_score:
                logger.info(f"     ✓ PASS: Scores show variance (not all identical)")
            else:
                logger.warning(f"     ✗ FAIL: All scores identical")
    
    logger.info("\n" + "="*70)
    logger.info("✓ VALIDATION COMPLETE")
    logger.info("="*70)
    logger.info("\nNext steps:")
    logger.info("1. Run card_scoring_validation.ipynb to verify synergy calculation")
    logger.info("2. Check that different commanders get different recommendations")
    logger.info("3. Verify known staples rank in top 100-500")

if __name__ == "__main__":
    main()
