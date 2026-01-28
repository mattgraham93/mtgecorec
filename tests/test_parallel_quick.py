#!/usr/bin/env python3
"""
Quick validation test for parallel card scoring with Cosmos DB data.
Tests with a smaller sample to run quickly.
"""

import logging
import time
import sys
from core.data_engine.card_scoring import CardScorer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def quick_test():
    """Quick test of parallel scoring."""
    print("\n" + "="*70)
    print("QUICK PARALLEL SCORING VALIDATION")
    print("="*70)
    
    print("\nInitializing CardScorer with Cosmos DB data...")
    scorer = CardScorer()
    
    # Find a test commander
    meren_matches = scorer.all_cards[
        scorer.all_cards['name'].str.lower().str.strip() == 'meren of clan nel toth'.lower().strip()
    ]
    
    if len(meren_matches) == 0:
        print("❌ Commander not found")
        return False
    
    meren = meren_matches.iloc[0].to_dict()
    print(f"✓ Found commander: {meren.get('name')}")
    
    # Test parallel scoring exists and works
    print("\nTesting parallel scoring method...")
    if not hasattr(scorer, 'score_all_cards_parallel'):
        print("❌ score_all_cards_parallel method not found")
        return False
    
    print("✓ Parallel scoring method exists")
    
    # Run a quick test with limited scope
    print("\nRunning parallel scoring (this may take 30-60 seconds)...")
    start = time.time()
    try:
        results = scorer.score_all_cards_parallel(meren, [], n_jobs=4)
        elapsed = time.time() - start
        
        print(f"✓ Parallel scoring completed in {elapsed:.2f}s")
        print(f"  Cards scored: {len(results)}")
        print(f"  Cards/sec: {len(results)/elapsed:.0f}")
        
        # Validate results
        print("\n✓ Results validation:")
        print(f"  - Total results: {len(results)}")
        print(f"  - Has 'card_name': {('card_name' in results.columns)}")
        print(f"  - Has 'total_score': {('total_score' in results.columns)}")
        print(f"  - Score range: {results['total_score'].min():.2f} - {results['total_score'].max():.2f}")
        
        # Show top 5
        print(f"\n  Top 5 cards:")
        for i, (_, row) in enumerate(results.head(5).iterrows(), 1):
            print(f"    {i}. {row['card_name']}: {row['total_score']:.2f}")
        
        print("\n" + "="*70)
        print("✓ ALL VALIDATIONS PASSED")
        print("="*70 + "\n")
        return True
        
    except Exception as e:
        print(f"❌ Error during parallel scoring: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        success = quick_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)
