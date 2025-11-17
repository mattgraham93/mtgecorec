#!/usr/bin/env python3
"""
Simple test to see what Perplexity returns for our JSON request
"""

import asyncio
import os
import json
import httpx

async def test_perplexity_json_request():
    """Test what Perplexity returns for a JSON request."""
    
    api_key = os.environ.get('PERPLEXITY_API_KEY')
    if not api_key:
        print("❌ No PERPLEXITY_API_KEY found")
        return
    
    print("🧪 Testing Perplexity JSON Request")
    print("=" * 50)
    
    query = '''
    For Magic: The Gathering Commander Alela, Artful Provocateur with color identity W/U/B, 
    recommend exactly 10-15 specific card names that synergize with these mechanics: Flying and artifacts, Token generation, Tribal synergies
    
    CRITICAL: Format your response as valid JSON only:
    {
        "recommended_cards": [
            "Card Name 1",
            "Card Name 2", 
            "Card Name 3"
        ]
    }
    
    Requirements:
    - Only cards legal in Commander format
    - Only cards within the commander's color identity  
    - Use exact card names as they appear in official Magic databases
    - No additional text, only JSON
    '''
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": query,
                    "max_results": 5
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ API call successful")
                print(f"📊 Status: {response.status_code}")
                
                # Extract the content from results
                if 'results' in data and data['results']:
                    for i, result in enumerate(data['results'], 1):
                        print(f"\n📄 Result {i}:")
                        
                        # Check different content fields
                        content = None
                        if hasattr(result, 'snippet') and result.get('snippet'):
                            content = result['snippet']
                        elif hasattr(result, 'content') and result.get('content'):
                            content = result['content']
                        elif isinstance(result, dict):
                            # Try common field names
                            for field in ['snippet', 'content', 'text', 'body', 'summary']:
                                if field in result and result[field]:
                                    content = result[field]
                                    print(f"   📝 Found content in '{field}' field")
                                    break
                        
                        if content:
                            print(f"   📄 Raw content: {content[:300]}...")
                            
                            # Try to parse as JSON
                            try:
                                # Look for JSON in the content
                                start_idx = content.find('{')
                                end_idx = content.rfind('}') + 1
                                
                                if start_idx >= 0 and end_idx > start_idx:
                                    json_str = content[start_idx:end_idx]
                                    parsed = json.loads(json_str)
                                    print(f"   ✅ Successfully parsed JSON: {parsed}")
                                    
                                    if 'recommended_cards' in parsed:
                                        cards = parsed['recommended_cards']
                                        print(f"   🎯 Extracted {len(cards)} cards: {cards}")
                                else:
                                    print(f"   ❌ No JSON structure found in content")
                                    
                            except json.JSONDecodeError as e:
                                print(f"   ❌ JSON parsing failed: {e}")
                                print(f"   🔍 Attempted to parse: {json_str[:200]}...")
                        else:
                            print(f"   ⚠️ No content found in result")
                            print(f"   🔍 Available fields: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                else:
                    print("❌ No results returned from Perplexity")
                    print(f"🔍 Response structure: {list(data.keys())}")
                    
            else:
                print(f"❌ API call failed: {response.status_code}")
                print(f"📄 Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_perplexity_json_request())