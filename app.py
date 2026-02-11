import os
from dotenv import load_dotenv
from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for, jsonify, session, flash)
from functools import lru_cache
from datetime import datetime, timedelta
import logging

# Load environment variables
load_dotenv()
# Import Cosmos DB driver
from core.data_engine import cosmos_driver
# Import authentication components
from core.data_engine.user_manager import UserManager
from core.data_engine.auth_decorators import login_required, ai_query_required

app = Flask(__name__, template_folder='templates', static_folder='static')

# Set secret key for sessions (in production, use environment variable)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production-very-long-secret')

# Configure session to be more permissive for development
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Allow cookies over HTTP in development
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  # More permissive for development
)

# Initialize user manager
user_manager = UserManager()

# Suppress werkzeug logging for internal polling endpoints
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Pricing cache: {commander_name: (timestamp, data)}
_pricing_cache = {}
_PRICING_CACHE_TTL = 300  # 5 minutes cache TTL

def get_cached_pricing(commander_name):
    """Get pricing from cache if available and not expired."""
    if commander_name in _pricing_cache:
        timestamp, data = _pricing_cache[commander_name]
        if datetime.now() - timestamp < timedelta(seconds=_PRICING_CACHE_TTL):
            return data
        else:
            # Cache expired, remove it
            del _pricing_cache[commander_name]
    return None

def set_cached_pricing(commander_name, data):
    """Store pricing in cache with timestamp."""
    _pricing_cache[commander_name] = (datetime.now(), data)

# Pricing helper functions
def get_latest_pricing_data(card_name):
    """Get the latest pricing data for a card by name using the actual database structure."""
    try:
        client = cosmos_driver.get_mongo_client()
        
        # First, get the card's scryfall ID
        cards_collection = client.mtgecorec.cards
        card = cards_collection.find_one({'name': card_name}, {'id': 1})
        
        if not card:
            return None
            
        scryfall_id = card['id']
        
        # Get the pricing collection (correct name from notebook)
        pricing_collection = client.mtgecorec.card_pricing_daily
        
        # Find pricing record for this card using scryfall_id (without sorting to avoid index issues)
        pricing_data = pricing_collection.find_one(
            {'scryfall_id': scryfall_id}
        )
        
        if pricing_data:
            # Extract pricing using the same logic as your notebook
            usd_price = None
            usd_foil_price = None
            date_value = pricing_data.get('date')
            
            # Strategy 1: Extract from 'prices' dictionary
            prices_dict = pricing_data.get('prices', {})
            if isinstance(prices_dict, dict):
                usd_price = prices_dict.get('usd')
                usd_foil_price = prices_dict.get('usd_foil')
            
            # Strategy 2: Use price_usd column if prices dict didn't work
            if not usd_price:
                usd_price = pricing_data.get('price_usd')
            
            # Strategy 3: Extract from price_type/price_value structure
            if not usd_price and pricing_data.get('price_type') == 'usd':
                usd_price = pricing_data.get('price_value')
            
            return {
                'usd': usd_price,
                'usd_foil': usd_foil_price,
                'eur': prices_dict.get('eur') if isinstance(prices_dict, dict) else None,
                'date': date_value
            }
        return None
        
    except Exception as e:
        print(f'Error fetching pricing data for {card_name}: {e}')
        return None

def get_all_versions_pricing_data(card_name):
    """Get pricing data for all versions of a card and return the lowest price info."""
    try:
        client = cosmos_driver.get_mongo_client()
        
        # Get all scryfall IDs for this card name with limit to reduce load
        cards_collection = client.mtgecorec.cards
        all_cards = list(cards_collection.find({'name': card_name}, {'id': 1, 'set_name': 1, 'set': 1}).limit(10))
        
        if not all_cards:
            return None
        
        # Get all pricing data in one query to avoid rate limits
        pricing_collection = client.mtgecorec.card_pricing_daily
        scryfall_ids = [card['id'] for card in all_cards]
        all_pricing = list(pricing_collection.find({'scryfall_id': {'$in': scryfall_ids}}).limit(20))
        
        print(f"DEBUG: Found {len(all_cards)} cards and {len(all_pricing)} pricing records for {card_name}")
        
        valid_prices = []
        for pricing_data in all_pricing:
            # Extract pricing using the same logic as get_latest_pricing_data
            usd_price = None
            usd_foil_price = None
            
            # Strategy 1: Extract from 'prices' dictionary
            prices_dict = pricing_data.get('prices', {})
            if isinstance(prices_dict, dict):
                usd_price = prices_dict.get('usd')
                usd_foil_price = prices_dict.get('usd_foil')
            
            # Strategy 2: Use price_usd column if prices dict didn't work
            if not usd_price:
                usd_price = pricing_data.get('price_usd')
            
            # Strategy 3: Extract from price_type/price_value structure
            if not usd_price and pricing_data.get('price_type') == 'usd':
                usd_price = pricing_data.get('price_value')
            
            if usd_price and not is_nan(float(usd_price)) and float(usd_price) > 0:
                valid_prices.append({
                    'usd': float(usd_price),
                    'usd_foil': float(usd_foil_price) if usd_foil_price and not is_nan(float(usd_foil_price)) else None,
                    'date': pricing_data.get('date'),
                    'scryfall_id': pricing_data.get('scryfall_id')
                })
        
        print(f"DEBUG: Found {len(valid_prices)} valid prices: {[p['usd'] for p in valid_prices]}")
        
        if valid_prices:
            # Find lowest non-foil price
            lowest_price = min(valid_prices, key=lambda x: x['usd'])
            print(f"DEBUG: Lowest price found: ${lowest_price['usd']:.2f} from {lowest_price.get('scryfall_id', 'unknown')}")
            
            # Find lowest foil price if any
            foil_prices = [p for p in valid_prices if p['usd_foil']]
            lowest_foil = min(foil_prices, key=lambda x: x['usd_foil']) if foil_prices else None
            
            return {
                'usd': lowest_price['usd'],
                'usd_foil': lowest_foil['usd_foil'] if lowest_foil else None,
                'date': lowest_price['date'],
                'total_versions': len(all_cards)
            }
        
        return None
        
    except Exception as e:
        print(f'Error fetching all versions pricing for {card_name}: {e}')
        # Fallback: try to get at least one pricing record
        try:
            single_pricing = get_latest_pricing_data(card_name)
            if single_pricing:
                return {
                    'usd': single_pricing['usd'],
                    'usd_foil': single_pricing['usd_foil'],
                    'date': single_pricing['date'],
                    'total_versions': 1
                }
        except:
            pass
        return None

def is_nan(value):
    """Helper function to check if a value is NaN."""
    try:
        float_val = float(value)
        return float_val != float_val  # NaN is the only value that is not equal to itself
    except (ValueError, TypeError):
        return True

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
   if request.method == 'POST':
      username = request.form.get('username')
      password = request.form.get('password')
      
      if not username or not password:
         flash('Username and password are required', 'error')
         return render_template('login.html')
      
      try:
         result = user_manager.authenticate_user(username, password)
         if result and result.get('success'):
            user = result['user']
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['user_email'] = user['email']
            session.permanent = True  # Make session permanent
            print(f"Login successful for {user['username']}, session: {dict(session)}")
            flash(f'Welcome back, {user["username"]}!', 'success')
            
            # Check if user was trying to access a specific page
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('commander_deck_builder'))  # Go directly to commander after login
         else:
            flash('Invalid username or password', 'error')
      except Exception as e:
         print(f'Login error: {e}')
         flash('Login failed. Please try again.', 'error')
   
   return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
   if request.method == 'POST':
      username = request.form.get('username')
      email = request.form.get('email')
      password = request.form.get('password')
      confirm_password = request.form.get('confirm_password')
      
      # Validate inputs
      if not all([username, email, password, confirm_password]):
         flash('All fields are required', 'error')
         return render_template('register.html')
      
      if password != confirm_password:
         flash('Passwords do not match', 'error')
         return render_template('register.html')
      
      if len(password) < 6:
         flash('Password must be at least 6 characters long', 'error')
         return render_template('register.html')
      
      if len(username) < 3 or len(username) > 30:
         flash('Username must be between 3-30 characters', 'error')
         return render_template('register.html')
      
      try:
         # Create user
         result = user_manager.register_user(username, email, password)
         if result and result.get('success'):
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
         else:
            error_msg = result.get('message', 'Username or email may already exist.') if result else 'Registration failed.'
            flash(f'Registration failed. {error_msg}', 'error')
      except Exception as e:
         print(f'Registration error: {e}')
         flash('Registration failed. Please try again.', 'error')
   
   return render_template('register.html')

@app.route('/logout')
def logout():
   username = session.get('username', 'User')
   session.clear()
   flash(f'Goodbye, {username}!', 'info')
   return redirect(url_for('index'))

@app.route('/status')
def status():
   """Simple status check to see if user is logged in."""
   if 'user_id' in session:
      return jsonify({
         'logged_in': True,
         'username': session.get('username'),
         'user_id': session.get('user_id'),
         'session_data': dict(session)
      })
   else:
      return jsonify({
         'logged_in': False,
         'session_data': dict(session)
      })

@app.route('/profile')
@login_required
def profile():
   """User profile page showing account info and usage."""
   try:
      user_id = session.get('user_id')
      user_data = user_manager.get_user_by_id(user_id)
      
      if not user_data:
         flash('User not found', 'error')
         return redirect(url_for('login'))
      
      # Get current month's query count
      query_count = user_manager.get_monthly_query_count(user_id)
      query_limit = user_data.get('monthly_query_limit', 50)
      
      return render_template('profile.html', 
                           user=user_data,
                           query_count=query_count,
                           query_limit=query_limit,
                           queries_remaining=max(0, query_limit - query_count))
   except Exception as e:
      print(f'Profile error: {e}')
      flash('Error loading profile', 'error')
      return redirect(url_for('index'))

# Main page routes
@app.route('/')
def index():
   print(f'Request for index page received, session: {dict(session)}')
   return render_template('construction.html')

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

@app.route('/construction')
def under_construction():
   """Under construction page - not linked in navigation."""
   return render_template('construction.html')

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
@login_required
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
      
      # Search for legendary creatures and planeswalkers - get unique commanders only
      search_query = {
         'name': {'$regex': query, '$options': 'i'},
         'legalities.commander': {'$in': ['legal', 'restricted']},
         '$or': [
            {'type_line': {'$regex': 'Legendary.*Creature', '$options': 'i'}},
            {'type_line': {'$regex': 'Legendary.*Planeswalker', '$options': 'i'}},
            {'oracle_text': {'$regex': 'can be your commander', '$options': 'i'}}
         ]
      }
      
      # Use aggregation pipeline to get unique commanders with best image
      commanders_pipeline = [
         {'$match': search_query},
         {'$group': {
            '_id': '$name',
            'commander': {'$first': '$$ROOT'},
            'best_image': {
               '$first': {
                  '$cond': [
                     {'$ifNull': ['$image_uris.normal', False]},
                     '$image_uris',
                     None
                  ]
               }
            }
         }},
         {'$project': {
            '_id': 0,
            'name': '$_id',
            'scryfall_id': '$commander.id',
            'mana_cost': '$commander.mana_cost',
            'colors': '$commander.colors',
            'type_line': '$commander.type_line',
            'oracle_text': '$commander.oracle_text',
            'power': '$commander.power',
            'toughness': '$commander.toughness',
            'image_uris': {
               '$cond': [
                  {'$ifNull': ['$best_image', False]},
                  '$best_image',
                  '$commander.image_uris'
               ]
            }
         }},
         {'$sort': {'name': 1}},
         {'$limit': 20}
      ]
      
      commanders = list(collection.aggregate(commanders_pipeline))
      
# Don't load pricing in search results to avoid rate limiting
      # Pricing will be loaded when a specific commander is selected
      return jsonify({'commanders': commanders})
      
   except Exception as e:
      print(f'Error searching commanders: {e}')
      return jsonify({'error': str(e)}), 500

@app.route('/api/commanders/<commander_name>/pricing')
def api_get_commander_pricing(commander_name):
   """Get pricing data for a specific commander (cached to reduce DB load)."""
   try:
      # Check cache first
      cached_data = get_cached_pricing(commander_name)
      if cached_data is not None:
         return jsonify({'pricing': cached_data})
      
      # Not in cache, get from database
      pricing_data = get_all_versions_pricing_data(commander_name)
      
      # Store in cache for future requests
      set_cached_pricing(commander_name, pricing_data)
      
      return jsonify({'pricing': pricing_data})
   except Exception as e:
      print(f'Error getting pricing for {commander_name}: {e}')
      return jsonify({'pricing': None})

@app.route('/api/commanders/<commander_name>/printings')
def api_get_commander_printings(commander_name):
   """Get all printings/versions of a specific commander."""
   try:
      client = cosmos_driver.get_mongo_client()
      collection = cosmos_driver.get_collection(client, 'mtgecorec', 'cards')
      
      # Get all versions of this commander
      printings_query = {
         'name': commander_name,
         'legalities.commander': {'$in': ['legal', 'restricted']},
         '$or': [
            {'type_line': {'$regex': 'Legendary.*Creature', '$options': 'i'}},
            {'type_line': {'$regex': 'Legendary.*Planeswalker', '$options': 'i'}},
            {'oracle_text': {'$regex': 'can be your commander', '$options': 'i'}}
         ]
      }
      
      # Limit results and use simpler projection to reduce database load
      printings = list(collection.find(printings_query, {
         '_id': 0,  # Exclude ObjectId to avoid JSON serialization issues
         'name': 1,
         'set_name': 1,
         'set': 1,
         'collector_number': 1,
         'rarity': 1,
         'image_uris': 1,
         'prices': 1,  # Keep original Scryfall prices as fallback
         'released_at': 1,
         'id': 1,  # Need scryfall_id for pricing lookup
         'artist': 1
      }).sort([('released_at', -1)]).limit(50))  # Limit to 50 versions max
      
      # Get all pricing data in a single query to avoid rate limits
      try:
         pricing_collection = client.mtgecorec.card_pricing_daily
         scryfall_ids = [p['id'] for p in printings if 'id' in p]
         
         if scryfall_ids:
            # Get all pricing data for these cards in one query
            all_pricing = list(pricing_collection.find({'scryfall_id': {'$in': scryfall_ids}}))
         
         # Create a lookup dict for fast access
         pricing_lookup = {}
         for pricing_data in all_pricing:
            scryfall_id = pricing_data.get('scryfall_id')
            if scryfall_id:
               # Extract pricing using the same logic as get_latest_pricing_data
               usd_price = None
               usd_foil_price = None
               
               # Strategy 1: Extract from 'prices' dictionary
               prices_dict = pricing_data.get('prices', {})
               if isinstance(prices_dict, dict):
                  usd_price = prices_dict.get('usd')
                  usd_foil_price = prices_dict.get('usd_foil')
               
               # Strategy 2: Use price_usd column if prices dict didn't work
               if not usd_price:
                  usd_price = pricing_data.get('price_usd')
               
               # Strategy 3: Extract from price_type/price_value structure
               if not usd_price and pricing_data.get('price_type') == 'usd':
                  usd_price = pricing_data.get('price_value')
               
               # Store the pricing data
               if usd_price and not is_nan(float(usd_price)):
                  pricing_lookup[scryfall_id] = {
                     'usd': float(usd_price),
                     'usd_foil': float(usd_foil_price) if usd_foil_price and not is_nan(float(usd_foil_price)) else None,
                     'date': pricing_data.get('date')
                  }
         
            # Apply pricing data to each printing
            for printing in printings:
               if 'id' in printing and printing['id'] in pricing_lookup:
                  printing['database_price'] = pricing_lookup[printing['id']]
               else:
                  pass  # Use Scryfall fallback

         else:
            pass  # No scryfall_ids found
      except Exception as pricing_error:
         # Continue without pricing data - use Scryfall fallback prices
         pass
      
      # Get the primary version (most recent or best image)
      primary_version = None
      if printings:
         # Prefer versions with good images, then most recent
         primary_version = next((p for p in printings if p.get('image_uris', {}).get('normal')), printings[0])
      
      return jsonify({
         'commander': primary_version,
         'printings': printings,
         'total_versions': len(printings)
      })
      
   except Exception as e:
      print(f'Error getting commander printings: {e}')
      return jsonify({'error': str(e)}), 500

@app.route('/api/commanders/<commander_name>/recommendations')
@ai_query_required
def api_get_commander_recommendations(commander_name):
   """Get deck recommendations for a specific commander with optional AI-powered personalization."""
   budget_limit = request.args.get('budget', type=float)
   power_level = request.args.get('power_level', 'casual')
   preferred_mechanics = request.args.get('preferred_mechanics', '').strip()
   
   if not commander_name:
      return jsonify({'error': 'Commander name required'}), 400
   
   try:
      # Import here to avoid circular imports
      import sys
      import os
      from core.data_engine.commander_recommender import CommanderRecommendationEngine, RecommendationRequest
      
      # Create recommendation engine with AI if preferred mechanics are provided
      use_ai = bool(preferred_mechanics)
      engine = CommanderRecommendationEngine(use_ai=use_ai)
      
      # Create request
      req = RecommendationRequest(
         commander_name=commander_name,
         budget_limit=budget_limit,
         power_level=power_level,
         preferred_mechanics=preferred_mechanics if preferred_mechanics else None
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
            'scryfall_id': rec.card_data.get('id', ''),  # Scryfall uses 'id' field, not 'scryfall_id'
            'confidence': rec.confidence_score,
            'synergy_score': rec.synergy_score,
            'category': rec.category,
            'reasons': rec.reasons[:2],  # Limit reasons for response size
            'estimated_price': rec.estimated_price,
            'ai_suggested': getattr(rec, 'ai_suggested', False),
            'primary_version': {
               'set': rec.card_data.get('set', ''),
               'set_name': rec.card_data.get('set_name', ''),
               'collector_number': rec.card_data.get('collector_number', ''),
               'rarity': rec.card_data.get('rarity', 'common'),
               'image_uris': rec.card_data.get('image_uris', {}),
               'scryfall_id': rec.card_data.get('id', ''),  # Scryfall uses 'id' field
               'price': rec.card_data.get('price', 0)
            },
            'all_versions': [{
               'set': v.get('set', ''),
               'set_name': v.get('set_name', ''),
               'collector_number': v.get('collector_number', ''),
               'rarity': v.get('rarity', 'common'),
               'image_uris': v.get('image_uris', {}),
               'scryfall_id': v.get('id', ''),  # Scryfall uses 'id' field
               'price': v.get('price', 0),
               'released_at': v.get('released_at', '')
            } for v in (rec.all_versions or [rec.card_data])[:10]]  # Limit to 10 versions
         } for rec in recommendations.recommendations[:50]],  # Top 50
         'mana_base': [{
            'name': rec.card_name,
            'scryfall_id': rec.card_data.get('id', ''),  # Scryfall uses 'id' field
            'category': rec.category,
            'estimated_price': rec.estimated_price,
            'primary_version': {
               'set': rec.card_data.get('set', ''),
               'set_name': rec.card_data.get('set_name', ''),
               'collector_number': rec.card_data.get('collector_number', ''),
               'rarity': rec.card_data.get('rarity', 'common'),
               'image_uris': rec.card_data.get('image_uris', {}),
               'scryfall_id': rec.card_data.get('id', ''),  # Scryfall uses 'id' field
               'price': rec.card_data.get('price', 0)
            },
            'all_versions': [{
               'set': v.get('set', ''),
               'set_name': v.get('set_name', ''),
               'collector_number': v.get('collector_number', ''),
               'rarity': v.get('rarity', 'common'),
               'image_uris': v.get('image_uris', {}),
               'scryfall_id': v.get('id', ''),  # Scryfall uses 'id' field
               'price': v.get('price', 0),
               'released_at': v.get('released_at', '')
            } for v in (rec.all_versions or [rec.card_data])[:10]]  # Limit to 10 versions
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

@app.route('/api/recommendations/progress')
def api_get_recommendation_progress():
   """Get current progress of recommendation generation."""
   try:
      from core.data_engine.commander_recommender import get_recommendation_progress
      progress = get_recommendation_progress()
      return jsonify(progress.get_current_step())
   except Exception as e:
      print(f'Error getting progress: {e}')
      return jsonify({'error': str(e)}), 500

@app.route('/api/commanders/<commander_name>/ai-analysis')
@ai_query_required
def api_get_ai_analysis(commander_name):
   """Get AI analysis for a commander using Perplexity."""
   current_deck = request.args.getlist('deck[]')  # Cards already in deck
   
   if not commander_name:
      return jsonify({'error': 'Commander name required'}), 400
   
   try:
      import sys
      import os
      from core.data_engine.perplexity_client import PerplexityClient
      
      # Temporarily disabled to save costs - AI card recommendations still active
      # client = PerplexityClient()
      # analysis = client.analyze_commander_synergies(commander_name, current_deck)
      
      # Return simple message instead of expensive analysis
      analysis = {
         'analysis': 'AI analysis temporarily disabled to reduce costs. Card recommendations with AI matching are still active!',
         'summary': f'{commander_name} analysis - focusing on cost-effective AI card recommendations.',
         'recommendations': [],
         'win_conditions': [],
         'synergy_categories': []
      }
      
      return jsonify(analysis)
      
   except ValueError as e:
      return jsonify({'error': 'AI analysis unavailable - API key not configured'}), 503
   except Exception as e:
      print(f'Error in AI analysis: {e}')
      return jsonify({'error': str(e)}), 500

@app.route('/api/commanders/<commander_name>/analysis-summary', methods=['POST'])
@ai_query_required
def api_generate_analysis_summary(commander_name):
   """Generate an executive summary of all analysis data using Perplexity."""
   
   try:
      data = request.get_json()
      existing_analysis = data.get('existing_analysis', '')
      recommendations_data = data.get('recommendations_data', {})
      
      if not commander_name:
         return jsonify({'error': 'Commander name required'}), 400
      
      # Import Perplexity client
      import sys
      import os
      from core.data_engine.perplexity_client import PerplexityClient
      
      client = PerplexityClient()
      
      # Create comprehensive summary prompt
      summary_prompt = f"""
      I need you to create a concise executive summary of a Magic: The Gathering Commander deck analysis.
      
      **Commander**: {commander_name}
      **Strategy**: {recommendations_data.get('strategy', 'Unknown')}
      **Power Level**: {recommendations_data.get('power_level', 'Unknown')}
      **Total Recommendations**: {recommendations_data.get('total_recommendations', 0)} cards
      
      **Detailed Analysis**:
      {existing_analysis[:2000]}  # Limit to prevent token overflow
      
      Please provide a brief executive summary (3-4 paragraphs max) that covers:
      
      1. **Deck Identity**: What this commander does and its core strategy
      2. **Key Synergies**: The most important card interactions and engines  
      3. **Strengths & Weaknesses**: What the deck does well and potential vulnerabilities
      4. **Play Pattern**: How games typically unfold with this commander
      
      Keep it concise but informative - this is for someone who wants to quickly understand the deck without reading the full analysis.
      """
      
      # Generate summary using Chat API (no search needed for summary)
      messages = [{
         "role": "system",
         "content": """You are an expert MTG Commander analyst who excels at distilling complex 
         deck analysis into clear, actionable executive summaries. Focus on the most important 
         strategic insights and practical implications."""
      }, {
         "role": "user", 
         "content": summary_prompt
      }]
      
      response = client._make_request_with_retry(messages, model="sonar")
      
      return jsonify({
         'commander': commander_name,
         'summary': response['choices'][0]['message']['content'],
         'citations': response.get('citations', []),
         'success': True
      })
      
   except Exception as e:
      print(f'Error generating analysis summary: {e}')
      return jsonify({'error': str(e)}), 500


# ===================================
# DECK MANAGEMENT API ENDPOINTS
# ===================================

@app.route('/api/decks', methods=['POST'])
@login_required
def create_deck():
    """Create a new deck."""
    try:
        user_id = session.get('user_id')
        data = request.json
        
        # Validate input
        if not data.get('deck_name'):
            return jsonify({'error': 'Validation error', 'message': 'Deck name is required'}), 400
        
        if not data.get('commander') or not data['commander'].get('scryfall_id'):
            return jsonify({'error': 'Validation error', 'message': 'Commander is required'}), 400
        
        # NEW: Validate cards array is not empty
        cards = data.get('cards', [])
        if not cards or len(cards) == 0:
            print(f'[WARNING] Deck save attempt with empty cards array')
            print(f'  Deck name: {data.get("deck_name")}')
            print(f'  Commander: {data.get("commander", {}).get("name")}')
            print(f'  Cards: {cards}')
            return jsonify({
                'error': 'Validation error', 
                'message': 'Deck must have at least one card. Please get recommendations first.'
            }), 400
        
        print(f'[DEBUG] Creating deck: {data.get("deck_name")}')
        print(f'  Commander: {data["commander"]["name"]}')
        print(f'  Cards count: {len(cards)}')
        print(f'  User: {user_id}')
        
        # Check deck limit
        user_doc = user_manager.get_user_doc_by_id(user_id)
        if not user_doc:
            return jsonify({'error': 'User not found'}), 404
        
        subscription_tier = user_doc.get('subscription_tier', 'free')
        deck_count = user_doc.get('deck_count', 0)
        
        # Enforce free tier limit
        if subscription_tier == 'free' and deck_count >= 3:
            return jsonify({
                'error': 'Deck limit reached',
                'message': 'Free tier allows 3 decks maximum. Delete an old deck or upgrade to Premium.',
                'deck_count': deck_count,
                'deck_limit': 3,
                'subscription_tier': subscription_tier
            }), 403
        
        # Create deck
        result = cosmos_driver.create_deck(user_id, data)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify({'error': 'Server error', 'message': result['message']}), 500
            
    except Exception as e:
        print(f'Error creating deck: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error', 'message': 'Failed to save deck'}), 500


@app.route('/api/decks', methods=['GET'])
@login_required
def get_user_decks():
    """Get all decks for current user."""
    try:
        user_id = session.get('user_id')
        user_doc = user_manager.get_user_doc_by_id(user_id)
        
        decks = cosmos_driver.get_user_decks(user_id)
        
        return jsonify({
            'decks': decks,
            'total_count': len(decks),
            'deck_limit': 3 if user_doc.get('subscription_tier') == 'free' else 999,
            'subscription_tier': user_doc.get('subscription_tier', 'free')
        })
        
    except Exception as e:
        print(f'Error fetching decks: {e}')
        return jsonify({'error': 'Server error', 'message': 'Failed to retrieve decks'}), 500


@app.route('/api/decks/<deck_id>', methods=['GET'])
def get_deck(deck_id):
    """Get a single deck by ID."""
    try:
        deck = cosmos_driver.get_deck_by_id(deck_id, populate_cards=True)
        
        if not deck:
            return jsonify({'error': 'Deck not found'}), 404
        
        # Check if deck is private and user is not owner
        if not deck.get('is_public', False):
            if 'user_id' not in session or session['user_id'] != deck['user_id']:
                return jsonify({'error': 'Access denied', 'message': 'This deck is private'}), 403
        
        return jsonify(deck)
        
    except Exception as e:
        print(f'Error fetching deck: {e}')
        return jsonify({'error': 'Server error', 'message': 'Failed to retrieve deck'}), 500


@app.route('/api/decks/<deck_id>', methods=['PUT'])
@login_required
def update_deck(deck_id):
    """Update a deck."""
    try:
        user_id = session.get('user_id')
        updates = request.json
        
        result = cosmos_driver.update_deck(deck_id, user_id, updates)
        
        if result['success']:
            return jsonify(result)
        elif 'not found' in result['message'].lower():
            return jsonify({'error': 'Deck not found'}), 404
        elif 'access denied' in result['message'].lower():
            return jsonify({'error': 'Access denied', 'message': 'You can only edit your own decks'}), 403
        else:
            return jsonify({'error': 'Server error', 'message': result['message']}), 500
            
    except Exception as e:
        print(f'Error updating deck: {e}')
        return jsonify({'error': 'Server error', 'message': 'Failed to update deck'}), 500


@app.route('/api/decks/<deck_id>', methods=['DELETE'])
@login_required
def delete_deck(deck_id):
    """Delete a deck."""
    try:
        user_id = session.get('user_id')
        
        result = cosmos_driver.delete_deck(deck_id, user_id)
        
        if result['success']:
            return jsonify(result)
        elif 'not found' in result['message'].lower():
            return jsonify({'error': 'Deck not found'}), 404
        elif 'access denied' in result['message'].lower():
            return jsonify({'error': 'Access denied', 'message': 'You can only delete your own decks'}), 403
        else:
            return jsonify({'error': 'Server error', 'message': result['message']}), 500
            
    except Exception as e:
        print(f'Error deleting deck: {e}')
        return jsonify({'error': 'Server error', 'message': 'Failed to delete deck'}), 500


@app.route('/my-decks')
@login_required
def my_decks():
    """User's saved decks page."""
    return render_template('my_decks.html')

@app.route('/deck/<deck_id>')
def view_deck(deck_id):
    """View a saved deck with card type groupings."""
    try:
        print(f'[DEBUG] view_deck called with deck_id: {deck_id}')
        
        # Fetch deck with populated card data
        deck = cosmos_driver.get_deck_by_id(deck_id, populate_cards=True)
        print(f'[DEBUG] get_deck_by_id returned: {deck is not None}')
        
        if not deck:
            print(f'[DEBUG] Deck not found, redirecting to my_decks')
            flash('Deck not found', 'error')
            return redirect(url_for('my_decks'))
        
        # Get user info
        user_id = session.get('user_id')
        deck_user_id = deck.get('user_id')
        is_public = deck.get('is_public', False)
        is_owner = user_id and user_id == deck_user_id
        
        print(f'[DEBUG] is_public: {is_public}, user_id: {user_id}, deck_user_id: {deck_user_id}, is_owner: {is_owner}')
        
        # Allow viewing if:
        # 1. Deck is public, OR
        # 2. User is logged in and is the owner
        if not is_public and not is_owner:
            print(f'[DEBUG] Private deck and user not owner, denying access')
            flash('This deck is private', 'error')
            return redirect(url_for('my_decks'))
        
        print(f'[DEBUG] Rendering deck_viewer.html')
        return render_template('deck_viewer.html', deck=deck, is_owner=is_owner)
        
    except Exception as e:
        print(f'[ERROR] Error viewing deck: {e}')
        import traceback
        traceback.print_exc()
        flash('Error loading deck', 'error')
        return redirect(url_for('my_decks'))

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
    # Pre-warm the card cache on startup (Phase 2 optimization)
    # This ensures the first request doesn't block on a 2-3s database load
    print("🔄 Pre-warming card database cache on startup...")
    try:
        _ = cosmos_driver.get_all_cards()
        print("✅ Cache pre-warmed! All requests will now use fast in-memory cache.")
    except Exception as e:
        print(f"⚠️  Warning: Cache pre-warming failed (non-blocking): {e}")
        print("   First request will take 2-3s, but subsequent requests will be fast.")
    
    # Start Flask app
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

