
# MTG EcoRec: AI-Powered Commander Deck Builder & MTG Analytics

A modern web application that combines **AI-powered Commander deck building** with **comprehensive MTG data analytics**. Built for competitive players, data analysts, and MTG enthusiasts who want intelligent card recommendations backed by real-time analysis.

## Key Features

### AI Commander Recommendations
- **Perplexity AI Integration**: Get intelligent card suggestions using advanced AI analysis
- **Commander Search & Analysis**: Search and analyze any Commander with detailed strategic insights  
- **Synergy Detection**: AI identifies optimal card combinations and deck strategies
- **Power Level Optimization**: Recommendations tailored to your preferred power level

### Advanced Card Analytics
- **Paginated Card Browser**: Browse 35,000+ MTG cards with advanced filtering
- **Real-time Data Visualizations**: Interactive charts and statistics
- **Color & Type Analysis**: Deep dive into card distribution and trends
- **Set Statistics**: Comprehensive analysis across all MTG sets

### Smart Filtering & Search
- **Multi-color Filtering**: Exclusive and inclusive color combinations
- **Card Type Filtering**: Filter by creatures, spells, artifacts, and more
- **Advanced Sorting**: Sort by name, CMC, power/toughness, and other attributes
- **Live Search**: Real-time search with instant results

## Tech Stack

### Backend
- **Python Flask**: Web framework with modern async capabilities
- **Azure Cosmos DB**: MongoDB API for scalable card data storage
- **Perplexity AI**: Advanced AI for card analysis and recommendations
- **Scryfall API**: Comprehensive MTG card data integration

### Frontend  
- **Bootstrap 5**: Responsive, modern UI components
- **Vanilla JavaScript**: Fast, lightweight interactive features
- **Chart.js**: Dynamic data visualizations
- **Async Loading**: Smooth user experience with progressive loading

### Infrastructure
- **Azure App Service**: Production hosting with auto-scaling
- **Azure Developer CLI (azd)**: Infrastructure as Code deployment
- **Bicep Templates**: Automated Azure resource provisioning
- **Environment Management**: Secure configuration with Azure Key Vault integration

## Project Structure

```
mtgecorec/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── azure.yaml            # Azure deployment configuration
├── core/
│   └── data_engine/      # AI and data processing modules
│       ├── commander_recommender.py    # AI recommendation engine
│       ├── perplexity_client.py       # Perplexity AI integration
│       ├── cosmos_driver.py           # Database operations
│       └── synergy_analyzer.py        # Card synergy analysis
├── templates/            # HTML templates
│   ├── commander.html    # Commander deck builder interface
│   ├── cards.html       # Card browser
│   └── visualizations.html  # Data analytics dashboard
├── static/              # CSS, JS, and assets
├── infra/               # Bicep infrastructure templates
└── tests/               # Unit and integration tests
```

## Quick Start

### Local Development
```bash
# 1. Clone the repository
git clone https://github.com/mattgraham93/mtgecorec.git
cd mtgecorec

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your API keys and database connection strings

# 4. Run locally
python app.py
```

### Azure Deployment
```bash
# 1. Install Azure Developer CLI
curl -fsSL https://aka.ms/install-azd.sh | bash

# 2. Deploy to Azure
azd up
```

## Configuration

### Required Environment Variables
```bash
# Database
COSMOS_CONNECTION_STRING="your_cosmos_db_connection_string"

# AI Services  
PERPLEXITY_API_KEY="your_perplexity_api_key"

# Optional: External APIs
SCRYFALL_API_KEY="your_scryfall_api_key"
```

### Azure Resources
The application automatically provisions:
- **Azure App Service**: Web application hosting
- **Azure Cosmos DB**: MongoDB API database
- **Azure Key Vault**: Secure configuration storage
- **Azure Application Insights**: Monitoring and analytics

## Current Status

### Implemented Features
- [x] AI-powered Commander recommendations with Perplexity integration
- [x] Advanced card browsing with filtering and pagination (35,000+ cards)
- [x] Interactive data visualizations and analytics
- [x] Commander search and analysis system
- [x] Real-time card statistics and summaries
- [x] Azure deployment with Infrastructure as Code
- [x] Responsive Bootstrap UI with dark theme

### In Development  
- [ ] Advanced deck building tools (save/load decks)
- [ ] Price tracking and budget optimization
- [ ] Meta analysis and competitive insights
- [ ] User accounts and deck sharing

### Future Roadmap
- [ ] Machine learning-based meta predictions
- [ ] Tournament results integration
- [ ] Advanced deck testing and simulation
- [ ] Mobile app development

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE.md](LICENSE.md) for details.

## Links

- **Live Application**: [Deployed on Azure](https://your-app-name.azurewebsites.net)
- **Documentation**: [Project Wiki](https://github.com/mattgraham93/mtgecorec/wiki)
- **Issues**: [GitHub Issues](https://github.com/mattgraham93/mtgecorec/issues)

---
**Built for the MTG community** - Combining the power of AI with comprehensive data analytics to elevate your Commander game.
