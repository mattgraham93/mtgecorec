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

@app.route('/narrative')
def narrative():
   return render_template('narrative.html')

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
   # Get multi-color and exclusive params
   colors = request.args.getlist('colors')  # multiple colors
   exclusive_colors = request.args.get('exclusive_colors') == 'true'
   skip = (page - 1) * page_size
   print(f'Pagination params: page={page}, page_size={page_size}, skip={skip}')
   print(f'Filter params: color={color_filter}, type={type_filter}')
   print(f'Sort params: sort_by={sort_by}, sort_order={sort_order}')
   many = request.args.get('many') == 'true'
   # Build MongoDB query based on filters
   query = {}
   
   # Handle color filtering (single color for backward compatibility, or multiple colors)
   if colors:
      # Multiple colors mode
      color_codes = []
      for color in colors:
         if color in ['White', 'Blue', 'Black', 'Red', 'Green']:
            color_map = {'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'}
            color_codes.append(color_map[color])
      
      if exclusive_colors:
         # Exclusive: cards must have exactly these colors (and no others)
         if 'Colorless' in colors:
            query['$or'] = [
               {'colors': {'$exists': False}},
               {'colors': []},
               {'colors': None}
            ]
         else:
            query['colors'] = {'$all': color_codes, '$size': len(color_codes)}
      else:
         # Inclusive: cards must have at least one of these colors
         if 'Colorless' in colors:
            query['$or'] = [
               {'colors': {'$exists': False}},
               {'colors': []},
               {'colors': None},
               {'colors': {'$in': color_codes}}
            ]
         else:
            query['colors'] = {'$in': color_codes}
   elif color_filter:
      # Backward compatibility: single color filter
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
         query['$and'] = query.get('$and', []) + [
            {'$or': [
               {'type_line': {'$exists': False}},
               {'type_line': None},
               {'type_line': {'$not': {'$regex': '^(Creature|Instant|Sorcery|Enchantment|Artifact|Planeswalker|Land)'}}}
            ]}
         ]
      else:
         query['$and'] = query.get('$and', []) + [
            {'type_line': {'$exists': True}},
            {'type_line': {'$ne': None}},
            {'type_line': {'$regex': f'^{type_filter}'}}
         ]
   print(f'MongoDB query: {query}')
   
   # More efficient approach: get unique card names first, then paginate
   name_pipeline = [
      {'$match': query},
      {'$group': {'_id': '$name'}},  # Just get unique names
      {'$sort': {'_id': 1}},  # Sort by name
      {'$skip': skip},
      {'$limit': page_size},
      {'$project': {'name': '$_id', '_id': 0}}
   ]
   
   # Get total count more efficiently
   total_pipeline = [
      {'$match': query},
      {'$group': {'_id': '$name'}},
      {'$count': 'total'}
   ]
   
   try:
      # Get paginated card names
      name_results = list(collection.aggregate(name_pipeline))
      card_names = [doc['name'] for doc in name_results]
      
      # Get total count
      total_result = list(collection.aggregate(total_pipeline))
      total = total_result[0]['total'] if total_result else 0
      
      # Now get full card details for these specific cards
      if card_names:
         # Define sort direction
         sort_direction = 1 if sort_order == 'asc' else -1
         
         cards_pipeline = [
            {'$match': {
               'name': {'$in': card_names},
               **query  # Apply the same filters
            }},
            {'$group': {
               '_id': '$name',
               'card': {'$first': '$$ROOT'},
               'set_count': {'$sum': 1},
               'sets': {'$push': {
                  'set': '$set',
                  'rarity': '$rarity',
                  'price': '$price',
                  'image_uris': '$image_uris',
                  'artist': '$artist'
               }}
            }},
            {'$project': {
               '_id': 0,
               'name': '$_id',
               'type_line': '$card.type_line',
               'colors': '$card.colors',
               'mana_cost': '$card.mana_cost',
               'artist': '$card.artist',
               'set_count': 1,
               'sets': 1,
               # Use the first set's data for display
               'set': {'$arrayElemAt': ['$sets.set', 0]},
               'rarity': {'$arrayElemAt': ['$sets.rarity', 0]},
               'price': {'$arrayElemAt': ['$sets.price', 0]},
               'image_uris': {'$arrayElemAt': ['$sets.image_uris', 0]}
            }},
            {'$sort': {sort_by: sort_direction}}
         ]
         
         cards = list(collection.aggregate(cards_pipeline))
      else:
         cards = []
         
   except Exception as e:
      print(f'Error in aggregation: {e}')
      return jsonify({'error': 'Database aggregation error', 'details': str(e)}), 500
   
   print(f'Total unique cards matching filters: {total}')
   print(f'Returning {len(cards)} unique cards for this page')
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
   # Get multi-color and exclusive params
   colors = request.args.getlist('colors')
   exclusive_colors = request.args.get('exclusive_colors') == 'true'

   # Build MongoDB query based on filters (same as /api/cards)
   query = {}
   
   # Handle color filtering (single color for backward compatibility, or multiple colors)
   if colors:
      # Multiple colors mode
      color_codes = []
      for color in colors:
         if color in ['White', 'Blue', 'Black', 'Red', 'Green']:
            color_map = {'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'}
            color_codes.append(color_map[color])
      
      if exclusive_colors:
         # Exclusive: cards must have exactly these colors (and no others)
         if 'Colorless' in colors:
            query['$or'] = [
               {'colors': {'$exists': False}},
               {'colors': []},
               {'colors': None}
            ]
         else:
            query['colors'] = {'$all': color_codes, '$size': len(color_codes)}
      else:
         # Inclusive: cards must have at least one of these colors
         if 'Colorless' in colors:
            query['$or'] = [
               {'colors': {'$exists': False}},
               {'colors': []},
               {'colors': None},
               {'colors': {'$in': color_codes}}
            ]
         else:
            query['colors'] = {'$in': color_codes}
   elif color_filter:
      # Backward compatibility: single color filter
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
         query['$and'] = query.get('$and', []) + [
            {'$or': [
               {'type_line': {'$exists': False}},
               {'type_line': None},
               {'type_line': {'$not': {'$regex': '^(Creature|Instant|Sorcery|Enchantment|Artifact|Planeswalker|Land)'}}}
            ]}
         ]
      else:
         query['$and'] = query.get('$and', []) + [
            {'type_line': {'$exists': True}},
            {'type_line': {'$ne': None}},
            {'type_line': {'$regex': f'^{type_filter}'}}
         ]

   print(f'MongoDB summary query: {query}')

   # Aggregation pipeline for total and combined color-type counts (using unique cards)
   pipeline = [
      {'$match': query},
      {'$facet': {
         'total': [
            {'$group': {'_id': '$name'}},
            {'$count': 'count'}
         ],
         'combined': [
            {'$project': {
               'name': 1,
               'colors': 1,
               'type_line': 1
            }},
            {'$unwind': {
               'path': '$colors',
               'preserveNullAndEmptyArrays': True
            }},
            {'$group': {
               '_id': {
                  'name': '$name',
                  'color': {
                     '$cond': [
                        {'$ifNull': ['$colors', False]},
                        {
                           '$switch': {
                              'branches': [
                                 {'case': {'$eq': ['$colors', 'W']}, 'then': 'White'},
                                 {'case': {'$eq': ['$colors', 'U']}, 'then': 'Blue'},
                                 {'case': {'$eq': ['$colors', 'B']}, 'then': 'Black'},
                                 {'case': {'$eq': ['$colors', 'R']}, 'then': 'Red'},
                                 {'case': {'$eq': ['$colors', 'G']}, 'then': 'Green'}
                              ],
                              'default': 'Other'
                           }
                        },
                        'Colorless'
                     ]
                  },
                  'type': {
                     '$cond': [
                        {'$ifNull': ['$type_line', False]},
                        {'$arrayElemAt': [{'$split': ['$type_line', ' — ']}, 0]},
                        'Other'
                     ]
                  }
               },
               'count': {'$sum': 1}
            }},
            {'$group': {
               '_id': {
                  'color': '$_id.color',
                  'type': '$_id.type'
               },
               'count': {'$sum': 1}
            }},
            {'$project': {
               '_id': 0,
               'color': '$_id.color',
               'type': '$_id.type',
               'count': 1
            }}
         ],
         'colors': [
            {'$project': {'name': 1, 'colors': 1}},
            {'$unwind': {
               'path': '$colors',
               'preserveNullAndEmptyArrays': True
            }},
            {'$group': {
               '_id': {
                  'name': '$name',
                  'color': '$colors'
               }
            }},
            {'$group': {
               '_id': '$_id.color',
               'count': {'$sum': 1}
            }}
         ],
         'many': [
            {'$project': {'name': 1, 'colors': 1}},
            {'$match': {'colors.1': {'$exists': True}}},
            {'$group': {'_id': '$name'}},
            {'$count': 'count'}
         ],
         'types': [
            {'$project': {'name': 1, 'type_line': 1}},
            {'$group': {
               '_id': {
                  'name': '$name',
                  'type': {
                     '$cond': [
                        {'$ifNull': ['$type_line', False]},
                        {'$arrayElemAt': [{'$split': ['$type_line', ' — ']}, 0]},
                        'Other'
                     ]
                  }
               }
            }},
            {'$group': {
               '_id': '$_id.type',
               'count': {'$sum': 1}
            }}
         ],
         'sets': [
            {'$group': {
               '_id': '$set',
               'unique_cards': {'$addToSet': '$name'}
            }},
            {'$project': {
               '_id': 0,
               'set': '$_id',
               'unique_cards_count': {'$size': '$unique_cards'}
            }},
            {'$match': {'unique_cards_count': {'$gt': 30}}},  # Only sets with more than 30 cards
            {'$sort': {'unique_cards_count': 1}}  # Ascending order
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
   
   # Combined color-type aggregations
   combined_aggregations = result['combined'] if 'combined' in result else []
   
   # Legacy color counts (keep for backward compatibility) - now counting unique cards
   color_counts = {'Colorless': 0, 'Many': 0}
   color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
   for doc in result['colors']:
      if doc['_id'] is None:
         color_counts['Colorless'] += doc['count']
      else:
         color_name = color_map.get(doc['_id'], 'Other')
         color_counts[color_name] = color_counts.get(color_name, 0) + doc['count']
   color_counts['Many'] = result['many'][0]['count'] if result['many'] else 0

   # Legacy type counts (keep for backward compatibility) - now counting unique cards
   type_counts = {}
   for doc in result['types']:
      t = doc['_id'] or 'Other'
      if t not in ['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land']:
         t = 'Other'
      type_counts[t] = type_counts.get(t, 0) + doc['count']

   # Set statistics
   sets_data = result['sets'] if 'sets' in result else []
   if sets_data:
      print(f'First 3 sets: {sets_data[:3]}')

   print(f'Summary: total={total} unique cards, combined_aggregations_count={len(combined_aggregations)}, color_counts={color_counts}, type_counts={type_counts}, sets_count={len(sets_data)}')
   return jsonify({
      'total': total,
      'combined_aggregations': combined_aggregations,
      'color_counts': color_counts,
      'type_counts': type_counts,
      'sets': sets_data
   })


@app.route('/commander')
def commander_deck_builder():
   """Commander deck builder page."""
   return render_template('commander.html')

@app.route('/api/commanders/search')
def api_search_commanders():
   """Search for commanders by name."""
   query = request.args.get('q', '')
   if len(query) < 2:
      return jsonify({'commanders': []})
   
   try:
      client = cosmos_driver.get_mongo_client()
      collection = cosmos_driver.get_collection(client, 'mtgecorec', 'cards')
      
      # Search for legendary creatures and planeswalkers
      search_query = {
         'name': {'$regex': query, '$options': 'i'},
         'legalities.commander': {'$in': ['legal', 'restricted']},
         '$or': [
            {'type_line': {'$regex': 'Legendary.*Creature', '$options': 'i'}},
            {'type_line': {'$regex': 'Legendary.*Planeswalker', '$options': 'i'}},
            {'oracle_text': {'$regex': 'can be your commander', '$options': 'i'}}
         ]
      }
      
      commanders = list(collection.find(search_query, {
         'name': 1, 'mana_cost': 1, 'colors': 1, 'type_line': 1,
         'oracle_text': 1, 'power': 1, 'toughness': 1, 'image_uris': 1,
         '_id': 0
      }).limit(20))
      
      return jsonify({'commanders': commanders})
      
   except Exception as e:
      print(f'Error searching commanders: {e}')
      return jsonify({'error': str(e)}), 500

@app.route('/api/commanders/<commander_name>/recommendations')
def api_get_commander_recommendations(commander_name):
   """Get deck recommendations for a specific commander."""
   budget_limit = request.args.get('budget', type=float)
   power_level = request.args.get('power_level', 'casual')
   
   if not commander_name:
      return jsonify({'error': 'Commander name required'}), 400
   
   try:
      # Import here to avoid circular imports
      import sys
      import os
      current_dir = os.path.dirname(os.path.abspath(__file__))
      sys.path.append(os.path.join(current_dir, 'data_engine'))
      from commander_recommender import CommanderRecommendationEngine, RecommendationRequest
      
      # Create recommendation engine
      engine = CommanderRecommendationEngine(use_ai=False)  # Start without AI for speed
      
      # Create request
      req = RecommendationRequest(
         commander_name=commander_name,
         budget_limit=budget_limit,
         power_level=power_level
      )
      
      # Generate recommendations (this is async, so we'll need to handle it)
      import asyncio
      
      # Run in thread to avoid blocking
      def run_async():
         loop = asyncio.new_event_loop()
         asyncio.set_event_loop(loop)
         try:
            return loop.run_until_complete(engine.generate_recommendations(req))
         finally:
            loop.close()
      
      recommendations = run_async()
      
      # Convert to JSON-serializable format
      result = {
         'commander': {
            'name': recommendations.commander.name,
            'color_identity': recommendations.commander.color_identity.to_string(),
            'colors': list(recommendations.commander.color_identity.colors),
            'mana_cost': recommendations.commander.mana_cost
         },
         'recommendations': [{
            'name': rec.card_name,
            'confidence': rec.confidence_score,
            'synergy_score': rec.synergy_score,
            'category': rec.category,
            'reasons': rec.reasons[:2],  # Limit reasons for response size
            'estimated_price': rec.estimated_price
         } for rec in recommendations.recommendations[:50]],  # Top 50
         'mana_base': [{
            'name': rec.card_name,
            'category': rec.category,
            'estimated_price': rec.estimated_price
         } for rec in recommendations.mana_base_suggestions],
         'strategy': recommendations.deck_strategy,
         'power_level': recommendations.power_level_assessment,
         'total_cost': recommendations.estimated_total_cost
      }
      
      return jsonify(result)
      
   except Exception as e:
      print(f'Error generating recommendations: {e}')
      import traceback
      traceback.print_exc()
      return jsonify({'error': str(e)}), 500

@app.route('/api/commanders/<commander_name>/ai-analysis')
def api_get_ai_analysis(commander_name):
   """Get AI analysis for a commander using Perplexity."""
   current_deck = request.args.getlist('deck[]')  # Cards already in deck
   
   if not commander_name:
      return jsonify({'error': 'Commander name required'}), 400
   
   try:
      import sys
      import os
      current_dir = os.path.dirname(os.path.abspath(__file__))
      sys.path.append(os.path.join(current_dir, 'data_engine'))
      from perplexity_client import PerplexityClient
      
      client = PerplexityClient()
      analysis = client.analyze_commander_synergies(commander_name, current_deck)
      
      return jsonify(analysis)
      
   except ValueError as e:
      return jsonify({'error': 'AI analysis unavailable - API key not configured'}), 503
   except Exception as e:
      print(f'Error in AI analysis: {e}')
      return jsonify({'error': str(e)}), 500

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

