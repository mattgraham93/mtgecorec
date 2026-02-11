"""
Unit tests for CommanderCard serialization (multiprocessing support)
"""
import pytest
from core.data_engine.commander_model import CommanderCard, ColorIdentity


def test_color_identity_to_dict():
    """Test ColorIdentity serialization to dict"""
    # Test with colors
    ci = ColorIdentity(colors={'W', 'U', 'B'})
    result = ci.to_dict()
    
    assert 'colors' in result
    assert isinstance(result['colors'], list)
    assert set(result['colors']) == {'W', 'U', 'B'}
    print("✓ ColorIdentity.to_dict() works with colors")
    
    # Test colorless
    ci_colorless = ColorIdentity(colors=set())
    result_colorless = ci_colorless.to_dict()
    
    assert result_colorless['colors'] == []
    print("✓ ColorIdentity.to_dict() works with colorless")


def test_color_identity_from_dict():
    """Test ColorIdentity deserialization from dict"""
    # Test with colors
    data = {'colors': ['W', 'U', 'B']}
    ci = ColorIdentity.from_dict(data)
    
    assert ci.colors == {'W', 'U', 'B'}
    print("✓ ColorIdentity.from_dict() works with colors")
    
    # Test colorless
    data_colorless = {'colors': []}
    ci_colorless = ColorIdentity.from_dict(data_colorless)
    
    assert ci_colorless.colors == set()
    print("✓ ColorIdentity.from_dict() works with colorless")
    
    # Test missing key
    data_empty = {}
    ci_empty = ColorIdentity.from_dict(data_empty)
    
    assert ci_empty.colors == set()
    print("✓ ColorIdentity.from_dict() handles missing 'colors' key")


def test_color_identity_round_trip():
    """Test ColorIdentity serialization round-trip"""
    original = ColorIdentity(colors={'R', 'G'})
    
    # Serialize and deserialize
    data = original.to_dict()
    restored = ColorIdentity.from_dict(data)
    
    # Verify fields match
    assert original.colors == restored.colors
    assert original.to_string() == restored.to_string()
    print("✓ ColorIdentity round-trip preserves all data")


def test_commander_card_to_dict():
    """Test CommanderCard serialization to dict"""
    ci = ColorIdentity(colors={'B', 'G'})
    
    commander = CommanderCard(
        name="Meren of Clan Nel Toth",
        mana_cost="{2}{B}{G}",
        colors=['B', 'G'],
        color_identity=ci,
        types=['Legendary', 'Creature'],
        subtypes=['Human', 'Shaman'],
        rules_text="Whenever another creature you control dies, you get an experience counter.",
        power=3,
        toughness=4,
        loyalty=None,
        is_legendary=True,
        can_be_commander=True,
        partner=False,
        partner_with=None
    )
    
    result = commander.to_dict()
    
    # Verify all fields present
    assert result['name'] == "Meren of Clan Nel Toth"
    assert result['mana_cost'] == "{2}{B}{G}"
    assert result['colors'] == ['B', 'G']
    assert 'color_identity' in result
    assert isinstance(result['color_identity'], dict)
    assert result['types'] == ['Legendary', 'Creature']
    assert result['subtypes'] == ['Human', 'Shaman']
    assert result['power'] == 3
    assert result['toughness'] == 4
    assert result['loyalty'] is None
    assert result['is_legendary'] is True
    assert result['can_be_commander'] is True
    assert result['partner'] is False
    assert result['partner_with'] is None
    
    print("✓ CommanderCard.to_dict() serializes all fields correctly")


def test_commander_card_from_dict():
    """Test CommanderCard deserialization from dict"""
    data = {
        'name': "Atraxa, Praetors' Voice",
        'mana_cost': "{G}{W}{U}{B}",
        'colors': ['W', 'U', 'B', 'G'],
        'color_identity': {'colors': ['W', 'U', 'B', 'G']},
        'types': ['Legendary', 'Creature'],
        'subtypes': ['Phyrexian', 'Angel', 'Horror'],
        'rules_text': "Flying, vigilance, deathtouch, lifelink",
        'power': 4,
        'toughness': 4,
        'loyalty': None,
        'is_legendary': True,
        'can_be_commander': True,
        'partner': False,
        'partner_with': None
    }
    
    commander = CommanderCard.from_dict(data)
    
    # Verify all fields restored
    assert commander.name == "Atraxa, Praetors' Voice"
    assert commander.mana_cost == "{G}{W}{U}{B}"
    assert commander.colors == ['W', 'U', 'B', 'G']
    assert commander.color_identity.colors == {'W', 'U', 'B', 'G'}
    assert commander.types == ['Legendary', 'Creature']
    assert commander.subtypes == ['Phyrexian', 'Angel', 'Horror']
    assert commander.power == 4
    assert commander.toughness == 4
    assert commander.loyalty is None
    assert commander.is_legendary is True
    assert commander.can_be_commander is True
    assert commander.partner is False
    assert commander.partner_with is None
    
    print("✓ CommanderCard.from_dict() deserializes all fields correctly")


def test_commander_card_round_trip():
    """Test CommanderCard serialization round-trip"""
    ci = ColorIdentity(colors={'U', 'R'})
    
    original = CommanderCard(
        name="Niv-Mizzet, Parun",
        mana_cost="{U}{U}{U}{R}{R}{R}",
        colors=['U', 'R'],
        color_identity=ci,
        types=['Legendary', 'Creature'],
        subtypes=['Dragon', 'Wizard'],
        rules_text="This spell can't be countered. Flying. Whenever you draw a card, Niv-Mizzet, Parun deals 1 damage to any target.",
        power=5,
        toughness=5,
        loyalty=None,
        is_legendary=True,
        can_be_commander=True,
        partner=False,
        partner_with=None
    )
    
    # Serialize and deserialize
    data = original.to_dict()
    restored = CommanderCard.from_dict(data)
    
    # Verify all fields match
    assert original.name == restored.name
    assert original.mana_cost == restored.mana_cost
    assert original.colors == restored.colors
    assert original.color_identity.colors == restored.color_identity.colors
    assert original.types == restored.types
    assert original.subtypes == restored.subtypes
    assert original.rules_text == restored.rules_text
    assert original.power == restored.power
    assert original.toughness == restored.toughness
    assert original.loyalty == restored.loyalty
    assert original.is_legendary == restored.is_legendary
    assert original.can_be_commander == restored.can_be_commander
    assert original.partner == restored.partner
    assert original.partner_with == restored.partner_with
    
    print("✓ CommanderCard round-trip preserves all data")


def test_commander_card_edge_cases():
    """Test edge cases: planeswalker, partner, empty fields"""
    # Planeswalker with loyalty
    pw_ci = ColorIdentity(colors={'W', 'U'})
    planeswalker = CommanderCard(
        name="Teferi, Temporal Archmage",
        mana_cost="{4}{U}{U}",
        colors=['U'],
        color_identity=pw_ci,
        types=['Legendary', 'Planeswalker'],
        subtypes=['Teferi'],
        rules_text="+1: Look at the top two cards of your library.",
        power=None,
        toughness=None,
        loyalty=5,
        is_legendary=True,
        can_be_commander=True,
        partner=False,
        partner_with=None
    )
    
    data = planeswalker.to_dict()
    restored = CommanderCard.from_dict(data)
    
    assert restored.power is None
    assert restored.toughness is None
    assert restored.loyalty == 5
    print("✓ Planeswalker serialization works (loyalty instead of power/toughness)")
    
    # Partner commander
    partner_ci = ColorIdentity(colors={'R', 'W'})
    partner_cmd = CommanderCard(
        name="Tymna the Weaver",
        mana_cost="{1}{W}{B}",
        colors=['W', 'B'],
        color_identity=partner_ci,
        types=['Legendary', 'Creature'],
        subtypes=['Human', 'Cleric'],
        rules_text="Lifelink. At the beginning of your postcombat main phase, you may pay X life, where X is the number of opponents that were dealt combat damage this turn. If you do, draw X cards. Partner",
        power=2,
        toughness=2,
        loyalty=None,
        is_legendary=True,
        can_be_commander=True,
        partner=True,
        partner_with=None
    )
    
    data = partner_cmd.to_dict()
    restored = CommanderCard.from_dict(data)
    
    assert restored.partner is True
    print("✓ Partner commander serialization works")


if __name__ == "__main__":
    # Run all tests
    print("\n" + "="*60)
    print("CommanderCard Serialization Tests")
    print("="*60 + "\n")
    
    test_color_identity_to_dict()
    test_color_identity_from_dict()
    test_color_identity_round_trip()
    print()
    
    test_commander_card_to_dict()
    test_commander_card_from_dict()
    test_commander_card_round_trip()
    print()
    
    test_commander_card_edge_cases()
    
    print("\n" + "="*60)
    print("✓✓✓ ALL TESTS PASSED ✓✓✓")
    print("="*60 + "\n")
