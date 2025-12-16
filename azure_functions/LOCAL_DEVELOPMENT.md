# Azure Functions Local Development

This directory contains tools for local Azure Functions development and testing.

## Quick Start

### 1. Configure Environment Variables

**Option A: Set Environment Variable (Recommended)**
```bash
# Set your CosmosDB connection string as environment variable
export COSMOS_CONNECTION_STRING="AccountEndpoint=https://mtgecorec.documents.azure.com:443/;AccountKey=YOUR_ACTUAL_KEY_HERE;"
```

**Option B: Edit local.settings.json**
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "COSMOS_CONNECTION_STRING": "AccountEndpoint=https://mtgecorec.documents.azure.com:443/;AccountKey=YOUR_ACTUAL_KEY_HERE;",
    "PYTHONPATH": "/workspaces/mtgecorec/azure_functions"
  }
}
```

**To Get Your Connection String:**
1. Go to Azure Portal → CosmosDB → mtgecorec → Keys
2. Copy the "Primary Connection String"

### 2. Local Testing Options

#### Option A: Direct Function Testing
```bash
# Test with small batch (fast)
python local_test.py --max-cards 5

# Test with specific date
python local_test.py --date 2025-12-15 --max-cards 10

# Test batch chaining logic
python local_test.py --test chaining
```

#### Option B: HTTP Server (Like Real Azure Functions)
```bash
# Start local server
python local_server.py

# In another terminal, test via HTTP
curl "http://localhost:7071/api/collect_pricing?max_cards=5"
curl -X POST "http://localhost:7071/api/collect_pricing" \
  -H "Content-Type: application/json" \
  -d '{"max_cards": 10, "target_date": "2025-12-15"}'
```

## Benefits of Local Development

✅ **Instant Testing** - No deployment delays  
✅ **Free** - No Azure consumption charges  
✅ **Debugging** - Full Python debugging support  
✅ **Fast Iteration** - Change code, test immediately  
✅ **Offline** - Works without internet  

## Development Workflow

1. **Develop locally** with small batches (`max_cards=5-10`)
2. **Test logic** until it works perfectly
3. **Deploy to Azure** only when ready for production
4. **Run production** with confidence

## Debugging Tips

- Use `max_cards=1` for ultra-fast testing
- Check logs in real-time during local execution  
- Test error conditions locally before deploying
- Use VS Code debugger with breakpoints

## Files

- `local_test.py` - Direct function testing
- `local_server.py` - HTTP server simulation
- `local.settings.json` - Local configuration (edit with real connection string)