
# MTG EcoRec: AI-Powered Commander Deck Builder & MTG Analytics

A modern web application that combines **AI-powered Commander deck building** with **comprehensive MTG data analytics**. Built for competitive players, data analysts, and MTG enthusiasts who want intelligent card recommendations backed by real-time analysis.

## Key Features

### AI Commander Deck Builder
- **Complete Commander Builder Interface**: Full deck building experience with side-by-side layout
- **Perplexity AI Integration**: Get intelligent card suggestions using advanced AI analysis
- **Visual Card Previews**: High-quality card images with automatic fallback handling
- **Commander Search & Selection**: Search any Commander with detailed printing options and thumbnail previews
- **Smart Export Features**: Export to Scryfall deck builder or text format with intelligent manabase suggestions
- **Synergy Detection**: AI identifies optimal card combinations and deck strategies
- **Power Level Optimization**: Recommendations tailored to your preferred power level

### Advanced Card Analytics
- **Paginated Card Browser**: Browse 35,000+ MTG cards with advanced filtering
- **Real-time Data Visualizations**: Interactive charts and statistics powered by Chart.js
- **Color & Type Analysis**: Deep dive into card distribution and trends
- **Set Statistics**: Comprehensive analysis across all MTG sets
- **Interactive Narrative**: Data storytelling with dynamic insights

### Smart Filtering & Search  
- **Multi-color Filtering**: Exclusive and inclusive color combinations
- **Card Type Filtering**: Filter by creatures, spells, artifacts, and more
- **Advanced Sorting**: Sort by name, CMC, power/toughness, and other attributes
- **Live Search**: Real-time search with instant results
- **Commander-specific Filters**: Filter by color identity, power level, and format legality

### User Experience
- **Responsive Design**: Bootstrap 5 with mobile-first approach
- **Dark Theme**: Professional dark purple theme optimized for long sessions
- **Authentication System**: Secure user accounts with session management
- **Progressive Loading**: Smooth performance with async data loading
- **Export Integration**: Seamless integration with Scryfall deck builder

## Tech Stack

### Backend
- **Python Flask**: Web framework with modern async capabilities
- **Azure Cosmos DB**: MongoDB API for scalable card data storage (35,000+ cards)
- **Perplexity AI**: Advanced AI for card analysis and recommendations
- **Scryfall API**: Comprehensive MTG card data integration with real-time updates
- **Authentication System**: Secure user session management with MongoDB integration

### Frontend  
- **Bootstrap 5**: Responsive, modern UI components with dark theme customization
- **Vanilla JavaScript**: Fast, lightweight interactive features with modular architecture
- **Chart.js**: Dynamic data visualizations with real-time updates
- **Progressive Enhancement**: Graceful degradation and async loading for optimal performance
- **Image Optimization**: Smart card image handling with automatic fallback mechanisms

### Infrastructure
- **Azure App Service**: Production hosting with auto-scaling
- **Azure Developer CLI (azd)**: Infrastructure as Code deployment
- **Bicep Templates**: Automated Azure resource provisioning
- **Environment Management**: Secure configuration with Azure Key Vault integration

## Project Structure

```
mtgecorec/
├── app.py                          # Main Flask application with authentication
├── requirements.txt                # Python dependencies
├── azure.yaml                     # Azure deployment configuration
├── auth.json                      # Authentication configuration
├── data_engine/                   # Core data processing and AI modules
│   ├── commander_recommender.py   # AI recommendation engine with image optimization
│   ├── cosmos_driver.py          # Database operations and user management
│   ├── scryfall.py               # Scryfall API integration
│   ├── main_driver.py            # Data pipeline orchestration
│   ├── justtcg.py               # Price data integration
│   └── exchange_rate.py          # Currency conversion utilities
├── templates/                     # Jinja2 HTML templates
│   ├── commander.html            # Complete Commander deck builder interface
│   ├── cards.html               # Advanced card browser with filtering
│   ├── visualizations.html      # Interactive data analytics dashboard
│   ├── narrative.html           # Data storytelling interface
│   ├── index.html              # Landing page with authentication
│   └── nav.html                # Navigation component
├── static/                       # Frontend assets
│   ├── css/
│   │   └── dark-purple.css      # Custom dark theme
│   ├── js/
│   │   ├── api.js              # API interaction layer
│   │   ├── visualizations.js   # Chart.js integrations
│   │   ├── main.js             # Core application logic
│   │   ├── charts.js           # Data visualization components
│   │   ├── table.js            # Interactive table components
│   │   ├── narrative.js        # Story-driven analytics
│   │   └── state.js            # Application state management
│   └── bootstrap/              # Bootstrap 5 framework
├── infra/                       # Azure Bicep infrastructure templates
│   ├── main.bicep             # Main infrastructure definition
│   ├── main.parameters.json   # Environment-specific parameters
│   └── core/                  # Modular infrastructure components
├── scripts/                    # Utility and maintenance scripts
├── notebooks/                  # Jupyter notebooks for data exploration
└── __pycache__/               # Python bytecode cache
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
export COSMOS_CONNECTION_STRING="your_cosmos_db_connection_string"
export PERPLEXITY_API_KEY="your_perplexity_api_key"

# 4. Configure authentication (optional)
# Edit auth.json with your user credentials

# 5. Run locally
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
# Database Configuration
COSMOS_CONNECTION_STRING="your_cosmos_db_connection_string"
COSMOS_DATABASE_NAME="mtg_cards"
COSMOS_COLLECTION_NAME="cards"

# AI Services  
PERPLEXITY_API_KEY="your_perplexity_api_key"

# Authentication (optional for development)
SECRET_KEY="your_flask_secret_key"

# External APIs (optional)
SCRYFALL_API_KEY="your_scryfall_api_key"
JUST_TCG_API_KEY="your_justtcg_api_key"
```

### Authentication Configuration
The application includes a built-in authentication system. Configure user accounts in `auth.json`:
```json
{
  "users": {
    "admin": {
      "password": "hashed_password",
      "role": "admin"
    }
  }
}
```

### Azure Resources
The application automatically provisions:
- **Azure App Service**: Web application hosting
- **Azure Cosmos DB**: MongoDB API database
- **Azure Key Vault**: Secure configuration storage
- **Azure Application Insights**: Monitoring and analytics

## Current Status

### ✅ Fully Implemented Features
- [x] **Complete Commander Deck Builder** - Full interface with AI recommendations and export functionality
- [x] **Visual Card Display** - High-quality images with smart fallback handling
- [x] **Side-by-side Layout** - Commander printings and images in optimized layout
- [x] **Export Integration** - Scryfall deck builder export with intelligent manabase suggestions
- [x] **Authentication System** - Secure user accounts with session management
- [x] **Advanced Card Browser** - 35,000+ cards with filtering, pagination, and search
- [x] **Interactive Data Visualizations** - Real-time charts and analytics with Chart.js
- [x] **AI-Powered Recommendations** - Perplexity AI integration for strategic card suggestions
- [x] **Responsive Design** - Mobile-first Bootstrap 5 with custom dark theme
- [x] **Azure Deployment** - Production-ready Infrastructure as Code with Bicep
- [x] **Progressive Loading** - Optimized performance with async data handling

### 🚧 In Development  
- [ ] Advanced deck management (save/load/share decks)
- [ ] Price tracking and budget optimization with TCG Player integration
- [ ] Meta analysis and competitive insights
- [ ] Deck testing and goldfish simulation
- [ ] Enhanced AI recommendations with meta awareness

### 🔮 Future Roadmap
- [ ] Machine learning-based meta predictions and trend analysis
- [ ] Tournament results integration and competitive insights
- [ ] Advanced deck optimization algorithms
- [ ] Mobile app development (React Native)
- [ ] Community features (deck sharing, comments, ratings)
- [ ] Advanced analytics (win rates, meta positioning)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE.md](LICENSE.md) for details.

## Screenshots

### Commander Deck Builder
![Commander Builder Interface](static/images/commander-builder-screenshot.png)
*Complete deck building experience with AI recommendations and visual card previews*

### Data Visualizations
![Analytics Dashboard](static/images/analytics-dashboard-screenshot.png)
*Interactive charts and data insights powered by Chart.js*

### Card Browser
![Card Browser](static/images/card-browser-screenshot.png)
*Advanced filtering and search across 35,000+ MTG cards*

## Performance Features

- **Fast Loading**: Optimized queries and image caching for sub-second response times
- **Mobile Responsive**: Fully functional on all device sizes with touch-optimized interactions
- **Progressive Enhancement**: Core functionality works even with JavaScript disabled
- **Error Handling**: Graceful degradation with comprehensive error recovery
- **Accessibility**: WCAG 2.1 AA compliant with screen reader support

## API Integration

- **Scryfall API**: Real-time card data and high-resolution images
- **Perplexity AI**: Advanced natural language processing for card recommendations
- **Azure Cosmos DB**: Globally distributed database with 99.99% SLA
- **Chart.js**: Interactive data visualizations with real-time updates

## Links

- **Live Application**: [Deployed on Azure](https://your-app-name.azurewebsites.net)
- **Documentation**: [Project Wiki](https://github.com/mattgraham93/mtgecorec/wiki)
- **Issues**: [GitHub Issues](https://github.com/mattgraham93/mtgecorec/issues)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---
**Built for the MTG community** - Combining the power of AI with comprehensive data analytics to elevate your Commander game. From casual deck building to competitive analysis, MTG EcoRec provides the tools and insights you need to optimize your gameplay.
