#!/usr/bin/env python3
import sys, os
sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')
sys.path.insert(0, '/workspaces/mtgecorec')

# Load .env
with open('/workspaces/mtgecorec/.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

from pricing_pipeline import MTGPricingPipeline

pipeline = MTGPricingPipeline()
date = '2025-12-16'

print('🔍 Checking Scryfall ID Uniqueness')
print('=' * 50)

# Let's look at one of those duplicated scryfall IDs from our earlier diagnostic
duplicate_scryfall_id = '0000419b'  # From earlier diagnostic showing 11 duplicates

# Get all records for this specific scryfall_id
print(f'📋 Analyzing scryfall_id: {duplicate_scryfall_id}...')
records = list(pipeline.pricing_collection.find({
    'scryfall_id': {'$regex': f'^{duplicate_scryfall_id}'}, 
    'date': date
}).limit(20))

if records:
    full_id = records[0]['scryfall_id']
    print(f'Full scryfall_id: {full_id}')
    
    # Group by price_type to see duplicates
    by_price_type = {}
    for record in records:
        price_type = record.get('price_type', 'unknown')
        if price_type not in by_price_type:
            by_price_type[price_type] = []
        by_price_type[price_type].append(record)
    
    print(f'\n📊 Records by price_type:')
    for price_type, recs in by_price_type.items():
        print(f'  {price_type}: {len(recs)} records')
        
        if len(recs) > 1:
            print(f'    🔍 Duplicate details for {price_type}:')
            for i, rec in enumerate(recs[:3]):  # Show first 3
                print(f'      {i+1}. Price: ${rec.get("price_value", 0):.3f}')
                print(f'         Finish: {rec.get("finish", "unknown")}')
                print(f'         Collected: {rec.get("collected_at", "unknown")}')
                print(f'         Source: {rec.get("source", "unknown")}')
                if 'set_code' in rec:
                    print(f'         Set: {rec.get("set_code", "unknown")}')
                print()

print('\n🎯 Let\'s check a few more random cards:')

# Get a sample of cards with multiple records
sample_duplicates = list(pipeline.pricing_collection.aggregate([
    {'$match': {'date': date}},
    {'$group': {
        '_id': {'scryfall_id': '$scryfall_id', 'price_type': '$price_type', 'finish': '$finish'},
        'count': {'$sum': 1},
        'docs': {'$push': '$$ROOT'}
    }},
    {'$match': {'count': {'$gt': 1}}},
    {'$limit': 3}
]))

for dup in sample_duplicates:
    scryfall_id = dup['_id']['scryfall_id']
    price_type = dup['_id']['price_type']
    finish = dup['_id']['finish']
    count = dup['count']
    
    print(f'\n🔍 Card {scryfall_id[:8]}... | {price_type} | {finish}: {count} duplicates')
    
    for i, doc in enumerate(dup['docs'][:2]):  # Show first 2
        print(f'  {i+1}. Price: ${doc.get("price_value", 0):.3f}')
        print(f'     Collected: {doc.get("collected_at", "unknown")}')
        print(f'     Source: {doc.get("source", "unknown")}')
        print(f'     Card Name: {doc.get("card_name", "unknown")}')
        
        # Check if this record has set information
        for key in ['set_code', 'set_name', 'set', 'expansion']:
            if key in doc:
                print(f'     {key}: {doc[key]}')

print('\n🏷️  Checking if cards collection has set info:')
card_sample = pipeline.cards_collection.find_one()
if card_sample:
    print('Sample card fields:')
    for key in sorted(card_sample.keys())[:15]:  # Show first 15 fields
        print(f'  - {key}')
    
    if 'set' in card_sample or 'set_name' in card_sample:
        print(f'\n🎯 Cards DO have set information!')
    else:
        print(f'\n⚠️  Cards may not have set information in obvious fields')
else:
    print('No cards found in cards collection')