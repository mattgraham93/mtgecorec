import logging
import json
import os
from datetime import datetime, date
import azure.functions as func

# Import our pipeline
import sys
sys.path.append('/home/site/wwwroot')  # Azure Functions path
sys.path.append('.')  # Local development path

from pricing_pipeline import run_pricing_pipeline_azure_function

# Create the Function App using v2 programming model
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

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
        "force": false                // Skip duplicate check if true
    }
    """
    
    logging.info('MTG Pricing Collection function triggered')
    
    try:
        # Parse request parameters
        target_date = None
        max_cards = None
        skip_existing = True
        
        if req.method == "POST":
            try:
                req_body = req.get_json()
                if req_body:
                    target_date = req_body.get('target_date')
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
        if not target_date:
            target_date = req.params.get('target_date')
        if not max_cards:
            max_cards_param = req.params.get('max_cards')
            if max_cards_param:
                try:
                    max_cards = int(max_cards_param)
                except ValueError:
                    pass
        
        # Set default date if none provided
        if not target_date:
            target_date = date.today().isoformat()
        
        logging.info(f"Starting pricing collection for date: {target_date}, max_cards: {max_cards}")
        
        # Run the pipeline
        result = run_pricing_pipeline_azure_function(
            target_date=target_date,
            max_cards=max_cards
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
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=500,
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
        # Run pricing pipeline with NO LIMIT for full performance test
        result = run_pricing_pipeline_azure_function(
            target_date=None,  # Use today's date
            max_cards=None     # Process ALL cards to measure time and cost
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