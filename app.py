import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for, jsonify)

# Import Cosmos DB driver
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'data_engine'))
from data_engine import cosmos_driver

app = Flask(__name__)


@app.route('/')
def index():
   print('Request for index page received')
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/hello', methods=['POST'])
def hello():
   name = request.form.get('name')

   if name:
       print('Request for hello page received with name=%s' % name)
       return render_template('hello.html', name = name)
   else:
       print('Request for hello page received with no name or blank name -- redirecting')
       return redirect(url_for('index'))


if __name__ == '__main__':
   app.run()



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
   skip = (page - 1) * page_size
   print(f'Pagination params: page={page}, page_size={page_size}, skip={skip}')
   total = collection.count_documents({})
   print(f'Total cards in collection: {total}')
   cursor = collection.find({}, {'_id': 0}).skip(skip).limit(page_size)
   cards = list(cursor)
   print(f'Returning {len(cards)} cards for this page')
   return jsonify({
      'cards': cards,
      'total': total,
      'page': page,
      'page_size': page_size
   })


# connect to azure mongo db
# get card api call underway
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

