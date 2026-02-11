"""
commander_model.py - Commander format data models and utilities

This module provides data structures and utilities for Commander format deck building,
including color identity calculations, legality checks, and deck validation.
"""
import re
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class CommanderArchetype(Enum):
    """Common Commander deck archetypes."""
    AGGRO = "aggro"
    CONTROL = "control" 
    COMBO = "combo"
    MIDRANGE = "midrange"
    VOLTRON = "voltron"
    TRIBAL = "tribal"
    ARTIFACTS = "artifacts"
    ENCHANTMENTS = "enchantments"
    GRAVEYARD = "graveyard"
    LANDS = "lands"
    TOKENS = "tokens"
    RAMP = "ramp"
    STAX = "stax"
    GROUP_HUG = "group_hug"
    POLITICS = "politics"


@dataclass
class ColorIdentity:
    """Represents a color identity in Magic: The Gathering."""
    colors: Set[str] = field(default_factory=set)
    
    @classmethod
    def from_mana_cost_and_rules_text(cls, mana_cost: str, rules_text: str = "") -> 'ColorIdentity':
        """Extract color identity from mana cost and rules text."""
        colors = set()
        
        # Extract from mana cost
        if mana_cost:
            color_symbols = re.findall(r'\{([WUBRG])\}', mana_cost.upper())
            colors.update(color_symbols)
        
        # Extract from rules text (hybrid mana, activated abilities, etc.)
        if rules_text:
            # Find all mana symbols in rules text
            all_symbols = re.findall(r'\{([WUBRG/]+)\}', rules_text.upper())
            for symbol in all_symbols:
                # Handle hybrid mana like {W/U}
                if '/' in symbol:
                    colors.update(symbol.split('/'))
                else:
                    colors.add(symbol)
        
        return cls(colors)
    
    @classmethod
    def from_color_list(cls, color_list: List[str]) -> 'ColorIdentity':
        """Create color identity from a list of color strings."""
        color_map = {'W': 'W', 'U': 'U', 'B': 'B', 'R': 'R', 'G': 'G',
                    'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'}
        
        colors = set()
        for color in color_list:
            if color in color_map:
                colors.add(color_map[color])
        
        return cls(colors)
    
    def contains(self, other: 'ColorIdentity') -> bool:
        """Check if this color identity contains another (for deck legality)."""
        return other.colors.issubset(self.colors)
    
    def is_colorless(self) -> bool:
        """Check if this is a colorless identity."""
        return len(self.colors) == 0
    
    def color_count(self) -> int:
        """Get the number of colors in this identity."""
        return len(self.colors)
    
    def to_string(self) -> str:
        """Convert to a readable string representation."""
        if not self.colors:
            return "Colorless"
        return "".join(sorted(self.colors))
    
    def to_guild_name(self) -> Optional[str]:
        """Get guild/shard name for common color combinations."""
        guilds = {
            frozenset(['W', 'U']): "Azorius",
            frozenset(['U', 'B']): "Dimir", 
            frozenset(['B', 'R']): "Rakdos",
            frozenset(['R', 'G']): "Gruul",
            frozenset(['G', 'W']): "Selesnya",
            frozenset(['W', 'B']): "Orzhov",
            frozenset(['U', 'R']): "Izzet",
            frozenset(['B', 'G']): "Golgari",
            frozenset(['R', 'W']): "Boros",
            frozenset(['G', 'U']): "Simic",
            frozenset(['W', 'U', 'B']): "Esper",
            frozenset(['U', 'B', 'R']): "Grixis",
            frozenset(['B', 'R', 'G']): "Jund",
            frozenset(['R', 'G', 'W']): "Naya",
            frozenset(['G', 'W', 'U']): "Bant",
            frozenset(['W', 'B', 'G']): "Abzan",
            frozenset(['U', 'R', 'W']): "Jeskai",
            frozenset(['B', 'G', 'U']): "Sultai",
            frozenset(['R', 'W', 'B']): "Mardu",
            frozenset(['G', 'U', 'R']): "Temur"
        }
        return guilds.get(frozenset(self.colors))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize ColorIdentity to a plain dict for multiprocessing.
        
        Returns:
            Dict with 'colors' key containing list of color strings
        """
        return {
            'colors': list(sorted(self.colors))  # Convert set to sorted list
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorIdentity':
        """
        Deserialize ColorIdentity from a plain dict.
        
        Args:
            data: Dict with 'colors' key containing list of color strings
            
        Returns:
            ColorIdentity instance
        """
        colors = data.get('colors', [])
        return cls(colors=set(colors))  # Convert list back to set


@dataclass 
class CommanderCard:
    """Represents a commander card with all relevant information."""
    name: str
    mana_cost: str
    colors: List[str]
    color_identity: ColorIdentity
    types: List[str]
    subtypes: List[str] 
    rules_text: str
    power: Optional[int] = None
    toughness: Optional[int] = None
    loyalty: Optional[int] = None
    is_legendary: bool = True
    can_be_commander: bool = True
    partner: bool = False
    partner_with: Optional[str] = None
    
    @classmethod
    def from_card_data(cls, card_data: Dict[str, Any]) -> 'CommanderCard':
        """Create CommanderCard from Scryfall card data."""
        # Extract type information
        type_line = card_data.get('type_line', '')
        types = []
        subtypes = []
        
        if ' — ' in type_line:
            main_types, sub_types = type_line.split(' — ', 1)
            types = main_types.split()
            subtypes = sub_types.split()
        else:
            types = type_line.split()
        
        # Check if legendary
        is_legendary = 'Legendary' in types
        
        # Check if can be commander (legendary creature or planeswalker with suitable ability)
        can_be_commander = (
            is_legendary and 
            ('Creature' in types or 'Planeswalker' in types or 
             'can be your commander' in card_data.get('oracle_text', '').lower())
        )
        
        # Check for partner abilities
        oracle_text = card_data.get('oracle_text', '')
        partner = 'Partner' in oracle_text or 'partner with' in oracle_text.lower()
        partner_with = None
        
        if 'partner with' in oracle_text.lower():
            # Extract partner name
            match = re.search(r'partner with ([^(]+)', oracle_text.lower())
            if match:
                partner_with = match.group(1).strip()
        
        # Create color identity
        color_identity = ColorIdentity.from_mana_cost_and_rules_text(
            card_data.get('mana_cost', ''), oracle_text
        )
        
        return cls(
            name=card_data.get('name', ''),
            mana_cost=card_data.get('mana_cost', ''),
            colors=card_data.get('colors', []),
            color_identity=color_identity,
            types=types,
            subtypes=subtypes,
            rules_text=oracle_text,
            power=card_data.get('power'),
            toughness=card_data.get('toughness'), 
            loyalty=card_data.get('loyalty'),
            is_legendary=is_legendary,
            can_be_commander=can_be_commander,
            partner=partner,
            partner_with=partner_with
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize CommanderCard to a plain dict for multiprocessing.
        
        This allows the card to be passed to worker processes via pickle.
        All complex objects (ColorIdentity) are serialized to dicts.
        
        Returns:
            Dict containing all CommanderCard fields
        """
        return {
            'name': self.name,
            'mana_cost': self.mana_cost,
            'colors': self.colors,  # Already a list
            'color_identity': self.color_identity.to_dict(),  # Serialize nested object
            'types': self.types,  # Already a list
            'subtypes': self.subtypes,  # Already a list
            'rules_text': self.rules_text,
            'power': self.power,
            'toughness': self.toughness,
            'loyalty': self.loyalty,
            'is_legendary': self.is_legendary,
            'can_be_commander': self.can_be_commander,
            'partner': self.partner,
            'partner_with': self.partner_with
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommanderCard':
        """
        Deserialize CommanderCard from a plain dict.
        
        This reconstructs a CommanderCard from the dict created by to_dict(),
        allowing it to be passed to worker processes.
        
        Args:
            data: Dict containing all CommanderCard fields
            
        Returns:
            CommanderCard instance
        """
        # Deserialize nested ColorIdentity
        color_identity_data = data.get('color_identity', {'colors': []})
        color_identity = ColorIdentity.from_dict(color_identity_data)
        
        return cls(
            name=data.get('name', ''),
            mana_cost=data.get('mana_cost', ''),
            colors=data.get('colors', []),
            color_identity=color_identity,
            types=data.get('types', []),
            subtypes=data.get('subtypes', []),
            rules_text=data.get('rules_text', ''),
            power=data.get('power'),
            toughness=data.get('toughness'),
            loyalty=data.get('loyalty'),
            is_legendary=data.get('is_legendary', True),
            can_be_commander=data.get('can_be_commander', True),
            partner=data.get('partner', False),
            partner_with=data.get('partner_with')
        )


@dataclass
class CommanderDeck:
    """Represents a complete Commander deck."""
    commander: CommanderCard
    partner_commander: Optional[CommanderCard] = None
    cards: List[Dict[str, Any]] = field(default_factory=list)
    color_identity: Optional[ColorIdentity] = None
    archetype: Optional[CommanderArchetype] = None
    
    def __post_init__(self):
        """Calculate color identity after initialization."""
        if not self.color_identity:
            commander_colors = self.commander.color_identity.colors
            if self.partner_commander:
                commander_colors = commander_colors.union(self.partner_commander.color_identity.colors)
            self.color_identity = ColorIdentity(commander_colors)
    
    def is_legal_card(self, card_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a card is legal in this Commander deck."""
        # Check color identity
        card_identity = ColorIdentity.from_mana_cost_and_rules_text(
            card_data.get('mana_cost', ''), card_data.get('oracle_text', '')
        )
        
        if not self.color_identity.contains(card_identity):
            return False, f"Card color identity {card_identity.to_string()} not in commander colors {self.color_identity.to_string()}"
        
        # Check singleton rule (except basic lands)
        card_name = card_data.get('name', '')
        is_basic_land = (
            'Basic' in card_data.get('type_line', '') and 
            'Land' in card_data.get('type_line', '')
        )
        
        if not is_basic_land:
            existing_names = [card.get('name', '') for card in self.cards]
            if card_name in existing_names:
                return False, f"Deck already contains {card_name} (singleton rule)"
        
        # Check Commander format legality
        legalities = card_data.get('legalities', {})
        if legalities.get('commander') not in ['legal', 'restricted']:
            return False, f"Card not legal in Commander format"
        
        return True, "Legal"
    
    def add_card(self, card_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Add a card to the deck if legal."""
        is_legal, reason = self.is_legal_card(card_data)
        
        if is_legal:
            self.cards.append(card_data)
            return True, "Card added successfully"
        else:
            return False, reason
    
    def get_mana_curve(self) -> Dict[int, int]:
        """Calculate the mana curve of the deck."""
        curve = {i: 0 for i in range(8)}  # 0-7+ mana
        
        for card in self.cards:
            cmc = card.get('cmc', 0)
            if cmc >= 7:
                curve[7] += 1
            else:
                curve[int(cmc)] += 1
        
        return curve
    
    def get_color_distribution(self) -> Dict[str, int]:
        """Get distribution of colors in the deck."""
        color_count = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'Colorless': 0}
        
        for card in self.cards:
            colors = card.get('colors', [])
            if not colors:
                color_count['Colorless'] += 1
            else:
                for color in colors:
                    if color in color_count:
                        color_count[color] += 1
        
        return color_count
    
    def get_type_distribution(self) -> Dict[str, int]:
        """Get distribution of card types in the deck."""
        types = {}
        
        for card in self.cards:
            type_line = card.get('type_line', '')
            main_type = type_line.split(' — ')[0].split()[-1] if type_line else 'Unknown'
            
            if main_type in types:
                types[main_type] += 1
            else:
                types[main_type] = 1
        
        return types
    
    def deck_size(self) -> int:
        """Get current deck size (excluding commander)."""
        return len(self.cards)
    
    def is_complete(self) -> bool:
        """Check if deck is complete (100 cards including commander)."""
        commander_count = 1 + (1 if self.partner_commander else 0)
        return len(self.cards) + commander_count == 100


class CommanderAnalyzer:
    """Utility class for analyzing Commander decks and cards."""
    
    @staticmethod
    def find_potential_commanders(cards: List[Dict[str, Any]]) -> List[CommanderCard]:
        """Find all potential commanders from a card list."""
        commanders = []
        
        for card_data in cards:
            try:
                commander = CommanderCard.from_card_data(card_data)
                if commander.can_be_commander:
                    commanders.append(commander)
            except Exception as e:
                print(f"Error processing card {card_data.get('name', 'Unknown')}: {e}")
                continue
        
        return commanders
    
    @staticmethod
    def suggest_archetype(commander: CommanderCard) -> List[CommanderArchetype]:
        """Suggest likely archetypes for a commander based on its characteristics."""
        archetypes = []
        rules_text = commander.rules_text.lower()
        types = [t.lower() for t in commander.types]
        subtypes = [s.lower() for s in commander.subtypes]
        
        # Tribal decks
        if any(tribe in subtypes for tribe in ['elf', 'goblin', 'zombie', 'dragon', 'angel', 'vampire', 'merfolk', 'human', 'soldier']):
            archetypes.append(CommanderArchetype.TRIBAL)
        
        # Voltron (equipment/aura focus)
        if ('equipment' in rules_text or 'attach' in rules_text or 
            'aura' in rules_text or '+1/+1' in rules_text):
            archetypes.append(CommanderArchetype.VOLTRON)
        
        # Combo
        if ('infinite' in rules_text or 'win the game' in rules_text or
            'each opponent' in rules_text):
            archetypes.append(CommanderArchetype.COMBO)
        
        # Tokens
        if ('token' in rules_text or 'create' in rules_text):
            archetypes.append(CommanderArchetype.TOKENS)
        
        # Artifacts
        if ('artifact' in rules_text or 'metalcraft' in rules_text):
            archetypes.append(CommanderArchetype.ARTIFACTS)
        
        # Graveyard
        if ('graveyard' in rules_text or 'mill' in rules_text or 
            'return' in rules_text and 'graveyard' in rules_text):
            archetypes.append(CommanderArchetype.GRAVEYARD)
        
        # Control (based on colors and abilities)
        if ('counter' in rules_text or 'draw' in rules_text or 'destroy' in rules_text):
            if commander.color_identity.colors & {'U', 'W', 'B'}:
                archetypes.append(CommanderArchetype.CONTROL)
        
        # Aggro (low mana cost, aggressive keywords)
        if (commander.mana_cost and re.findall(r'\{(\d+)\}', commander.mana_cost) and
            any(int(x) <= 3 for x in re.findall(r'\{(\d+)\}', commander.mana_cost))):
            if any(keyword in rules_text for keyword in ['haste', 'first strike', 'double strike', 'trample']):
                archetypes.append(CommanderArchetype.AGGRO)
        
        return archetypes or [CommanderArchetype.MIDRANGE]  # Default to midrange


def test_commander_model():
    """Test the Commander data model with sample data."""
    print("Testing Commander data model...")
    
    # Test color identity
    ci1 = ColorIdentity.from_mana_cost_and_rules_text("{2}{W}{U}", "Draw a card. {B}: Regenerate.")
    print(f"Color identity from cost and rules: {ci1.to_string()} ({ci1.to_guild_name()})")
    
    # Test sample commander
    sample_card = {
        'name': 'Atraxa, Praetors\' Voice',
        'mana_cost': '{G}{W}{U}{B}',
        'colors': ['W', 'U', 'B', 'G'],
        'type_line': 'Legendary Creature — Phyrexian Angel Horror',
        'oracle_text': 'Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.',
        'power': '4',
        'toughness': '4',
        'legalities': {'commander': 'legal'}
    }
    
    commander = CommanderCard.from_card_data(sample_card)
    print(f"\nCommander: {commander.name}")
    print(f"Color Identity: {commander.color_identity.to_string()}")
    print(f"Can be commander: {commander.can_be_commander}")
    
    # Test deck creation
    deck = CommanderDeck(commander=commander)
    print(f"\nDeck color identity: {deck.color_identity.to_string()}")
    
    # Test archetype suggestion
    archetypes = CommanderAnalyzer.suggest_archetype(commander)
    print(f"Suggested archetypes: {[a.value for a in archetypes]}")
    
    print("Commander model test complete!")


if __name__ == "__main__":
    test_commander_model()