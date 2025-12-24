import logging
import json
import os
from datetime import datetime, date, timezone
import azure.functions as func

# Global lock to prevent concurrent executions
_pricing_collection_running = False
_pricing_lock_timestamp = None

# Import our pipeline
import sys
sys.path.append('/home/site/wwwroot')  # Azure Functions path
sys.path.append('.')  # Local development path

try:
    # First check if requests is available
    import requests
    logging.info("✅ requests module available")
    
    # Then try to import the pipeline
    from pricing_pipeline import run_pricing_pipeline_azure_function
    logging.info("✅ Successfully imported pricing_pipeline")
except ImportError as e:
    import_error = str(e)
    logging.error(f"❌ Import failed: {import_error}")
    # Create a dummy function to prevent total failure
    def run_pricing_pipeline_azure_function(*args, **kwargs):
        return {"error": "Pipeline import failed", "details": import_error}
except Exception as e:
    import_error = str(e)
    logging.error(f"❌ Unexpected error during import: {import_error}")
    def run_pricing_pipeline_azure_function(*args, **kwargs):
        return {"error": "Pipeline import failed", "details": import_error}

# Create the Function App using v2 programming model
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="debug/modules", methods=["GET"])
def debug_modules(req: func.HttpRequest) -> func.HttpResponse:
    """Debug function to check available modules"""
    import sys
    import os
    
    try:
        # Check specific modules
        modules_to_check = ['requests', 'pymongo', 'azure.functions']
        module_status = {}
        
        for module in modules_to_check:
            try:
                __import__(module)
                module_status[module] = "✅ Available"
            except ImportError as e:
                module_status[module] = f"❌ Missing: {str(e)}"
        
        # Try to get installed packages
        installed_packages = []
        try:
            import pkg_resources
            installed_packages = [str(d) for d in pkg_resources.working_set][:10]
        except:
            installed_packages = ["pkg_resources not available"]
        
        debug_info = {
            "python_version": sys.version,
            "python_path": sys.path[:3],
            "working_directory": os.getcwd() if hasattr(os, 'getcwd') else "unknown",
            "module_status": module_status,
            "installed_packages": installed_packages
        }
        
        return func.HttpResponse(
            json.dumps(debug_info, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Debug failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="pricing/collect", methods=["GET", "POST"])
def collect_pricing(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to collect MTG card pricing data
    
    Supports both GET and POST requests:
    - GET: Run with default settings (today's date, skip existing)
    - POST: Run with custom parameters via JSON body
    
    POST Body Parameters (all optional):
    {
        "target_date": "2025-12-13",  // Date in YYYY-MM-DD format
        "max_cards": 5000,            // Limit cards processed (for chunking)
        "force": false,               // Skip duplicate check if true
        "hobby_mode": false           // Process all cards (no filtering)
    }
    """
    
    global _pricing_collection_running, _pricing_lock_timestamp
    
    logging.info('MTG Pricing Collection function triggered')
    
    # Check if another instance is already running (with 15-minute timeout)
    current_time = datetime.now(timezone.utc)
    if _pricing_collection_running:
        if _pricing_lock_timestamp and (current_time - _pricing_lock_timestamp).total_seconds() > 900:  # 15 minutes
            logging.warning('Pricing lock expired (15+ minutes), resetting...')
            _pricing_collection_running = False
            _pricing_lock_timestamp = None
        else:
            logging.warning('Pricing collection already in progress, skipping...')
            return func.HttpResponse(
                json.dumps({
                    "status": "skipped",
                    "message": "Another pricing collection is already in progress",
                    "timestamp": current_time.isoformat()
                }),
                status_code=200,
                mimetype="application/json"
            )
    
    # Set the lock
    _pricing_collection_running = True
    _pricing_lock_timestamp = current_time
    
    # Initialize variables with default values
    target_date = date.today().isoformat()
    max_cards = None
    skip_existing = True
    
    try:
        # Parse request parameters
        
        if req.method == "POST":
            try:
                req_body = req.get_json()
                if req_body:
                    if 'target_date' in req_body and req_body['target_date']:
                        target_date = req_body.get('target_date')
                    if 'max_cards' in req_body:
                        max_cards = req_body.get('max_cards')
                    skip_existing = not req_body.get('force', False)
            except ValueError:
                return func.HttpResponse(
                    json.dumps({
                        "error": "Invalid JSON in request body",
                        "status": "error"
                    }),
                    status_code=400,
                    mimetype="application/json"
                )
        
        # URL parameters (for GET requests)  
        url_target_date = req.params.get('target_date')
        if url_target_date:
            target_date = url_target_date
        if not max_cards:
            max_cards_param = req.params.get('max_cards')
            if max_cards_param:
                try:
                    max_cards = int(max_cards_param)
                except ValueError:
                    pass
        
        # Use provided target_date or keep default (already set above)
        
        # Process all cards - no filtering applied
        # Full dataset processing for complete coverage
        if max_cards is None:
            # With 2.5 hour timeout, we can process all remaining cards in one execution
            # Current performance: ~18 cards/sec, 92K cards = ~85 minutes (well under 150 min limit)
            default_batch_size = int(os.getenv('DEFAULT_BATCH_SIZE', '100000'))  # Process all remaining cards at once
            batch_size = default_batch_size
            logging.info(f"Using default batch size: {batch_size} cards per function call (2.5h timeout allows single execution)")
        else:
            batch_size = max_cards
            
        logging.info(f"Starting pricing collection for date: {target_date}, batch_size: {batch_size}")
        
        # Run the pipeline
        result = run_pricing_pipeline_azure_function(
            target_date=target_date,
            max_cards=batch_size
        )
        
        # Format response
        response_data = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "function": "pricing_collection",
            **result
        }
        
        # Log summary
        cards_processed = result.get('cards_processed', 0)
        records_created = result.get('records_created', 0)
        logging.info(f"Pipeline completed: {cards_processed} cards, {records_created} records")
        
        # Check if we should trigger the next batch (simplified, no threading)
        should_continue = False
        next_batch_info = ""
        
        # Auto-continue if this was a full batch (not a user-limited run) 
        # The key insight: continue based on remaining cards, not cards processed in this batch
        # Many cards may not have pricing data, so batch size != cards processed
        user_specified_limit = req.method == "POST" and req.get_json() and req.get_json().get('max_cards') is not None
        url_max_cards = req.params.get('max_cards') is not None
        is_limited_run = user_specified_limit or url_max_cards
        
        if not is_limited_run:  # Continue if this was a full pipeline run (not user-limited)
            # Check if there are more cards to process for this specific date
            try:
                from pricing_pipeline import MTGPricingPipeline
                
                # Create pipeline instance to check remaining cards
                pipeline = MTGPricingPipeline()
                
                # Get cards that DON'T have pricing for this specific date
                # This is the correct calculation
                total_cards = pipeline.cards_collection.count_documents({})
                
                # Find cards that already have pricing for this date
                cards_with_pricing_ids = set()
                pricing_cursor = pipeline.pricing_collection.find(
                    {'date': target_date}, 
                    {'scryfall_id': 1}
                )
                for record in pricing_cursor:
                    cards_with_pricing_ids.add(record.get('scryfall_id'))
                
                cards_with_pricing = len(cards_with_pricing_ids)
                remaining_cards = total_cards - cards_with_pricing
                
                logging.info(f"📊 Total cards: {total_cards:,}")
                logging.info(f"📊 Cards with pricing for {target_date}: {cards_with_pricing:,}")
                logging.info(f"📊 Remaining cards: {remaining_cards:,}")
                
                if remaining_cards > 1000:  # Only continue if meaningful work left
                    should_continue = True
                    next_batch_info = f"Next batch needed: {remaining_cards:,} cards remaining for {target_date}"
                    logging.info(next_batch_info)
                    
                    # Re-enabled with 20K batch size - much safer memory profile
                    # Simple HTTP trigger (no threading) - just make the request directly
                    try:
                        import requests
                        import time
                        time.sleep(3)  # Brief delay to avoid collision
                        
                        response = requests.get(
                            "https://mtgecorec-pricing.azurewebsites.net/api/collect_pricing",
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            logging.info("✅ Successfully triggered next batch")
                        else:
                            logging.warning(f"⚠️  Next batch trigger returned {response.status_code}")
                            
                    except Exception as e:
                        logging.warning(f"❌ Failed to trigger next batch: {e}")
                        next_batch_info += f" (Auto-trigger failed: {e})"
                else:
                    next_batch_info = f"Collection complete for {target_date}! Only {remaining_cards} cards remaining (below threshold)"
                    logging.info(next_batch_info)
                    
            except Exception as e:
                logging.error(f"Failed to check remaining cards: {e}")
                next_batch_info = f"Unable to check for remaining cards: {e}"
        
        # Add batch info to response
        response_data["batch_info"] = {
            "batch_size": batch_size,
            "auto_continue": should_continue,
            "next_batch_status": next_batch_info
        }
        
        # Release the lock
        _pricing_collection_running = False
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_msg = f"Pipeline execution failed: {str(e)}"
        logging.error(error_msg)
        
        error_response = {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "function": "pricing_collection",
            "error": str(e),
            "target_date": target_date
        }
        
        # Release the lock
        _pricing_collection_running = False
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="pricing/reset_lock", methods=["POST"])
def reset_pricing_lock(req: func.HttpRequest) -> func.HttpResponse:
    """
    Reset the pricing collection lock - use when function gets stuck
    """
    global _pricing_collection_running
    
    was_running = _pricing_collection_running
    _pricing_collection_running = False
    
    logging.info(f'Pricing lock reset. Was running: {was_running}')
    
    return func.HttpResponse(
        json.dumps({
            "status": "success",
            "message": "Pricing collection lock reset",
            "was_running": was_running,
            "now_running": False,
            "timestamp": datetime.utcnow().isoformat()
        }),
        status_code=200,
        mimetype="application/json"
    )

@app.route(route="pricing/status", methods=["GET"])
def pricing_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get pricing coverage statistics
    """
    
    logging.info('Pricing status check triggered')
    
    try:
        # Import here to avoid import issues during deployment
        from pricing_pipeline import MTGPricingPipeline
        
        pipeline = MTGPricingPipeline()
        stats = pipeline.get_coverage_stats()
        
        response_data = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "function": "pricing_status",
            **stats
        }
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_msg = f"Status check failed: {str(e)}"
        logging.error(error_msg)
        
        error_response = {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "function": "pricing_status",
            "error": str(e)
        }
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Simple health check endpoint
    """
    
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "mtg-pricing-pipeline"
        }),
        status_code=200,
        mimetype="application/json"
    )


@app.route(route="test", methods=["GET"])
def simple_test(req: func.HttpRequest) -> func.HttpResponse:
    """
    Simple test endpoint that doesn't depend on external modules
    """
    logging.info('Simple test function triggered')
    
    return func.HttpResponse(
        json.dumps({
            "message": "Function app is working!",
            "timestamp": datetime.utcnow().isoformat(),
            "python_version": sys.version
        }),
        status_code=200,
        mimetype="application/json"
    )


@app.timer_trigger(schedule="0 0 3 * * *", arg_name="myTimer", run_on_startup=False)
def daily_pricing_collection(myTimer: func.TimerRequest) -> None:
    """
    Scheduled daily pricing collection
    Runs every day at 7:00 PM PST (3:00 AM UTC next day)
    """
    
    if myTimer.past_due:
        logging.info('Timer is past due!')
    
    logging.info('Starting scheduled daily pricing collection at 7:00 PM PST...')
    
    try:
        # Trigger the HTTP function which has auto-chaining logic
        # This ensures complete processing of all cards
        import requests
        try:
            response = requests.get(
                "https://mtgecorecfunc.azurewebsites.net/api/pricing/collect",
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                logging.info("✅ Successfully triggered auto-chaining pipeline from timer")
            else:
                logging.error(f"❌ HTTP trigger failed: {response.status_code}")
                # Fallback to direct call
                result = run_pricing_pipeline_azure_function(
                    target_date=None,
                    max_cards=20000
                )
        except Exception as e:
            logging.error(f"❌ HTTP trigger failed: {e}, falling back to direct call")
            # Fallback to direct call  
            result = run_pricing_pipeline_azure_function(
                target_date=None,
                max_cards=20000
            )
        
        cards_processed = result.get('cards_processed', 0)
        records_created = result.get('records_created', 0)
        status = result.get('status', 'unknown')
        
        if status == 'complete':
            logging.info(
                f"✅ Scheduled pricing collection completed successfully!\n"
                f"📊 Cards processed: {cards_processed:,}\n"
                f"💎 Pricing records created: {records_created:,}\n"
                f"⏰ Execution time: {result.get('total_time_seconds', 0)} seconds"
            )
        else:
            logging.warning(
                f"⚠️ Scheduled pricing collection completed with status: {status}\n"
                f"📊 Cards processed: {cards_processed:,}\n"
                f"💎 Records created: {records_created:,}"
            )
        
    except Exception as e:
        logging.error(f"❌ Scheduled pricing collection failed: {str(e)}", exc_info=True)
        # Don't re-raise - let the function complete gracefully