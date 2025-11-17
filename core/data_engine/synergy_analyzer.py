"""
synergy_analyzer.py - Card synergy analysis for MTG Commander decks

This module provides algorithms to identify card synergies based on mechanics,
types, themes, and Commander strategies.
"""
import re
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict, Counter
from .commander_model import CommanderCard, ColorIdentity


@dataclass
class SynergyScore:
    """Represents a synergy score between cards or with a commander."""
    primary_card: str
    synergy_card: str
    score: float  # 0.0 to 1.0
    reasons: List[str]
    category: str  # 'mechanical', 'thematic', 'tribal', 'combo', etc.


class SynergyAnalyzer:
    """Analyzes card synergies for Commander deck building."""
    
    def __init__(self):
        # Common MTG keywords and mechanics
        self.keywords = {
            'flying', 'trample', 'haste', 'vigilance', 'deathtouch', 'lifelink',
            'first strike', 'double strike', 'reach', 'flash', 'hexproof',
            'indestructible', 'menace', 'prowess', 'scry', 'surveil', 'explore',
            'convoke', 'delve', 'escape', 'flashback', 'madness', 'cycling',
            'kicker', 'multikicker', 'overload', 'populate', 'proliferate',
            'storm', 'cascade', 'suspend', 'morph', 'manifest', 'megamorph',
            'awaken', 'surge', 'emerge', 'escalate', 'undaunted', 'partner',
            'improvise', 'aftermath', 'eternalize', 'embalm', 'afflict',
            'rampage', 'bushido', 'ninjutsu', 'soulshift', 'splice', 'channel'
        }
        
        # Tribal synergies
        self.tribes = {
            'angel', 'demon', 'dragon', 'sphinx', 'hydra', 'kraken', 'leviathan',
            'octopus', 'serpent', 'whale', 'elf', 'goblin', 'human', 'zombie',
            'vampire', 'werewolf', 'spirit', 'elemental', 'beast', 'bird',
            'cat', 'dog', 'soldier', 'warrior', 'wizard', 'cleric', 'rogue',
            'knight', 'merfolk', 'treefolk', 'giant', 'dwarf', 'artifact creature'
        }
        
        # Mechanical themes
        self.themes = {
            'artifacts': ['artifact', 'equipment', 'metalcraft', 'affinity', 'improvise'],
            'enchantments': ['enchantment', 'constellation', 'aura', 'enchant'],
            'graveyard': ['graveyard', 'mill', 'dredge', 'flashback', 'unearth', 'reanimate'],
            'tokens': ['token', 'populate', 'create', 'copy'],
            'counters': ['+1/+1 counter', 'proliferate', 'counter', 'experience counter'],
            'lands': ['landfall', 'land', 'ramp', 'basic land'],
            'spells': ['instant', 'sorcery', 'spell', 'prowess', 'storm'],
            'combat': ['attack', 'combat', 'power', 'toughness', 'damage'],
            'lifegain': ['lifegain', 'life', 'lifelink'],
            'card_draw': ['draw', 'card', 'hand size'],
            'sacrifice': ['sacrifice', 'dies', 'death trigger'],
            'enter_battlefield': ['enters the battlefield', 'etb', 'when ~ enters'],
            'planeswalkers': ['planeswalker', 'loyalty', 'superfriends']
        }
    
    def extract_mechanics(self, card_text: str) -> Set[str]:
        """Extract mechanics and keywords from card text."""
        if not card_text:
            return set()
            
        text = card_text.lower()
        mechanics = set()
        
        # Find keywords
        for keyword in self.keywords:
            if keyword in text:
                mechanics.add(keyword)
        
        # Find abilities with patterns
        patterns = {
            'etb': r'when .* enters the battlefield',
            'dies': r'when .* dies',
            'attack': r'when .* attacks',
            'deal_damage': r'deals? \d+ damage',
            'draw_cards': r'draw \d+ cards?',
            'gain_life': r'gain \d+ life',
            'mill': r'mill \d+',
            'scry': r'scry \d+',
            'counter_spell': r'counter target spell',
            'destroy': r'destroy target',
            'exile': r'exile target',
            'return_hand': r'return .* to .* hand',
            'return_battlefield': r'return .* to the battlefield',
            'search_library': r'search your library',
            'discard': r'discard',
            'sacrifice': r'sacrifice',
            'tap': r'tap target',
            'untap': r'untap',
            'create_token': r'create .* token',
            'copy': r'copy target',
            'double': r'double',
            'additional_turn': r'extra turn',
            'cant_block': r"can't block",
            'cant_attack': r"can't attack",
            'protection': r'protection from',
            'ward': r'ward',
            'hexproof': r'hexproof',
            'shroud': r'shroud'
        }
        
        for mechanic, pattern in patterns.items():
            if re.search(pattern, text):
                mechanics.add(mechanic)
        
        return mechanics
    
    def extract_tribes(self, type_line: str, card_text: str) -> Set[str]:
        """Extract creature types and tribal references."""
        tribes = set()
        
        if type_line:
            type_text = type_line.lower()
            for tribe in self.tribes:
                if tribe in type_text:
                    tribes.add(tribe)
        
        if card_text:
            text = card_text.lower()
            for tribe in self.tribes:
                # Look for tribal references in text
                if f"{tribe}s" in text or tribe in text:
                    tribes.add(tribe)
        
        return tribes
    
    def extract_themes(self, card_text: str, type_line: str) -> Dict[str, float]:
        """Extract thematic elements and assign relevance scores."""
        themes = defaultdict(float)
        
        if not card_text:
            return themes
        
        text = card_text.lower()
        type_text = type_line.lower() if type_line else ""
        
        for theme_name, keywords in self.themes.items():
            score = 0.0
            
            for keyword in keywords:
                # Count occurrences in text
                text_count = text.count(keyword)
                type_count = type_text.count(keyword)
                
                # Weight differently based on where it appears
                score += text_count * 0.8 + type_count * 1.0
            
            if score > 0:
                themes[theme_name] = min(score, 3.0) / 3.0  # Normalize to 0-1
        
        return dict(themes)
    
    def calculate_mechanical_synergy(self, card1: Dict[str, Any], card2: Dict[str, Any]) -> SynergyScore:
        """Calculate synergy score based on mechanical interactions."""
        name1 = card1.get('name', '')
        name2 = card2.get('name', '')
        
        mechanics1 = self.extract_mechanics(card1.get('oracle_text', ''))
        mechanics2 = self.extract_mechanics(card2.get('oracle_text', ''))
        
        # Find shared mechanics
        shared_mechanics = mechanics1 & mechanics2
        complementary_pairs = {
            ('lifegain', 'draw_cards'),
            ('mill', 'return_battlefield'),
            ('sacrifice', 'dies'),
            ('etb', 'return_hand'),
            ('tokens', 'sacrifice'),
            ('counters', 'proliferate'),
            ('artifacts', 'sacrifice'),
            ('graveyard', 'mill')
        }
        
        score = 0.0
        reasons = []
        
        # Shared mechanics bonus
        if shared_mechanics:
            score += len(shared_mechanics) * 0.2
            reasons.append(f"Shared mechanics: {', '.join(shared_mechanics)}")
        
        # Complementary mechanics
        for mech1 in mechanics1:
            for mech2 in mechanics2:
                if (mech1, mech2) in complementary_pairs or (mech2, mech1) in complementary_pairs:
                    score += 0.3
                    reasons.append(f"Complementary: {mech1} + {mech2}")
        
        return SynergyScore(
            primary_card=name1,
            synergy_card=name2,
            score=min(score, 1.0),
            reasons=reasons,
            category='mechanical'
        )
    
    def calculate_tribal_synergy(self, card1: Dict[str, Any], card2: Dict[str, Any]) -> SynergyScore:
        """Calculate synergy score based on tribal interactions."""
        name1 = card1.get('name', '')
        name2 = card2.get('name', '')
        
        tribes1 = self.extract_tribes(card1.get('type_line', ''), card1.get('oracle_text', ''))
        tribes2 = self.extract_tribes(card2.get('type_line', ''), card2.get('oracle_text', ''))
        
        shared_tribes = tribes1 & tribes2
        
        score = 0.0
        reasons = []
        
        if shared_tribes:
            score = len(shared_tribes) * 0.4
            reasons.append(f"Shared tribes: {', '.join(shared_tribes)}")
        
        # Tribal support (one card supports the other's tribe)
        text1 = card1.get('oracle_text', '').lower()
        text2 = card2.get('oracle_text', '').lower()
        
        for tribe in tribes1:
            if tribe in text2 and tribe not in shared_tribes:
                score += 0.6
                reasons.append(f"{name2} supports {tribe}s")
        
        for tribe in tribes2:
            if tribe in text1 and tribe not in shared_tribes:
                score += 0.6
                reasons.append(f"{name1} supports {tribe}s")
        
        return SynergyScore(
            primary_card=name1,
            synergy_card=name2,
            score=min(score, 1.0),
            reasons=reasons,
            category='tribal'
        )
    
    def calculate_thematic_synergy(self, card1: Dict[str, Any], card2: Dict[str, Any]) -> SynergyScore:
        """Calculate synergy score based on thematic coherence."""
        name1 = card1.get('name', '')
        name2 = card2.get('name', '')
        
        themes1 = self.extract_themes(card1.get('oracle_text', ''), card1.get('type_line', ''))
        themes2 = self.extract_themes(card2.get('oracle_text', ''), card2.get('type_line', ''))
        
        score = 0.0
        reasons = []
        
        # Calculate theme overlap
        for theme in themes1:
            if theme in themes2:
                theme_score = (themes1[theme] + themes2[theme]) / 2
                score += theme_score * 0.4
                reasons.append(f"Shared theme: {theme} ({theme_score:.1f})")
        
        return SynergyScore(
            primary_card=name1,
            synergy_card=name2,
            score=min(score, 1.0),
            reasons=reasons,
            category='thematic'
        )
    
    def calculate_commander_synergy(self, commander: CommanderCard, card: Dict[str, Any]) -> SynergyScore:
        """Calculate how well a card synergizes with a specific commander."""
        card_name = card.get('name', '')
        
        # Combine all synergy types
        commander_data = {
            'name': commander.name,
            'oracle_text': commander.rules_text,
            'type_line': ' '.join(commander.types + commander.subtypes)
        }
        
        mechanical = self.calculate_mechanical_synergy(commander_data, card)
        tribal = self.calculate_tribal_synergy(commander_data, card)
        thematic = self.calculate_thematic_synergy(commander_data, card)
        
        # Weight the scores
        total_score = (mechanical.score * 0.4 + tribal.score * 0.3 + thematic.score * 0.3)
        
        all_reasons = []
        if mechanical.reasons:
            all_reasons.extend([f"Mechanical: {r}" for r in mechanical.reasons])
        if tribal.reasons:
            all_reasons.extend([f"Tribal: {r}" for r in tribal.reasons])
        if thematic.reasons:
            all_reasons.extend([f"Thematic: {r}" for r in thematic.reasons])
        
        return SynergyScore(
            primary_card=commander.name,
            synergy_card=card_name,
            score=total_score,
            reasons=all_reasons,
            category='commander_synergy'
        )
    
    def find_combo_potential(self, cards: List[Dict[str, Any]]) -> List[Tuple[str, str, List[str]]]:
        """Identify potential combos between cards."""
        combos = []
        
        # Known combo patterns
        combo_patterns = [
            # Infinite mana combos
            (['untap', 'mana'], ['tap', 'mana'], "Infinite mana potential"),
            # Infinite creatures
            (['create', 'token'], ['sacrifice', 'create'], "Infinite creature generation"),
            # Infinite card draw
            (['draw', 'card'], ['discard', 'draw'], "Infinite card draw engine"),
            # Infinite damage
            (['damage', 'deal'], ['untap', 'damage'], "Infinite damage combo"),
            # Infinite turns
            (['extra turn'], ['return', 'hand'], "Infinite turns"),
        ]
        
        for i, card1 in enumerate(cards):
            for j, card2 in enumerate(cards[i+1:], i+1):
                text1 = card1.get('oracle_text', '').lower()
                text2 = card2.get('oracle_text', '').lower()
                
                for pattern1, pattern2, description in combo_patterns:
                    if (any(p in text1 for p in pattern1) and 
                        any(p in text2 for p in pattern2)):
                        combos.append((
                            card1.get('name', ''),
                            card2.get('name', ''),
                            [description]
                        ))
        
        return combos
    
    def analyze_deck_synergies(self, commander: CommanderCard, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Comprehensive analysis of all synergies in a deck."""
        # Calculate commander synergies
        commander_synergies = []
        for card in cards:
            synergy = self.calculate_commander_synergy(commander, card)
            if synergy.score > 0.1:  # Only include meaningful synergies
                commander_synergies.append(synergy)
        
        # Sort by score
        commander_synergies.sort(key=lambda x: x.score, reverse=True)
        
        # Find card-to-card synergies
        card_synergies = []
        for i, card1 in enumerate(cards):
            for j, card2 in enumerate(cards[i+1:], i+1):
                mechanical = self.calculate_mechanical_synergy(card1, card2)
                tribal = self.calculate_tribal_synergy(card1, card2)
                thematic = self.calculate_thematic_synergy(card1, card2)
                
                # Take the best synergy type
                best_synergy = max([mechanical, tribal, thematic], key=lambda x: x.score)
                if best_synergy.score > 0.2:
                    card_synergies.append(best_synergy)
        
        card_synergies.sort(key=lambda x: x.score, reverse=True)
        
        # Find combos
        combos = self.find_combo_potential(cards)
        
        # Analyze themes
        all_themes = defaultdict(float)
        for card in cards:
            card_themes = self.extract_themes(card.get('oracle_text', ''), card.get('type_line', ''))
            for theme, score in card_themes.items():
                all_themes[theme] += score
        
        # Normalize theme scores
        if all_themes:
            max_theme_score = max(all_themes.values())
            all_themes = {theme: score/max_theme_score for theme, score in all_themes.items()}
        
        return {
            'commander_synergies': commander_synergies[:10],  # Top 10
            'card_synergies': card_synergies[:15],  # Top 15
            'combos': combos,
            'dominant_themes': dict(sorted(all_themes.items(), key=lambda x: x[1], reverse=True)[:5]),
            'synergy_score': sum(s.score for s in commander_synergies[:10]) / min(len(commander_synergies), 10) if commander_synergies else 0.0
        }


def test_synergy_analyzer():
    """Test the synergy analyzer with sample cards."""
    print("Testing Synergy Analyzer...")
    
    analyzer = SynergyAnalyzer()
    
    # Sample commander
    commander_data = {
        'name': 'Atraxa, Praetors\' Voice',
        'mana_cost': '{G}{W}{U}{B}',
        'colors': ['W', 'U', 'B', 'G'],
        'type_line': 'Legendary Creature — Phyrexian Angel Horror',
        'oracle_text': 'Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.',
        'power': '4',
        'toughness': '4'
    }
    
    from commander_model import CommanderCard
    commander = CommanderCard.from_card_data(commander_data)
    
    # Sample cards
    cards = [
        {
            'name': 'Doubling Season',
            'oracle_text': 'If an effect would create one or more tokens under your control, it creates twice that many of those tokens instead. If an effect would put one or more counters on a permanent you control, it puts twice that many of those counters on that permanent instead.',
            'type_line': 'Enchantment'
        },
        {
            'name': 'Hardened Scales',
            'oracle_text': 'If one or more +1/+1 counters would be put on a creature you control, that many plus one +1/+1 counters are put on it instead.',
            'type_line': 'Enchantment'
        }
    ]
    
    # Test commander synergy
    for card in cards:
        synergy = analyzer.calculate_commander_synergy(commander, card)
        print(f"\n{commander.name} + {card['name']}: {synergy.score:.2f}")
        for reason in synergy.reasons:
            print(f"  - {reason}")
    
    # Test deck analysis
    analysis = analyzer.analyze_deck_synergies(commander, cards)
    print(f"\nDeck synergy analysis:")
    print(f"Overall synergy score: {analysis['synergy_score']:.2f}")
    print(f"Dominant themes: {analysis['dominant_themes']}")
    
    print("Synergy analyzer test complete!")


if __name__ == "__main__":
    test_synergy_analyzer()