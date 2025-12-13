# Azure Functions Deployment Instructions

## Prerequisites
1. Azure CLI installed
2. Azure Functions Core Tools v4
3. Python 3.9+ installed

## Local Development Setup

1. **Create local settings file:**
   ```bash
   cp local.settings.json.template local.settings.json
   ```

2. **Edit local.settings.json with your MongoDB connection string:**
   ```json
   {
     "IsEncrypted": false,
     "Values": {
       "AzureWebJobsStorage": "UseDevelopmentStorage=true", 
       "FUNCTIONS_WORKER_RUNTIME": "python",
       "COSMOS_CONNECTION_STRING": "your_actual_connection_string"
     }
   }
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start local development:**
   ```bash
   func start
   ```

## Azure Deployment

### Option 1: Azure CLI Deployment

1. **Login to Azure:**
   ```bash
   az login
   ```

2. **Create Resource Group (if needed):**
   ```bash
   az group create --name rg-mtgecorec --location "East US"
   ```

3. **Create Storage Account:**
   ```bash
   az storage account create --name stmtgecorecfunc --location "East US" --resource-group rg-mtgecorec --sku Standard_LRS
   ```

4. **Create Function App:**
   ```bash
   az functionapp create --resource-group rg-mtgecorec --consumption-plan-location "East US" --runtime python --runtime-version 3.11 --functions-version 4 --name func-mtgecorec-pricing --storage-account stmtgecorecfunc
   ```

5. **Configure App Settings:**
   ```bash
   az functionapp config appsettings set --name func-mtgecorec-pricing --resource-group rg-mtgecorec --settings "COSMOS_CONNECTION_STRING=your_connection_string"
   ```

6. **Deploy:**
   ```bash
   func azure functionapp publish func-mtgecorec-pricing
   ```

### Option 2: VS Code Extension

1. Install "Azure Functions" extension
2. Sign in to Azure
3. Create Function App from VS Code
4. Deploy using the extension

## Function Endpoints

After deployment, your functions will be available at:

- **Collect Pricing:** `https://func-mtgecorec-pricing.azurewebsites.net/api/pricing/collect`
- **Get Status:** `https://func-mtgecorec-pricing.azurewebsites.net/api/pricing/status`  
- **Health Check:** `https://func-mtgecorec-pricing.azurewebsites.net/api/health`

## Calling from Your Web App

### JavaScript/TypeScript Example:
```javascript
async function collectPricing(maxCards = null) {
    const response = await fetch('/api/pricing/collect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            target_date: '2025-12-13',
            max_cards: maxCards
        })
    });
    
    return await response.json();
}
```

### Python Example:
```python
import requests

def trigger_pricing_collection():
    response = requests.post(
        'https://func-mtgecorec-pricing.azurewebsites.net/api/pricing/collect',
        json={
            'target_date': '2025-12-13',
            'max_cards': 5000
        }
    )
    return response.json()
```

## Monitoring

- View logs in Azure Portal > Function App > Functions > Monitor
- Set up Application Insights for detailed monitoring
- Configure alerts for failures

## Scaling Considerations

**Consumption Plan (Recommended for start):**
- Pay per execution
- 5-minute timeout (use max_cards=5000)
- Auto-scales

**Premium Plan (For heavy usage):**
- 30-minute timeout
- Always warm instances
- Process full dataset in one call