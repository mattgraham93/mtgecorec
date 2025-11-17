#!/usr/bin/env python3
"""
Test script to check image URL structure in the database.
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, 'data_engine'))

from data_engine.cosmos_driver import get_collection

def test_image_urls():
    """Check what image URL structure looks like in our database."""
    print("Testing image URL structure...")
    
    try:
        # Get cards collection
        from data_engine.cosmos_driver import get_mongo_client
        client = get_mongo_client()
        collection = get_collection(client, 'mtgecorec', 'cards')
        
        # Find a few cards with image_uris
        cards_with_images = list(collection.find(
            {'image_uris': {'$exists': True, '$ne': None}}, 
            {'name': 1, 'image_uris': 1, 'set_name': 1}
        ).limit(3))
        
        print(f"Found {len(cards_with_images)} cards with images:")
        
        for card in cards_with_images:
            print(f"\n{card.get('name', 'Unknown')} ({card.get('set_name', 'Unknown set')}):")
            image_uris = card.get('image_uris', {})
            print(f"   Image URIs structure: {list(image_uris.keys())}")
            
            # Check each image type
            for img_type in ['normal', 'large', 'small', 'png', 'art_crop', 'border_crop']:
                if img_type in image_uris:
                    url = image_uris[img_type]
                    print(f"   {img_type}: {url[:50]}..." if len(url) > 50 else f"   {img_type}: {url}")
        
        # Also check a specific card we know should have images
        alela = collection.find_one({'name': 'Alela, Artful Provocateur'}, {'name': 1, 'image_uris': 1, 'set_name': 1})
        if alela:
            print(f"\n🧚 Alela, Artful Provocateur:")
            image_uris = alela.get('image_uris', {})
            if image_uris:
                print(f"   Available image types: {list(image_uris.keys())}")
                if 'normal' in image_uris:
                    print(f"   Normal image: {image_uris['normal']}")
                if 'large' in image_uris:
                    print(f"   Large image: {image_uris['large']}")
            else:
                print("   No image_uris found!")
        
        print("\nImage URL structure test completed!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_image_urls()