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

print('📊 Pricing Data Analysis for', date)
print('=' * 50)

# Total records for today
total_records = pipeline.pricing_collection.count_documents({'date': date})
print(f'Total pricing records: {total_records:,}')

# Unique cards with aggregation pipeline
unique_result = list(pipeline.pricing_collection.aggregate([
    {'$match': {'date': date}},
    {'$group': {'_id': '$scryfall_id'}},
    {'$count': 'unique_cards'}
]))

unique_cards = unique_result[0]['unique_cards'] if unique_result else 0
print(f'Unique cards with pricing: {unique_cards:,}')

if unique_cards > 0:
    avg_per_card = total_records / unique_cards
    print(f'Average records per card: {avg_per_card:.1f}')

print()
print('📋 Sample Records:')
samples = list(pipeline.pricing_collection.find({'date': date}).limit(5))
for i, record in enumerate(samples, 1):
    print(f'{i}. {record.get("card_name", "Unknown")} | {record.get("price_type", "Unknown")} | ${record.get("price_value", 0):.2f}')

print()
print('📈 Price Types Distribution:')
price_types = list(pipeline.pricing_collection.aggregate([
    {'$match': {'date': date}},
    {'$group': {'_id': '$price_type', 'count': {'$sum': 1}}},
    {'$sort': {'count': -1}}
]))

for pt in price_types:
    print(f'   {pt["_id"]}: {pt["count"]:,} records')

print()
print('🔍 Checking for True Duplicates (card + date + price_type + finish):')
# Check if there are duplicate records for the same card/price_type/finish combination
duplicates = list(pipeline.pricing_collection.aggregate([
    {'$match': {'date': date}},
    {'$group': {
        '_id': {
            'scryfall_id': '$scryfall_id', 
            'price_type': '$price_type',
            'finish': '$finish'
        }, 
        'count': {'$sum': 1}
    }},
    {'$match': {'count': {'$gt': 1}}},
    {'$limit': 10}
]))

if duplicates:
    print(f'Found {len(duplicates)} TRUE duplicate combinations (showing first 10):')
    for dup in duplicates:
        card_id = dup["_id"]["scryfall_id"][:8] + "..." if dup["_id"]["scryfall_id"] else "Unknown"
        price_type = dup["_id"]["price_type"]
        finish = dup["_id"]["finish"]
        count = dup["count"]
        print(f'   {card_id} | {price_type} | {finish}: {count} records')
else:
    print('No true duplicates found!')

print()
print('📊 Finish Distribution:')
finish_dist = list(pipeline.pricing_collection.aggregate([
    {'$match': {'date': date}},
    {'$group': {'_id': '$finish', 'count': {'$sum': 1}}},
    {'$sort': {'count': -1}}
]))

for finish in finish_dist:
    print(f'   {finish["_id"]}: {finish["count"]:,} records')