"""
Unit tests for mechanic synergy calculation in CardScorer.

Tests the 5-step synergy algorithm:
1. Extract mechanics from card and commander
2. Calculate Jaccard similarity
3. Calculate weighted synergy
4. Calculate co-occurrence bonus
5. Combine with weights
"""

import pytest
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_engine.card_scoring import CardScorer


class TestMechanicExtraction:
    """Test mechanic extraction from various card data formats."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer with real Phase 1.5 data."""
        return CardScorer()
    
    def test_extract_card_mechanics_from_json_list(self, scorer):
        """Test extracting mechanics from JSON string list."""
        card = {'name': 'Test Card', 'detected_mechanics': '["flying", "lifelink"]'}
        mechanics = scorer._extract_card_mechanics(card)
        assert 'flying' in mechanics
        assert 'lifelink' in mechanics
    
    def test_extract_card_mechanics_from_python_list(self, scorer):
        """Test extracting mechanics from Python list."""
        card = {'name': 'Test Card', 'detected_mechanics': ['haste', 'trample']}
        mechanics = scorer._extract_card_mechanics(card)
        assert 'haste' in mechanics
        assert 'trample' in mechanics
    
    def test_extract_card_mechanics_empty(self, scorer):
        """Test extracting mechanics from card with no mechanics."""
        card = {'name': 'Sol Ring', 'detected_mechanics': []}
        mechanics = scorer._extract_card_mechanics(card)
        assert len(mechanics) == 0
    
    def test_extract_card_mechanics_missing_field(self, scorer):
        """Test extracting mechanics when field is missing."""
        card = {'name': 'Unknown Card'}
        mechanics = scorer._extract_card_mechanics(card)
        # Should return empty set or parsed from oracle_text
        assert isinstance(mechanics, set)
    
    def test_extract_commander_mechanics(self, scorer):
        """Test extracting mechanics from commander data."""
        commander = {
            'name': 'Meren of Clan Nel Toth',
            'detected_mechanics': ['graveyard', 'recursion', 'sacrifice']
        }
        mechanics = scorer._extract_commander_mechanics(commander)
        assert 'graveyard' in mechanics
        assert 'recursion' in mechanics
        assert 'sacrifice' in mechanics
    
    def test_mechanic_normalization(self, scorer):
        """Test mechanic name normalization."""
        # Test lowercase conversion
        normalized = scorer._normalize_mechanic_name('FLYING')
        assert normalized == 'flying'
        
        # Test whitespace stripping
        normalized = scorer._normalize_mechanic_name('  haste  ')
        assert normalized == 'haste'
        
        # Test combined
        normalized = scorer._normalize_mechanic_name('  Card Draw  ')
        assert normalized == 'card draw'


class TestJaccardSimilarity:
    """Test Jaccard similarity calculation."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer."""
        return CardScorer()
    
    def test_jaccard_identical_sets(self, scorer):
        """Test Jaccard with identical sets (should be 1.0)."""
        set_a = {'flying', 'lifelink'}
        set_b = {'flying', 'lifelink'}
        similarity = scorer._calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 1.0
    
    def test_jaccard_no_overlap(self, scorer):
        """Test Jaccard with no overlap (should be 0.0)."""
        set_a = {'flying', 'lifelink'}
        set_b = {'haste', 'trample'}
        similarity = scorer._calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.0
    
    def test_jaccard_partial_overlap(self, scorer):
        """Test Jaccard with partial overlap."""
        set_a = {'flying', 'lifelink', 'vigilance'}
        set_b = {'flying', 'haste'}
        # Intersection: {flying} = 1, Union: {flying, lifelink, vigilance, haste} = 4
        similarity = scorer._calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.25
    
    def test_jaccard_empty_set(self, scorer):
        """Test Jaccard when one set is empty."""
        set_a = {'flying'}
        set_b = set()
        similarity = scorer._calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.0
    
    def test_jaccard_both_empty(self, scorer):
        """Test Jaccard when both sets are empty."""
        set_a = set()
        set_b = set()
        similarity = scorer._calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.0


class TestSynergyWeights:
    """Test synergy weight lookup and calculation."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer."""
        return CardScorer()
    
    def test_synergy_weights_loaded(self, scorer):
        """Verify synergy weights were loaded."""
        assert len(scorer.mechanic_synergy_weights) > 0, "Synergy weights not loaded"
        # Should have weights for common mechanics
        # Check if any common mechanic is present
        common_mechanics = ['cast', 'flying', 'counter', 'sacrifice', 'create']
        found = any(mech in scorer.mechanic_synergy_weights for mech in common_mechanics)
        assert found, "No common mechanics found in synergy weights"
    
    def test_get_synergy_weight_found(self, scorer):
        """Test getting synergy weight for mechanics that exist."""
        # Should have some weights loaded
        weight = scorer._get_synergy_weight('flying', 'flying')
        # Weight should be between 0 and 1
        assert 0.0 <= weight <= 1.0
    
    def test_get_synergy_weight_not_found(self, scorer):
        """Test getting synergy weight for mechanics that don't exist."""
        weight = scorer._get_synergy_weight('nonexistent_mech_a', 'nonexistent_mech_b')
        assert weight == 0.0
    
    def test_weighted_synergy_overlapping_mechanics(self, scorer):
        """Test weighted synergy calculation with overlapping mechanics."""
        # If we have flying in both, should get positive synergy
        card_mechanics = {'flying', 'lifelink'}
        commander_mechanics = {'flying', 'haste'}
        
        weighted = scorer._calculate_weighted_synergy(card_mechanics, commander_mechanics)
        # Should be between 0 and 1
        assert 0.0 <= weighted <= 1.0
    
    def test_weighted_synergy_no_overlap(self, scorer):
        """Test weighted synergy with no overlapping mechanics."""
        card_mechanics = {'flying', 'lifelink'}
        commander_mechanics = {'haste', 'trample'}
        
        weighted = scorer._calculate_weighted_synergy(card_mechanics, commander_mechanics)
        # Might be 0 if no synergy weights exist for these pairs
        assert 0.0 <= weighted <= 1.0
    
    def test_weighted_synergy_empty_set(self, scorer):
        """Test weighted synergy with empty set."""
        card_mechanics = {'flying'}
        commander_mechanics = set()
        
        weighted = scorer._calculate_weighted_synergy(card_mechanics, commander_mechanics)
        assert weighted == 0.0


class TestCooccurrence:
    """Test co-occurrence matrix lookup and bonus calculation."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer."""
        return CardScorer()
    
    def test_cooccurrence_loaded(self, scorer):
        """Verify co-occurrence matrix was loaded."""
        assert len(scorer.mechanic_cooccurrence) > 0, "Co-occurrence matrix not loaded"
        # Should have entries for multiple mechanics
        assert len(scorer.mechanic_cooccurrence) >= 10, "Too few mechanics in co-occurrence matrix"
    
    def test_get_cooccurrence_count(self, scorer):
        """Test getting co-occurrence count."""
        # Get count for any two mechanics that exist
        if scorer.mechanic_cooccurrence:
            mech_a = list(scorer.mechanic_cooccurrence.keys())[0]
            mech_b = list(scorer.mechanic_cooccurrence[mech_a].keys())[0] if scorer.mechanic_cooccurrence[mech_a] else mech_a
            
            count = scorer._get_cooccurrence_count(mech_a, mech_b)
            assert count >= 0.0
    
    def test_cooccurrence_bonus(self, scorer):
        """Test co-occurrence bonus calculation."""
        # Should return normalized score between 0 and 1
        card_mechanics = {'flying', 'lifelink'}
        commander_mechanics = {'flying', 'haste'}
        
        bonus = scorer._calculate_cooccurrence_bonus(card_mechanics, commander_mechanics)
        assert 0.0 <= bonus <= 1.0
    
    def test_cooccurrence_bonus_no_overlap(self, scorer):
        """Test co-occurrence bonus with no overlapping mechanics."""
        card_mechanics = {'flying', 'lifelink'}
        commander_mechanics = {'haste', 'trample'}
        
        bonus = scorer._calculate_cooccurrence_bonus(card_mechanics, commander_mechanics)
        assert 0.0 <= bonus <= 1.0


class TestMechanicSynergy:
    """Test complete mechanic synergy calculation."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer."""
        return CardScorer()
    
    def test_synergy_both_no_mechanics(self, scorer):
        """Test synergy when neither card nor commander has mechanics."""
        card = {'name': 'Vanilla Card', 'detected_mechanics': []}
        commander = {'name': 'Vanilla Commander', 'detected_mechanics': []}
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
        assert score == 50.0  # Neutral baseline for both empty
    
    def test_synergy_card_no_mechanics_staples(self, scorer):
        """Test synergy for staple cards with no mechanics."""
        card = {'name': 'Sol Ring', 'detected_mechanics': []}
        commander = {
            'name': 'Atraxa',
            'detected_mechanics': ['proliferate', 'keywords']
        }
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
        assert score == 30.0  # Slight penalty for no mechanics
    
    def test_synergy_commander_no_mechanics(self, scorer):
        """Test synergy when commander has no mechanics."""
        card = {'name': 'Flying Card', 'detected_mechanics': ['flying', 'lifelink']}
        commander = {'name': 'Vanilla Commander', 'detected_mechanics': []}
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
        assert score == 60.0  # Universal utility bonus
    
    def test_synergy_perfect_overlap(self, scorer):
        """Test synergy with perfect mechanic overlap."""
        card = {'name': 'Token Card', 'detected_mechanics': ['tokens', 'sacrifice']}
        commander = {
            'name': 'Token Commander',
            'detected_mechanics': ['tokens', 'sacrifice']
        }
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        # Should be higher than random score due to perfect match
        assert score > 60.0  # Should be well above neutral
        assert score <= 100.0
    
    def test_synergy_no_overlap(self, scorer):
        """Test synergy with no mechanic overlap."""
        card = {'name': 'Flying Card', 'detected_mechanics': ['flying', 'vigilance']}
        commander = {
            'name': 'Graveyard Commander',
            'detected_mechanics': ['graveyard', 'recursion']
        }
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
        # Should be lower than perfect match but might not be zero
        # due to possible indirect synergies
    
    def test_synergy_partial_overlap(self, scorer):
        """Test synergy with partial mechanic overlap."""
        card = {'name': 'Sacrifice Card', 'detected_mechanics': ['sacrifice', 'death']}
        commander = {
            'name': 'Aristocrats Commander',
            'detected_mechanics': ['sacrifice', 'tokens', 'drain']
        }
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
        # Should be mid-range due to partial overlap


class TestScoringEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer."""
        return CardScorer()
    
    def test_synergy_with_null_values(self, scorer):
        """Test synergy calculation with None/null values."""
        card = {'name': 'Test', 'detected_mechanics': None}
        commander = {'name': 'Commander', 'detected_mechanics': None}
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
    
    def test_synergy_with_malformed_json(self, scorer):
        """Test synergy with malformed JSON in detected_mechanics."""
        card = {'name': 'Bad JSON', 'detected_mechanics': 'not valid json'}
        commander = {'name': 'Commander', 'detected_mechanics': ['valid']}
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0
    
    def test_synergy_missing_name_field(self, scorer):
        """Test synergy calculation with missing card names."""
        card = {'detected_mechanics': ['flying']}  # No name
        commander = {'detected_mechanics': ['flying']}  # No name
        
        score = scorer._calculate_mechanic_synergy(card, commander, [])
        assert 0.0 <= score <= 100.0


class TestDataLoadingAndLookups:
    """Test that all Phase 1.5 data is properly loaded and accessible."""
    
    @pytest.fixture
    def scorer(self):
        """Initialize CardScorer."""
        return CardScorer()
    
    def test_all_cards_loaded(self, scorer):
        """Verify master_analysis_full.csv was loaded."""
        assert hasattr(scorer, 'all_cards')
        assert len(scorer.all_cards) > 0
        assert 'name' in scorer.all_cards.columns
    
    def test_mechanic_weights_loaded(self, scorer):
        """Verify mechanic_synergy_weights.csv was loaded."""
        assert hasattr(scorer, 'mechanic_weights')
        assert len(scorer.mechanic_weights) > 0
    
    def test_cooccurrence_matrix_loaded(self, scorer):
        """Verify mechanic_cooccurrence_matrix.csv was loaded."""
        assert hasattr(scorer, 'cooccurrence_matrix')
        assert len(scorer.cooccurrence_matrix) > 0
    
    def test_synergy_weights_lookup_built(self, scorer):
        """Verify synergy weights lookup was built."""
        assert hasattr(scorer, 'mechanic_synergy_weights')
        assert len(scorer.mechanic_synergy_weights) > 0
        assert isinstance(scorer.mechanic_synergy_weights, dict)
    
    def test_cooccurrence_lookup_built(self, scorer):
        """Verify co-occurrence lookup was built."""
        assert hasattr(scorer, 'mechanic_cooccurrence')
        assert len(scorer.mechanic_cooccurrence) > 0
        assert isinstance(scorer.mechanic_cooccurrence, dict)
    
    def test_card_name_lookup_built(self, scorer):
        """Verify card name lookup was built."""
        assert hasattr(scorer, 'card_name_lookup')
        assert len(scorer.card_name_lookup) > 0
        assert isinstance(scorer.card_name_lookup, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
