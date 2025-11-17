"""
perplexity_client.py - Perplexity AI API client for MTG Commander analysis

This module provides functions to interact with Perplexity AI for analyzing
Magic: The Gathering cards and providing strategic insights for Commander decks.
"""
import os
import time
import random
import logging
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
import httpx
import perplexity
from perplexity import Perplexity

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerplexityClient:
    """Client for interacting with Perplexity AI API for MTG analysis."""
    
    def __init__(self, api_key: Optional[str] = None, use_mock: bool = False):
        self.api_key = api_key or os.environ.get('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY must be set in environment or passed to constructor.")
        
        self.use_mock = use_mock
        
        # Initialize mock client as fallback
        import sys
        sys.path.append(os.path.dirname(__file__))
        from perplexity_mock import MockPerplexityClient
        self.mock_client = MockPerplexityClient(api_key=self.api_key)
        
        # Try to initialize the real client with proper timeouts
        try:
            # Configure timeouts as recommended in the documentation
            timeout = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=10.0)
            
            self.client = Perplexity(
                api_key=self.api_key,
                timeout=timeout
            )
            
            # Test connection with a simple call
            logger.info("Testing Perplexity API connection...")
            self._test_connection()
            
        except Exception as e:
            logger.warning(f"Could not initialize Perplexity client, using mock: {e}")
            self.use_mock = True

    def _test_connection(self):
        """Test the API connection with a simple request."""
        try:
            # Test both search and chat capabilities
            search_response = self.client.search.create(
                query="Magic: The Gathering Commander format",
                max_results=3
            )
            logger.info("Perplexity Search API connection successful")
            
            chat_response = self.client.chat.completions.create(
                model="sonar",
                messages=[{"role": "user", "content": "What is Magic: The Gathering?"}]
            )
            logger.info("Perplexity Chat API connection successful")
            return True
        except Exception as e:
            logger.error(f"Perplexity API connection test failed: {e}")
            raise

    def _search_commander_info(self, commander_name: str, max_results: int = 10) -> Dict[str, Any]:
        """Use Search API to gather comprehensive information about a commander."""
        try:
            # Use multi-query search for comprehensive research as recommended
            search_queries = [
                f"{commander_name} MTG Commander deck building guide strategy",
                f"{commander_name} Magic card synergies interactions",
                f"{commander_name} EDH deck tech recommendations",
                f"{commander_name} Commander power level meta analysis",
                f"{commander_name} MTG card combos win conditions"
            ]
            
            search_results = []
            for query in search_queries:
                try:
                    result = self.client.search.create(
                        query=query,
                        max_results=max_results // len(search_queries) + 1
                    )
                    search_results.append({
                        'query': query,
                        'results': result.results if hasattr(result, 'results') else []
                    })
                    
                    # Small delay between searches to respect rate limits
                    time.sleep(0.2)
                    
                except Exception as e:
                    logger.warning(f"Search query failed: {query} - {e}")
                    continue
            
            return {
                'commander': commander_name,
                'search_results': search_results,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Commander search failed: {e}")
            return {
                'commander': commander_name,
                'error': str(e),
                'success': False
            }

    def _make_request_with_retry(self, messages: List[Dict[str, str]], model: str = "sonar-pro", max_retries: int = 3) -> Dict[str, Any]:
        """Make a request with proper error handling and retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.3
                )
                
                # Convert response to dictionary format
                return {
                    'choices': [
                        {
                            'message': {
                                'content': response.choices[0].message.content
                            }
                        }
                    ],
                    'citations': getattr(response, 'citations', [])
                }
                
            except perplexity.RateLimitError as e:
                if attempt == max_retries - 1:
                    logger.error("Rate limit exceeded after all retries")
                    raise
                
                # Exponential backoff with jitter for rate limits
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Rate limited. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                
            except perplexity.APIConnectionError as e:
                if attempt == max_retries - 1:
                    logger.error("Connection error after all retries")
                    raise
                
                # Shorter delay for connection errors
                delay = 1 + random.uniform(0, 1)
                logger.warning(f"Connection error. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                
            except perplexity.AuthenticationError as e:
                logger.error("Authentication failed - check API key")
                raise
                
            except perplexity.ValidationError as e:
                logger.error(f"Validation error: {e}")
                raise
                
            except perplexity.APIStatusError as e:
                logger.error(f"API Status Error {e.status_code}: {e.message}")
                if hasattr(e, 'response'):
                    logger.error(f"Request ID: {e.response.headers.get('X-Request-ID')}")
                
                # Don't retry for client errors (4xx), but retry for server errors (5xx)
                if e.status_code >= 500 and attempt < max_retries - 1:
                    delay = 2 ** attempt
                    logger.warning(f"Server error. Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error: {type(e).__name__}: {e}")
                raise

    def _make_request_curl(self, messages: List[Dict[str, str]], model: str = "sonar-pro") -> Dict[str, Any]:
        """Make a request to the Perplexity API using curl (fallback method)."""
        import subprocess
        import json
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1500,
            "temperature": 0.3
        }
        
        try:
            # Use curl since it works reliably in this environment
            curl_cmd = [
                'curl', '-X', 'POST', 'https://api.perplexity.ai/chat/completions',
                '-H', f'Authorization: Bearer {self.api_key}',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps(payload)
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                raise Exception(f"curl failed: {result.stderr}")
                
        except Exception as e:
            print(f"Error making request to Perplexity: {e}")
            raise

    def analyze_commander_synergies(self, commander_name: str, card_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a commander and suggest synergistic cards and strategies.
        
        Args:
            commander_name: Name of the commander card
            card_list: Optional list of cards already in the deck
            
        Returns:
            Dictionary containing synergy analysis and recommendations
        """
        deck_context = ""
        if card_list:
            deck_context = f"\n\nCurrent deck cards: {', '.join(card_list[:20])}" + \
                          ("..." if len(card_list) > 20 else "")
        
        # Use curl as fallback since Python HTTP libraries have connection issues in this env
        import subprocess
        import json
        
        prompt = f"""Analyze the MTG Commander "{commander_name}" for deck building. 
        Provide detailed analysis including:
        
        1. **Commander Strategy Overview**: What makes this commander effective?
        2. **Key Synergy Categories**: What types of cards work best with this commander?
        3. **Specific Card Recommendations**: Name 10-15 specific cards that synergize well
        4. **Win Conditions**: Primary ways this deck can win games
        5. **Mana Base Considerations**: Any special mana requirements or strategies
        6. **Common Pitfalls**: What to avoid when building around this commander
        
        Format your response as structured analysis with clear sections.{deck_context}"""
        
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": """You are an expert Magic: The Gathering deck builder specializing in the Commander format. 
                    Analyze commanders and provide strategic deck building advice focusing on:
                    1. Card synergies and interactions
                    2. Mana curve optimization
                    3. Win conditions and game plans
                    4. Meta considerations
                    5. Budget alternatives when relevant
                    
                    Provide specific, actionable recommendations with clear reasoning."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Use mock client if API is unavailable or explicitly requested
        if self.use_mock:
            return self.mock_client.analyze_commander_synergies(commander_name, card_list)
        
        messages = [{
            "role": "system",
            "content": """You are an expert Magic: The Gathering deck builder specializing in the Commander format. 
            Analyze commanders and provide strategic deck building advice focusing on:
            1. Card synergies and interactions
            2. Mana curve optimization
            3. Win conditions and game plans
            4. Meta considerations
            5. Budget alternatives when relevant
            
            Provide specific, actionable recommendations with clear reasoning."""
        }, {
            "role": "user",
            "content": prompt
        }]
        
        try:
            # Step 1: Use Search API to gather comprehensive information
            logger.info(f"Gathering information about {commander_name}...")
            search_data = self._search_commander_info(commander_name, max_results=15)
            
            # Step 2: Use gathered information to create a more informed prompt
            search_context = ""
            if search_data['success'] and search_data['search_results']:
                search_context = "\n\n**Research Context:**\n"
                for search_result in search_data['search_results'][:3]:  # Use top 3 queries
                    if search_result.get('results'):
                        search_context += f"- Query: {search_result['query']}\n"
                        for result in search_result['results'][:2]:  # Top 2 results per query
                            if hasattr(result, 'title') and hasattr(result, 'snippet'):
                                search_context += f"  • {result.title}: {result.snippet[:100]}...\n"
                search_context += "\n"
            
            # Enhanced prompt with search context
            enhanced_prompt = prompt + search_context + """
            
            Based on the research context above and your MTG expertise, provide comprehensive analysis."""
            
            enhanced_messages = [{
                "role": "system",
                "content": """You are an expert Magic: The Gathering deck builder specializing in the Commander format. 
                You have access to comprehensive research about MTG cards and strategies. Analyze commanders and provide 
                strategic deck building advice focusing on:
                1. Card synergies and interactions
                2. Mana curve optimization
                3. Win conditions and game plans
                4. Meta considerations
                5. Budget alternatives when relevant
                
                Provide specific, actionable recommendations with clear reasoning. Use the research context 
                provided to inform your analysis."""
            }, {
                "role": "user", 
                "content": enhanced_prompt
            }]
            
            # Step 3: Use Chat API with enhanced context for analysis
            logger.info(f"Generating analysis for {commander_name}...")
            response = self._make_request_with_retry(enhanced_messages, model="sonar-pro")
            
            # Serialize search results properly for JSON response
            serializable_search_results = []
            if search_data['success'] and search_data['search_results']:
                for search_result in search_data['search_results']:
                    serializable_results = []
                    for result in search_result.get('results', []):
                        if hasattr(result, 'title') and hasattr(result, 'snippet'):
                            serializable_results.append({
                                'title': result.title,
                                'snippet': result.snippet,
                                'url': getattr(result, 'url', '')
                            })
                    serializable_search_results.append({
                        'query': search_result.get('query', ''),
                        'results': serializable_results
                    })
            
            return {
                'commander': commander_name,
                'analysis': response['choices'][0]['message']['content'],
                'citations': response.get('citations', []),
                'search_context': serializable_search_results,
                'success': True
            }
                
        except perplexity.AuthenticationError:
            logger.error("Invalid API key - please check PERPLEXITY_API_KEY")
            return {
                'commander': commander_name,
                'error': 'Invalid API key - please check your configuration',
                'success': False
            }
            
        except Exception as e:
            logger.warning(f"API error ({type(e).__name__}: {e}), using mock response")
            return self.mock_client.analyze_commander_synergies(commander_name, card_list)

    def analyze_card_synergies(self, target_cards: List[str], deck_theme: str) -> Dict[str, Any]:
        """
        Analyze specific cards for synergies within a deck theme using Search + Chat APIs.
        
        Args:
            target_cards: List of card names to analyze
            deck_theme: Description of the deck's theme or strategy
            
        Returns:
            Dictionary containing synergy analysis
        """
        if self.use_mock:
            return self.mock_client.analyze_card_synergies(target_cards, deck_theme)
        
        try:
            # Step 1: Search for synergy information for key cards
            search_results = []
            for card in target_cards[:4]:  # Limit to 4 cards to manage API calls
                try:
                    search_query = f"{card} MTG {deck_theme} synergy combo interactions"
                    result = self.client.search.create(
                        query=search_query,
                        max_results=3
                    )
                    search_results.append({
                        'card': card,
                        'query': search_query,
                        'results': result.results if hasattr(result, 'results') else []
                    })
                    time.sleep(0.3)  # Rate limit protection
                except Exception as e:
                    logger.warning(f"Synergy search failed for {card}: {e}")
                    continue
            
            # Step 2: Compile synergy research context  
            search_context = "\n\n**Synergy Research:**\n"
            for search_result in search_results:
                search_context += f"- {search_result['card']}:\n"
                for result in search_result['results'][:2]:
                    if hasattr(result, 'title') and hasattr(result, 'snippet'):
                        search_context += f"  • {result.title}: {result.snippet[:150]}...\n"
            
            # Step 3: Analyze card synergies with Chat API
            cards_text = ", ".join(target_cards)
            messages = [{
                "role": "system",
                "content": f"""You are an expert MTG deck analyst. Evaluate card synergies within specific 
                deck themes and strategies. Focus on mechanical interactions, combo potential, and strategic 
                value. Use research context to inform your analysis."""
            }, {
                "role": "user",
                "content": f"""Analyze these MTG cards for synergies within a "{deck_theme}" strategy: {cards_text}

                Please provide:
                1. **Direct Synergies**: How these cards work together mechanically
                2. **Combo Potential**: Multi-card interactions and engine pieces
                3. **Missing Pieces**: What cards would complete powerful interactions
                4. **Optimization Suggestions**: How to improve these synergies
                5. **Alternative Options**: Similar cards that might work better
                6. **Strategic Value**: How these synergies support the deck's game plan
                
                Focus on competitive deck building and strategic analysis.
                
                {search_context}"""
            }]
            
            response = self._make_request_with_retry(messages, model="sonar-pro")
            
            # Serialize search results properly for JSON response  
            serializable_search_results = []
            for search_result in search_results:
                serializable_results = []
                for result in search_result.get('results', []):
                    if hasattr(result, 'title') and hasattr(result, 'snippet'):
                        serializable_results.append({
                            'title': result.title,
                            'snippet': result.snippet,
                            'url': getattr(result, 'url', '')
                        })
                serializable_search_results.append({
                    'card': search_result.get('card', ''),
                    'query': search_result.get('query', ''),
                    'results': serializable_results
                })
            
            return {
                'cards': target_cards,
                'theme': deck_theme,
                'analysis': response['choices'][0]['message']['content'],
                'citations': response.get('citations', []),
                'search_results': serializable_search_results,
                'success': True
            }
            
        except Exception as e:
            logger.warning(f"Card synergy analysis failed ({e}), using mock response")
            return self.mock_client.analyze_card_synergies(target_cards, deck_theme)

    def suggest_budget_alternatives(self, expensive_cards: List[str], budget_limit: float) -> Dict[str, Any]:
        """
        Get budget alternatives for expensive cards using Search + Chat APIs.
        
        Args:
            expensive_cards: List of expensive card names
            budget_limit: Maximum budget per card in USD
            
        Returns:
            Dictionary containing budget alternatives
        """
        if self.use_mock:
            return self.mock_client.suggest_budget_alternatives(expensive_cards, budget_limit)
        
        try:
            # Step 1: Search for budget alternatives for each card
            search_results = []
            for card in expensive_cards[:5]:  # Limit to 5 cards to manage API calls
                try:
                    search_query = f"{card} MTG budget alternative similar effect under ${budget_limit}"
                    result = self.client.search.create(
                        query=search_query,
                        max_results=3
                    )
                    search_results.append({
                        'card': card,
                        'query': search_query,
                        'results': result.results if hasattr(result, 'results') else []
                    })
                    time.sleep(0.3)  # Rate limit protection
                except Exception as e:
                    logger.warning(f"Budget search failed for {card}: {e}")
                    continue
            
            # Step 2: Compile search context
            search_context = "\n\n**Budget Research:**\n"
            for search_result in search_results:
                search_context += f"- {search_result['card']}:\n"
                for result in search_result['results'][:2]:
                    if hasattr(result, 'title') and hasattr(result, 'snippet'):
                        search_context += f"  • {result.title}: {result.snippet[:150]}...\n"
            
            # Step 3: Generate budget analysis with Chat API
            cards_text = ", ".join(expensive_cards)
            messages = [{
                "role": "system",
                "content": f"""You are an expert MTG budget deck builder. Provide affordable alternatives 
                to expensive cards while maintaining similar functionality and power level. Research context 
                is provided to inform your recommendations."""
            }, {
                "role": "user",
                "content": f"""Suggest budget alternatives (under ${budget_limit} each) for these expensive MTG cards: {cards_text}
                
                For each card, provide:
                1. **Primary Alternative**: Best budget substitute
                2. **Secondary Options**: 2-3 additional alternatives  
                3. **Functionality Notes**: What you gain/lose with the substitute
                4. **Estimated Price**: Rough price range for alternatives
                
                Focus on maintaining the deck's core strategy while reducing cost.
                
                {search_context}"""
            }]
            
            response = self._make_request_with_retry(messages, model="sonar-pro")
            
            # Serialize search results properly for JSON response
            serializable_search_results = []
            for search_result in search_results:
                serializable_results = []
                for result in search_result.get('results', []):
                    if hasattr(result, 'title') and hasattr(result, 'snippet'):
                        serializable_results.append({
                            'title': result.title,
                            'snippet': result.snippet,
                            'url': getattr(result, 'url', '')
                        })
                serializable_search_results.append({
                    'card': search_result.get('card', ''),
                    'query': search_result.get('query', ''),
                    'results': serializable_results
                })
            
            return {
                'original_cards': expensive_cards,
                'budget_limit': budget_limit,
                'alternatives': response['choices'][0]['message']['content'],
                'citations': response.get('citations', []),
                'search_results': serializable_search_results,
                'success': True
            }
            
        except Exception as e:
            logger.warning(f"Budget alternatives failed ({e}), using mock response")
            return self.mock_client.suggest_budget_alternatives(expensive_cards, budget_limit)

    def analyze_meta_considerations(self, commander: str, playgroup_description: str = "casual") -> Dict[str, Any]:
        """
        Analyze meta considerations for a commander in different playgroups using Search + Chat APIs.
        
        Args:
            commander: Commander name
            playgroup_description: Description of playgroup meta (casual, competitive, etc.)
            
        Returns:
            Dictionary containing meta analysis
        """
        if self.use_mock:
            return self.mock_client.analyze_meta_considerations(commander, playgroup_description)
        
        try:
            # Step 1: Search for meta information based on playgroup type
            meta_queries = [
                f"{commander} MTG Commander {playgroup_description} meta 2024",
                f"EDH {playgroup_description} playgroup {commander} power level",
                f"{commander} vs {playgroup_description} meta commanders",
                f"MTG Commander {playgroup_description} strategies {commander}",
                f"{playgroup_description} EDH meta trends popular decks"
            ]
            
            search_results = []
            for query in meta_queries:
                try:
                    result = self.client.search.create(
                        query=query,
                        max_results=3
                    )
                    search_results.append({
                        'query': query,
                        'results': result.results if hasattr(result, 'results') else []
                    })
                    time.sleep(0.3)  # Rate limit protection
                except Exception as e:
                    logger.warning(f"Meta search failed for query '{query}': {e}")
                    continue
            
            # Step 2: Compile meta research context
            search_context = "\n\n**Meta Research:**\n"
            for search_result in search_results:
                if search_result['results']:
                    search_context += f"- Query: {search_result['query'][:60]}...\n"
                    for result in search_result['results'][:2]:
                        if hasattr(result, 'title') and hasattr(result, 'snippet'):
                            search_context += f"  • {result.title}: {result.snippet[:150]}...\n"
            
            # Step 3: Analyze meta considerations with Chat API
            messages = [{
                "role": "system",
                "content": f"""You are an expert MTG Commander meta analyst specializing in different 
                playgroup dynamics. Provide strategic advice for optimizing commanders for specific 
                meta environments. Use research context to inform your recommendations."""
            }, {
                "role": "user", 
                "content": f"""Analyze {commander} for a {playgroup_description} EDH meta/playgroup.
                
                Provide analysis on:
                1. **Power Level Match**: How well {commander} fits this meta level
                2. **Expected Opposition**: Common threats in {playgroup_description} groups
                3. **Strategy Optimization**: How to build {commander} for this environment
                4. **Political Considerations**: Table dynamics and threat assessment
                5. **Card Choices**: Key inclusions/exclusions for this meta
                6. **Win Conditions**: Appropriate win-cons for this power level
                
                Focus on practical deck building advice for this specific playgroup type.
                
                {search_context}"""
            }]
            
            response = self._make_request_with_retry(messages, model="sonar-pro")
            
            # Serialize search results properly for JSON response
            serializable_search_results = []
            for search_result in search_results:
                serializable_results = []  
                for result in search_result.get('results', []):
                    if hasattr(result, 'title') and hasattr(result, 'snippet'):
                        serializable_results.append({
                            'title': result.title,
                            'snippet': result.snippet,
                            'url': getattr(result, 'url', '')
                        })
                serializable_search_results.append({
                    'query': search_result.get('query', ''),
                    'results': serializable_results
                })
            
            return {
                'commander': commander,
                'playgroup_type': playgroup_description,
                'analysis': response['choices'][0]['message']['content'],
                'citations': response.get('citations', []),
                'search_results': serializable_search_results,
                'success': True
            }
            
        except Exception as e:
            logger.warning(f"Meta considerations analysis failed ({e}), using mock response")
            return self.mock_client.analyze_meta_considerations(commander, playgroup_description)


def test_perplexity_client():
    """Test the Perplexity client with proper error handling."""
    print("Testing Perplexity AI integration...")
    
    try:
        # Test API key availability
        api_key = os.environ.get('PERPLEXITY_API_KEY')
        if not api_key:
            print("PERPLEXITY_API_KEY not found in environment")
            return False
        
        print(f"🔑 API Key found: {api_key[:10]}...")
        
        # Initialize client with proper error handling
        client = PerplexityClient(use_mock=False)  # Force real API test
        
        # Test with a popular commander
        print("Testing commander analysis...")
        result = client.analyze_commander_synergies("Atraxa, Praetors' Voice")
        
        if result['success']:
            print("Perplexity AI integration successful!")
            print("\nAnalysis Preview:")
            preview = result['analysis'][:500] + "..." if len(result['analysis']) > 500 else result['analysis']
            print(preview)
            
            if result.get('citations'):
                print(f"\nSources: {len(result['citations'])} citations found")
            
            if result.get('mock'):
                print("\nNote: Using mock response (API unavailable)")
            else:
                print("\n🌐 Real API response received!")
                
            return True
        else:
            print(f"Analysis failed: {result.get('error', 'Unknown error')}")
            return False
            
    except perplexity.AuthenticationError:
        print("Authentication failed - check your API key")
        return False
    except perplexity.APIConnectionError as e:
        print(f"Connection failed: {e}")
        print("This might be a network issue - using mock responses for now")
        return False
    except Exception as e:
        logger.error(f"Test failed with unexpected error: {e}")
        print(f"Unexpected error: {type(e).__name__}: {e}")
        print("\nCheck your API key and network connection")
        return False


if __name__ == "__main__":
    test_perplexity_client()