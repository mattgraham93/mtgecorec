#!/usr/bin/env python3
"""Test the improved card extraction patterns."""

import re

def extract_cards_from_text(content: str):
    """Extract cards from text using improved pattern matching."""
    
    # Multiple extraction patterns to handle various formats (Updated patterns)
    patterns = [
        # Numbered lists with bold cards: "1. **Skullclamp** - description"
        r'^\s*\d+\.?\s*\*?\*?([A-Z][a-zA-Z\s\',\-]+?)\*?\*?\s*[-–]',
        
        # Bold cards: **Card Name**
        r'\*\*([A-Z][a-zA-Z\s\',\-]+?)\*\*',
        
        # Quoted cards: "Card Name"
        r'["""]([A-Z][a-zA-Z\s\',\-]+?)["""]',
        
        # Cards after action keywords (more specific)
        r'(?:recommend|suggest|include|consider|use|play|add|run)\s+([A-Z][a-zA-Z\s\',\-]{3,30}?)(?:\s+for|\s+to|\s|,|\.|\n|$)',
        
        # Cards mentioned with "along with": "along with Zur the Enchanter"
        r'along\s+with\s+([A-Z][a-zA-Z\s\',\-]{3,30}?)(?:\s+and|\s|,|\.|\n|$)',
        
        # Cards alongside other cards: "alongside Korvold, Fae-Cursed King"
        r'alongside\s+([A-Z][a-zA-Z\s\',\-]{3,30}?)(?:\s|,|\.|\n|$)',
        
        # Specific MTG phrases: "Swords to Plowshares", "Path to Exile"
        r'\b([A-Z][a-zA-Z]+\s+to\s+[A-Z][a-zA-Z]+)\b',
        
        # Card names with common MTG suffixes
        r'\b([A-Z][a-zA-Z]+(?:\s+the\s+[A-Z][a-zA-Z]+|clamp|signet|tower))\b',
        
        # Well-known card patterns (Conservative approach)
        r'\b(Zur\s+the\s+Enchanter|Oloro,?\s+Ageless\s+Ascetic|Korvold,?\s+Fae-Cursed\s+King|Chulane,?\s+Teller\s+of\s+Tales|Skullclamp|Sol\s+Ring|Arcane\s+Signet|Command\s+Tower|Rhystic\s+Study|Smothering\s+Tithe|Cyclonic\s+Rift)\b',
    ]
    
    suggested_cards = []
    
    print("🔍 Testing extraction patterns...")
    
    for i, pattern in enumerate(patterns, 1):
        print(f"\nPattern {i}: {pattern}")
        matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
        
        print(f"  Found {len(matches)} matches: {matches}")
        
        for match in matches:
            card_name = match.strip().rstrip(',').rstrip('.').rstrip(':').strip()
            
            if card_name and card_name not in suggested_cards:
                suggested_cards.append(card_name)
    
    return suggested_cards

# Test with the actual Perplexity response we saw
test_content = """Last updated on August 28, 2024

*Alela, Artful Provocateur | Illustration by Grzegorz Rutkowski*

Alela, Artful Provocateur is one of the most popular Esper () commanders out there along with Zur the Enchanter and Oloro, Ageless Ascetic. It's been printed in... *Throne of Eldraine* alongside Korvold, Fae-Cursed King and Chulane, Teller of Tales for Brawl, which are also very popular cards and commanders, and I've played with Alela enough to know its power.

This faerie dominates if it survives, and I recommend Skullclamp for massive card draw. You should also consider Swords to Plowshares for removal."""

print("🧪 Testing improved card extraction...")
print("\nTest content:")
print(test_content)
print("\n" + "="*50)

extracted_cards = extract_cards_from_text(test_content)

print(f"\n✅ Final extracted cards ({len(extracted_cards)}):")
for i, card in enumerate(extracted_cards, 1):
    print(f"{i}. '{card}'")