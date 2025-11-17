"""
commander_validation.py - Commander format validation utilities

This module provides validation functions for Commander format deck building,
including color identity, singleton rules, and format legality checks.
"""
from typing import List, Dict, Tuple, Any
from commander_model import CommanderCard, ColorIdentity
from collections import Counter


class CommanderFormatValidator:
    """Validates Commander format rules and deck legality."""
    
    def __init__(self):
        self.banned_cards = {
            # Banned as commanders
            'braids, cabal minion',
            'erayo, soratami ascendant',
            'rofellos, llanowar emissary',
            
            # Banned in 99
            'ancestral recall',
            'balance',
            'biorhythm',
            'black lotus',
            'braids, cabal minion',
            'channel',
            'chaos orb',
            'coalition victory',
            'emrakul, the aeons torn',
            'erayo, soratami ascendant',
            'falling star',
            'fastbond',
            'flash',
            'gifts ungiven',
            'griselbrand',
            'hullbreacher',
            'iona, shield of emeria',
            'karakas',
            'leovold, emissary of trest',
            'library of alexandria',
            'limited resources',
            'lutri, the spellchaser',
            'mox emerald',
            'mox jet',
            'mox pearl',
            'mox ruby',
            'mox sapphire',
            'painter\'s servant',
            'panoptic mirror',
            'primeval titan',
            'prophet of kruphix',
            'recurring nightmare',
            'rofellos, llanowar emissary',
            'sundering titan',
            'sway of the stars',
            'sylvan primordial',
            'time vault',
            'time walk',
            'tinker',
            'tolarian academy',
            'trade secrets',
            'upheaval',
            'worldfire',
            'yawgmoth\'s bargain'
        }
    
    def validate_commander(self, commander_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate if a card can legally be a commander."""
        errors = []
        
        # Check if card is banned as commander
        name = commander_data.get('name', '').lower()
        if name in self.banned_cards:
            errors.append(f"{commander_data.get('name')} is banned as a commander")
        
        # Check if legendary or has "can be your commander"
        type_line = commander_data.get('type_line', '')
        oracle_text = commander_data.get('oracle_text', '')
        
        is_legendary = 'Legendary' in type_line
        has_commander_text = 'can be your commander' in oracle_text.lower()
        
        if not (is_legendary or has_commander_text):
            errors.append("Commander must be legendary or have 'can be your commander' text")
        
        # Check if creature or planeswalker (or has commander text)
        is_creature = 'Creature' in type_line
        is_planeswalker = 'Planeswalker' in type_line
        
        if not (is_creature or is_planeswalker or has_commander_text):
            errors.append("Commander must be a legendary creature, planeswalker, or have 'can be your commander' text")
        
        # Check format legality
        legalities = commander_data.get('legalities', {})
        if legalities.get('commander') not in ['legal', 'restricted']:
            errors.append("Card is not legal in Commander format")
        
        return len(errors) == 0, errors
    
    def validate_color_identity(self, commander_identity: ColorIdentity, card_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate if a card fits within the commander's color identity."""
        # Extract card's color identity
        card_identity = ColorIdentity.from_mana_cost_and_rules_text(
            card_data.get('mana_cost', ''), 
            card_data.get('oracle_text', '')
        )
        
        if commander_identity.contains(card_identity):
            return True, "Color identity is legal"
        else:
            return False, f"Card color identity {card_identity.to_string()} exceeds commander identity {commander_identity.to_string()}"
    
    def validate_singleton_rule(self, deck_cards: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Validate singleton rule (no duplicates except basic lands)."""
        errors = []
        
        # Count card names
        card_names = []
        for card in deck_cards:
            name = card.get('name', '')
            type_line = card.get('type_line', '')
            
            # Skip basic lands
            is_basic_land = 'Basic' in type_line and 'Land' in type_line
            if not is_basic_land:
                card_names.append(name)
        
        # Find duplicates
        name_counts = Counter(card_names)
        for name, count in name_counts.items():
            if count > 1:
                errors.append(f"Duplicate card: {name} (appears {count} times)")
        
        return len(errors) == 0, errors
    
    def validate_deck_size(self, deck_cards: List[Dict[str, Any]], commander_count: int = 1) -> Tuple[bool, str]:
        """Validate deck has exactly 100 cards including commander(s)."""
        total_cards = len(deck_cards) + commander_count
        
        if total_cards == 100:
            return True, "Deck size is correct (100 cards)"
        elif total_cards < 100:
            return False, f"Deck too small ({total_cards}/100 cards)"
        else:
            return False, f"Deck too large ({total_cards}/100 cards)"
    
    def validate_banned_cards(self, deck_cards: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Check for banned cards in the 99."""
        errors = []
        
        for card in deck_cards:
            name = card.get('name', '').lower()
            if name in self.banned_cards:
                errors.append(f"Banned card: {card.get('name')}")
        
        return len(errors) == 0, errors
    
    def validate_format_legality(self, deck_cards: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Check if all cards are legal in Commander format."""
        errors = []
        
        for card in deck_cards:
            legalities = card.get('legalities', {})
            commander_legal = legalities.get('commander')
            
            if commander_legal not in ['legal', 'restricted']:
                errors.append(f"Format illegal: {card.get('name')} ({commander_legal})")
        
        return len(errors) == 0, errors
    
    def validate_complete_deck(self, commander_data: Dict[str, Any], 
                              deck_cards: List[Dict[str, Any]],
                              partner_commander: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform complete deck validation."""
        results = {
            'is_legal': True,
            'errors': [],
            'warnings': [],
            'commander_validation': {},
            'deck_validation': {}
        }
        
        # Validate commander
        commander_legal, commander_errors = self.validate_commander(commander_data)
        results['commander_validation'] = {
            'is_legal': commander_legal,
            'errors': commander_errors
        }
        
        if not commander_legal:
            results['is_legal'] = False
            results['errors'].extend(commander_errors)
        
        # Validate partner commander if present
        if partner_commander:
            partner_legal, partner_errors = self.validate_commander(partner_commander)
            if not partner_legal:
                results['is_legal'] = False
                results['errors'].extend([f"Partner: {error}" for error in partner_errors])
        
        # Get commander color identity
        commander_identity = ColorIdentity.from_mana_cost_and_rules_text(
            commander_data.get('mana_cost', ''), 
            commander_data.get('oracle_text', '')
        )
        
        if partner_commander:
            partner_identity = ColorIdentity.from_mana_cost_and_rules_text(
                partner_commander.get('mana_cost', ''),
                partner_commander.get('oracle_text', '')
            )
            # Combine color identities
            combined_colors = commander_identity.colors | partner_identity.colors
            commander_identity = ColorIdentity(combined_colors)
        
        # Validate deck cards
        color_errors = []
        for card in deck_cards:
            card_legal, error_msg = self.validate_color_identity(commander_identity, card)
            if not card_legal:
                color_errors.append(error_msg)
        
        singleton_legal, singleton_errors = self.validate_singleton_rule(deck_cards)
        size_legal, size_error = self.validate_deck_size(deck_cards, 1 + (1 if partner_commander else 0))
        banned_legal, banned_errors = self.validate_banned_cards(deck_cards)
        format_legal, format_errors = self.validate_format_legality(deck_cards)
        
        results['deck_validation'] = {
            'color_identity': len(color_errors) == 0,
            'singleton_rule': singleton_legal,
            'deck_size': size_legal,
            'banned_cards': banned_legal,
            'format_legality': format_legal
        }
        
        # Collect all errors
        all_deck_errors = color_errors + singleton_errors + banned_errors + format_errors
        if not size_legal:
            all_deck_errors.append(size_error)
        
        if all_deck_errors:
            results['is_legal'] = False
            results['errors'].extend(all_deck_errors)
        
        # Add warnings for potential issues
        if len(deck_cards) < 90:
            results['warnings'].append("Deck is significantly under 100 cards")
        
        # Check mana curve
        high_cmc_count = sum(1 for card in deck_cards if card.get('cmc', 0) >= 7)
        if high_cmc_count > 8:
            results['warnings'].append(f"High mana curve: {high_cmc_count} cards with CMC 7+")
        
        return results


def test_validator():
    """Test the Commander format validator."""
    print("Testing Commander Format Validator...")
    
    validator = CommanderFormatValidator()
    
    # Test commander validation
    sample_commander = {
        'name': 'Atraxa, Praetors\' Voice',
        'type_line': 'Legendary Creature — Phyrexian Angel Horror',
        'oracle_text': 'Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.',
        'mana_cost': '{G}{W}{U}{B}',
        'legalities': {'commander': 'legal'}
    }
    
    is_legal, errors = validator.validate_commander(sample_commander)
    print(f"Commander validation: {is_legal} (errors: {len(errors)})")
    
    # Test banned card
    banned_card = {
        'name': 'Black Lotus',
        'type_line': 'Artifact',
        'legalities': {'commander': 'banned'}
    }
    
    banned_legal, banned_errors = validator.validate_banned_cards([banned_card])
    print(f"Banned card test: {not banned_legal} (correctly identifies banned card)")
    
    # Test color identity
    commander_identity = ColorIdentity.from_color_list(['W', 'U', 'B', 'G'])
    
    legal_card = {
        'name': 'Wrath of God',
        'mana_cost': '{2}{W}{W}',
        'oracle_text': 'Destroy all creatures.'
    }
    
    illegal_card = {
        'name': 'Lightning Bolt',
        'mana_cost': '{R}',
        'oracle_text': 'Lightning Bolt deals 3 damage to any target.'
    }
    
    legal_check = validator.validate_color_identity(commander_identity, legal_card)
    illegal_check = validator.validate_color_identity(commander_identity, illegal_card)
    
    print(f"Color identity validation - Legal card: {legal_check[0]}")
    print(f"Color identity validation - Illegal card: {illegal_check[0]}")
    
    print("Commander format validator test complete!")


if __name__ == "__main__":
    test_validator()