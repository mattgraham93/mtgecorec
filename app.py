import os
from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for, jsonify)
# Import Cosmos DB driver
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'data_engine'))
from data_engine import cosmos_driver

app = Flask(__name__, template_folder='templates', static_folder='static')

# Main page routes
@app.route('/')
def index():
   print('Request for index page received')
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
   return send_from_directory(os.path.join(app.root_path, 'static'),
                        'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/cards')
def cards():
   return render_template('cards.html')

@app.route('/visualizations')
def visualizations():
   return render_template('visualizations.html')

@app.route('/analysis')
def analysis():
   return send_from_directory(os.path.join(app.root_path, 'static'), 'card_explore.html', mimetype='text/html')

# API endpoint to get paginated card data as JSON
@app.route('/api/cards')
def api_cards():
   print('--- /api/cards called ---')
   client = cosmos_driver.get_mongo_client()
   database_name = 'cards'
   container_name = 'mtgecorec'
   collection = cosmos_driver.get_collection(client, container_name, database_name)
   # Get pagination params
   try:
      page = int(request.args.get('page', 1))
      page_size = int(request.args.get('page_size', 25))
      if page < 1: page = 1
      if page_size < 1: page_size = 25
   except Exception as e:
      print(f'Error parsing pagination params: {e}')
      page, page_size = 1, 25
   # Get filter params
   color_filter = request.args.get('color')
   type_filter = request.args.get('type')
   # Get sorting params
   sort_by = request.args.get('sort_by', 'name')  # default sort by name
   sort_order = request.args.get('sort_order', 'asc')  # 'asc' or 'desc'
   skip = (page - 1) * page_size
   print(f'Pagination params: page={page}, page_size={page_size}, skip={skip}')
   print(f'Filter params: color={color_filter}, type={type_filter}')
   print(f'Sort params: sort_by={sort_by}, sort_order={sort_order}')
   many = request.args.get('many') == 'true'
   # Build MongoDB query based on filters
   query = {}
   if color_filter:
      if color_filter == 'Many':
         query['$and'] = [
            {'colors': {'$exists': True}},
            {'colors': {'$ne': []}},
            {'colors': {'$not': {'$size': 1}}}
         ]
      elif many and color_filter in ['White', 'Blue', 'Black', 'Red', 'Green']:
         color_map = {
            'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'
         }
         color_code = color_map[color_filter]
         query['$and'] = [
            {'colors': {'$in': [color_code]}},
            {'colors': {'$size': {'$gt': 1}}}
         ]
      elif color_filter in ['White', 'Blue', 'Black', 'Red', 'Green']:
         color_map = {
            'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'
         }
         color_code = color_map[color_filter]
         query['colors'] = {'$in': [color_code]}
      elif color_filter == 'Colorless':
         query['$or'] = [
            {'colors': {'$exists': False}},
            {'colors': []},
            {'colors': None}
         ]
   if type_filter:
      if type_filter == 'Other':
         query['type_line'] = {'$not': {'$regex': '^(Creature|Instant|Sorcery|Enchantment|Artifact|Planeswalker|Land)'}}
      else:
         query['type_line'] = {'$regex': f'^{type_filter}'}
   print(f'MongoDB query: {query}')
   total = collection.count_documents(query)
   print(f'Total cards matching filters: {total}')
   # Build sort specification
   sort_spec = []
   if sort_by in ['name', 'type_line', 'set', 'rarity', 'price']:
      sort_direction = 1 if sort_order == 'asc' else -1
      sort_spec.append((sort_by, sort_direction))
   # Always sort by name as secondary sort for consistent ordering
   if sort_by != 'name':
      sort_spec.append(('name', 1))
   print(f'Sort specification: {sort_spec}')
   # Only return needed fields for each card
   projection = {
      '_id': 0,
      'name': 1,
      'type_line': 1,
      'set': 1,
      'rarity': 1,
      'price': 1,
      'image_uris': 1,
      'colors': 1,
      'mana_cost': 1,
      'artist': 1
   }
   cursor = collection.find(query, projection).sort(sort_spec).skip(skip).limit(page_size)
   cards = list(cursor)
   print(f'Returning {len(cards)} cards for this page')
   return jsonify({
      'cards': cards,
      'total': total,
      'page': page,
      'page_size': page_size
   })

@app.route('/api/cards/summary')
def api_cards_summary():
   import time
   from pymongo.errors import OperationFailure
   print('--- /api/cards/summary called ---')
   client = cosmos_driver.get_mongo_client()
   database_name = 'cards'
   container_name = 'mtgecorec'
   collection = cosmos_driver.get_collection(client, container_name, database_name)

   # Get filter params
   color_filter = request.args.get('color')
   type_filter = request.args.get('type')
   many = request.args.get('many') == 'true'

   # Build MongoDB query based on filters (same as /api/cards)
   query = {}
   if color_filter:
      if color_filter == 'Many':
         query['$and'] = [
            {'colors': {'$exists': True}},
            {'colors': {'$ne': []}},
            {'colors': {'$not': {'$size': 1}}}
         ]
      elif many and color_filter in ['White', 'Blue', 'Black', 'Red', 'Green']:
         color_map = {
            'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'
         }
         color_code = color_map[color_filter]
         query['$and'] = [
            {'colors': {'$in': [color_code]}},
            {'colors': {'$size': {'$gt': 1}}}
         ]
      elif color_filter in ['White', 'Blue', 'Black', 'Red', 'Green']:
         color_map = {
            'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'
         }
         color_code = color_map[color_filter]
         query['colors'] = {'$in': [color_code]}
      elif color_filter == 'Colorless':
         query['$or'] = [
            {'colors': {'$exists': False}},
            {'colors': []},
            {'colors': None}
         ]

   if type_filter:
      if type_filter == 'Other':
         query['type_line'] = {'$not': {'$regex': '^(Creature|Instant|Sorcery|Enchantment|Artifact|Planeswalker|Land)'}}
      else:
         query['type_line'] = {'$regex': f'^{type_filter}'}

   print(f'MongoDB summary query: {query}')

   # Aggregation pipeline for total, color, and type counts
   pipeline = [
      {'$match': query},
      {'$facet': {
         'total': [
            {'$count': 'count'}
         ],
         'colors': [
            {'$project': {'colors': 1}},
            {'$unwind': {
               'path': '$colors',
               'preserveNullAndEmptyArrays': True
            }},
            {'$group': {
               '_id': '$colors',
               'count': {'$sum': 1}
            }}
         ],
         'many': [
            {'$match': {'colors.1': {'$exists': True}}},
            {'$count': 'count'}
         ],
         'types': [
            {'$project': {'type_line': 1}},
            {'$group': {
               '_id': {
                  '$cond': [
                     {'$ifNull': ['$type_line', False]},
                     {'$arrayElemAt': [{'$split': ['$type_line', ' — ']}, 0]},
                     'Other'
                  ]
               },
               'count': {'$sum': 1}
            }}
         ]
      }}
   ]

   max_retries = 3
   for attempt in range(max_retries):
      try:
         result = list(collection.aggregate(pipeline))[0]
         break
      except OperationFailure as e:
         if 'TooManyRequests' in str(e) or '429' in str(e):
            wait = 2 ** attempt
            print(f'CosmosDB 429 error, retrying in {wait}s...')
            time.sleep(wait)
         else:
            print(f'Unexpected Mongo error: {e}')
            return jsonify({'error': 'Database error', 'details': str(e)}), 500
      except Exception as e:
         print(f'Unexpected error: {e}')
         return jsonify({'error': 'Unexpected error', 'details': str(e)}), 500
   else:
      return jsonify({'error': 'Too many requests, please try again later.'}), 429

   # Parse aggregation result
   total = result['total'][0]['count'] if result['total'] else 0
   color_counts = {'Colorless': 0, 'Many': 0}
   color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
   for doc in result['colors']:
      if doc['_id'] is None:
         color_counts['Colorless'] += doc['count']
      else:
         color_name = color_map.get(doc['_id'], 'Other')
         color_counts[color_name] = color_counts.get(color_name, 0) + doc['count']
   color_counts['Many'] = result['many'][0]['count'] if result['many'] else 0

   type_counts = {}
   for doc in result['types']:
      t = doc['_id'] or 'Other'
      if t not in ['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land']:
         t = 'Other'
      type_counts[t] = type_counts.get(t, 0) + doc['count']

   print(f'Summary: total={total}, color_counts={color_counts}, type_counts={type_counts}')
   return jsonify({
      'total': total,
      'color_counts': color_counts,
      'type_counts': type_counts
   })


@app.route('/regenerate-analysis')
def regenerate_analysis():
   try:
      import subprocess
      result = subprocess.run(['python', 'scripts/convert_notebook.py'],
                       capture_output=True, text=True, cwd=app.root_path)
      if result.returncode == 0:
         return "Analysis page regenerated successfully!", 200
      else:
         return f"Error regenerating analysis: {result.stderr}", 500
   except Exception as e:
      return f"Error regenerating analysis: {str(e)}", 500

if __name__ == '__main__':
   app.run()

# get price api call underway
# finalize fields for card info

# rn thinking of:
# card name
# card type
# card set
# card rarity
# card price
# card image
# card id (for db purposes)
# card colors
# card mana cost
# card text
# card flavor text
# card artist
# card number (in set)
# card power/toughness (if applicable)
# card loyalty (if applicable)
# card border color
# card legalities (in various formats)
# card release date
# card foil availability
# card non-foil availability
# card promo availability
# card reprint status
# card variations (if any)
# card related products (if any)
# card rulings (if any)
# card printings (other sets it has been printed in)
# card booster pack availability
# card price history (if available)
# card market price
# card low price
# card mid price
# card high price
# card trend (price trend over time)
# card currency (for price information)
# card language (if applicable)
# card condition (if applicable)
# card foil condition (if applicable)
# card signed status (if applicable)
# card altered status (if applicable)       

# test some d3.js stuff
# make a graph of price over time for a card
# make a graph of card popularity over time (if data available)
# make a graph of card printings over time
# make a graph of card legality over time (if data available)
# make a graph of card variations over time (if data available)

