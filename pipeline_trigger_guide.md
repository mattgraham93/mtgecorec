# MTG Pricing Pipeline - Trigger Guide

## Azure Portal Method (Easiest)

1. **In Azure Portal** → Your Function App → Functions
2. **Click on `collect_pricing`** function
3. **Go to "Code + Test"** tab
4. **Click "Test/Run"** button
5. **Select HTTP Method**: GET or POST
6. **For GET**: Just click "Run" (uses defaults)
7. **For POST**: Add JSON body like:
```json
{
    "target_date": "2024-12-14",
    "max_cards": 1000,
    "force": false
}
```

## Terminal/Command Line Methods

### Option A: Using Azure CLI
```bash
# Install Azure CLI if needed
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Trigger the function
az functionapp function invoke \
  --resource-group mtgecorec \
  --name mtgecorecfunc \
  --function-name collect_pricing
```

### Option B: Using curl/HTTP requests
```bash
# GET request (simple trigger)
curl "https://mtgecorecfunc.azurewebsites.net/api/pricing/collect"

# POST request (with parameters)
curl -X POST "https://mtgecorecfunc.azurewebsites.net/api/pricing/collect" \
  -H "Content-Type: application/json" \
  -d '{
    "target_date": "2024-12-14",
    "max_cards": 500,
    "force": false
  }'
```

## Check Function Status

### 1. Azure Portal Monitoring
- **Functions → collect_pricing → Monitor**
- Look for recent invocations
- Green = Success, Red = Failed
- Click on individual runs to see detailed logs

### 2. Application Insights (if enabled)
- **Function App → Application Insights**
- Check traces and exceptions

### 3. Check your CosmosDB
```python
# Run this in your local terminal to check if data was added
python -c "
from core.data_engine.cosmos_driver import get_cosmos_client
client = get_cosmos_client()
db = client['mtg_cards']
collection = db['card_pricing_daily']

# Count today's records
from datetime import date
today = date.today().isoformat()
count = collection.count_documents({'date_collected': today})
print(f'Records collected today: {count}')
"
```

## Available Functions

1. **`collect_pricing`** - Main data collection
2. **`daily_pricing_collection`** - Scheduled daily run
3. **`health_check`** - Simple status check
4. **`pricing_status`** - Check collection status
5. **`simple_test`** - Basic connectivity test

## Quick Health Check
Start with `health_check` function to test connectivity:
```bash
curl "https://mtgecorecfunc.azurewebsites.net/api/health_check"
```