# MTGEcoRec Changelog

<a name="0.0.3"></a>
# 0.0.3 (2025-12-16)

*Major Features*
* **Pricing Pipeline Overhaul**: Complete rewrite of Azure Functions pricing collection with upsert logic
* **Local Development Environment**: Created comprehensive local testing suite for rapid development
* **Duplicate Prevention**: Implemented robust upsert operations to prevent data duplication
* **Performance Optimization**: Achieved 20+ cards/second processing rate (100x improvement)
* **CosmosDB Optimization**: Fixed retryable writes compatibility and bulk operation issues

*Bug Fixes*
* **Massive Data Duplication**: Resolved 90% duplicate records issue (1.6M → 300K expected records)
* **Pipeline Freezing**: Fixed 4+ minute hangs during individual upsert operations
* **Azure Functions Timeout**: Implemented proper batch management and auto-chaining for 10-minute limits
* **Environment Configuration**: Standardized `.env` loading and COSMOS_CONNECTION_STRING handling
* **Bulk Operation Errors**: Resolved CosmosDB retryable writes conflicts with ordered bulk inserts

*Performance Improvements*
* **Database Cleanup**: Removed 594K duplicate records from production database
* **Upsert Logic**: Replaced error-prone inserts with proper replace_one operations
* **Bulk Processing**: Optimized batch sizes and connection settings for CosmosDB compatibility
* **Local Testing**: Created 100x faster development cycle vs Azure deployment testing

*Technical Debt Cleanup*
* **Diagnostic Tools**: Created comprehensive data analysis and cleanup utilities
* **Code Organization**: Improved pipeline structure and error handling
* **Documentation**: Added agent handover documentation and technical insights

*Infrastructure*
* **Azure Functions**: Updated deployment with timeout management and progress tracking
* **CosmosDB**: Optimized connection settings and bulk operation compatibility
* **Development Tools**: Local testing environment with production simulation capabilities

<a name="0.0.1-0.0.2"></a>
# 2.0.x (Previous Versions)
* Initial Azure deployment and basic pricing collection
* Flask web application with commander recommendations
* Perplexity AI integration for deck suggestions
* Basic CosmosDB integration and card data management
