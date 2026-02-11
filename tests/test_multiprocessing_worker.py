"""
Integration test for multiprocessing worker with CommanderCard serialization
"""
from core.data_engine.commander_model import CommanderCard, ColorIdentity
from core.data_engine.commander_recommender import _score_batch_worker


def test_worker_function_with_serialization():
    """Test that the worker function can deserialize and use CommanderCard"""
    
    # Create a test commander
    ci = ColorIdentity(colors={'B', 'G'})
    commander = CommanderCard(
        name="Meren of Clan Nel Toth",
        mana_cost="{2}{B}{G}",
        colors=['B', 'G'],
        color_identity=ci,
        types=['Legendary', 'Creature'],
        subtypes=['Human', 'Shaman'],
        rules_text="Experience counters and graveyard synergy",
        power=3,
        toughness=4,
        loyalty=None,
        is_legendary=True,
        can_be_commander=True,
        partner=False,
        partner_with=None
    )
    
    # Serialize commander (as would happen before passing to worker)
    commander_dict = commander.to_dict()
    
    print(f"✓ Commander serialized: {commander_dict['name']}")
    
    # Create sample card data (simplified)
    card_items = [
        ('Sakura-Tribe Elder', [
            {
                'name': 'Sakura-Tribe Elder',
                'type_line': 'Creature — Snake Shaman',
                'oracle_text': 'Sacrifice: Search library for basic land',
                'cmc': 2,
                'colors': ['G'],
                'id': 'abc123'
            }
        ])
    ]
    
    current_deck = []
    budget_limit = None
    
    print(f"✓ Test data prepared: {len(card_items)} card(s)")
    
    # Call worker function (this will use from_dict internally)
    try:
        results = _score_batch_worker(
            card_items,
            commander_dict,  # Pass serialized commander
            current_deck,
            budget_limit
        )
        
        print(f"✓ Worker function executed successfully")
        print(f"✓ Results returned: {len(results)} recommendation(s)")
        
        if results:
            rec = results[0]
            print(f"✓ Sample result: {rec.card_name} (score: {rec.confidence_score:.2f})")
        
        assert len(results) > 0, "Worker should return at least one result"
        print("\n✓✓✓ INTEGRATION TEST PASSED ✓✓✓")
        
    except Exception as e:
        print(f"\n✗✗✗ INTEGRATION TEST FAILED ✗✗✗")
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Multiprocessing Worker Integration Test")
    print("="*60 + "\n")
    
    test_worker_function_with_serialization()
    
    print("\n" + "="*60)
