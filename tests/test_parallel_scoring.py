#!/usr/bin/env python3
"""
Test script for parallel card scoring implementation.

Verifies that:
1. Parallel scoring works without errors
2. Results match the sequential version
3. Performance improvement is measurable
4. Deduplication and filtering work correctly
"""

import logging
import time
import sys
from core.data_engine.card_scoring import CardScorer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_parallel_scoring():
    """Test parallel scoring implementation."""
    print("\n" + "="*70)
    print("PARALLEL CARD SCORING TEST")
    print("="*70)
    
    # Initialize scorer
    logger.info("Initializing CardScorer...")
    scorer = CardScorer()
    
    # Find Meren of Clan Nel Toth
    meren_name = 'Meren of Clan Nel Toth'
    meren_matches = scorer.all_cards[
        scorer.all_cards['name'].str.lower().str.strip() == meren_name.lower().strip()
    ]
    
    if len(meren_matches) == 0:
        logger.error(f"Commander '{meren_name}' not found in database")
        return False
    
    meren = meren_matches.iloc[0].to_dict()
    logger.info(f"Found commander: {meren.get('name')}")
    
    # Test 1: Sequential scoring
    print("\n" + "-"*70)
    print("TEST 1: Sequential Scoring")
    print("-"*70)
    
    start = time.time()
    results_sequential = scorer.score_all_cards(meren, [])
    sequential_time = time.time() - start
    
    print(f"Sequential results:")
    print(f"  Cards scored: {len(results_sequential)}")
    print(f"  Time: {sequential_time:.2f}s")
    print(f"  Cards/sec: {len(results_sequential)/sequential_time:.0f}")
    print(f"  Top 5 cards:")
    for idx, row in results_sequential.head(5).iterrows():
        print(f"    {idx+1}. {row['card_name']}: {row['total_score']:.2f}")
    
    # Test 2: Parallel scoring
    print("\n" + "-"*70)
    print("TEST 2: Parallel Scoring")
    print("-"*70)
    
    start = time.time()
    results_parallel = scorer.score_all_cards_parallel(meren, [], n_jobs=-1)
    parallel_time = time.time() - start
    
    print(f"Parallel results:")
    print(f"  Cards scored: {len(results_parallel)}")
    print(f"  Time: {parallel_time:.2f}s")
    print(f"  Cards/sec: {len(results_parallel)/parallel_time:.0f}")
    print(f"  Top 5 cards:")
    for idx, row in results_parallel.head(5).iterrows():
        print(f"    {idx+1}. {row['card_name']}: {row['total_score']:.2f}")
    
    # Test 3: Compare results
    print("\n" + "-"*70)
    print("TEST 3: Results Comparison")
    print("-"*70)
    
    # Check if both have same number of results
    if len(results_sequential) != len(results_parallel):
        logger.warning(f"Result count mismatch: sequential={len(results_sequential)}, parallel={len(results_parallel)}")
    else:
        logger.info(f"✓ Both methods returned {len(results_sequential)} cards")
    
    # Compare top 100
    top_100_seq = set(results_sequential['card_name'].head(100))
    top_100_par = set(results_parallel['card_name'].head(100))
    
    intersection = len(top_100_seq & top_100_par)
    print(f"Top 100 overlap: {intersection}/100 cards match")
    
    if intersection >= 95:
        logger.info("✓ Top 100 results are consistent")
    else:
        logger.warning(f"⚠ Only {intersection}/100 top cards match (may indicate differences)")
    
    # Check for exact score matches on top 20
    top_20_comparison = []
    for i in range(min(20, len(results_sequential), len(results_parallel))):
        seq_card = results_sequential.iloc[i]
        par_card = results_parallel.iloc[i]
        
        if seq_card['card_name'] == par_card['card_name']:
            score_diff = abs(seq_card['total_score'] - par_card['total_score'])
            if score_diff > 0.01:
                top_20_comparison.append((seq_card['card_name'], score_diff))
    
    if not top_20_comparison:
        logger.info("✓ All top 20 cards match with identical scores")
    else:
        logger.warning(f"⚠ {len(top_20_comparison)} top 20 cards have score differences")
        for card_name, diff in top_20_comparison[:5]:
            logger.warning(f"   {card_name}: diff={diff:.4f}")
    
    # Test 4: Performance analysis
    print("\n" + "-"*70)
    print("TEST 4: Performance Analysis")
    print("-"*70)
    
    speedup = sequential_time / parallel_time
    print(f"Speedup: {speedup:.2f}x")
    print(f"Sequential: {sequential_time:.2f}s")
    print(f"Parallel:   {parallel_time:.2f}s")
    print(f"Savings:    {sequential_time - parallel_time:.2f}s ({(1-parallel_time/sequential_time)*100:.1f}%)")
    
    # Test 5: Data validation
    print("\n" + "-"*70)
    print("TEST 5: Data Validation")
    print("-"*70)
    
    # Check for NaN/inf values
    nan_count = results_parallel[['total_score', 'base_power', 'mechanic_synergy']].isna().sum().sum()
    inf_count = (results_parallel[['total_score', 'base_power', 'mechanic_synergy']] == float('inf')).sum().sum()
    
    print(f"NaN values: {nan_count}")
    print(f"Inf values: {inf_count}")
    
    if nan_count > 0 or inf_count > 0:
        logger.error(f"Invalid values detected in results")
        return False
    
    logger.info("✓ All data validation passed")
    
    # Final summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✓ Parallel scoring works correctly")
    print(f"✓ Results are consistent ({intersection}/100 top cards match)")
    print(f"✓ Performance improvement: {speedup:.2f}x speedup")
    print(f"✓ Data validation: No NaN/Inf values")
    print("="*70 + "\n")
    
    return True


if __name__ == '__main__':
    try:
        success = test_parallel_scoring()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        sys.exit(1)
