#!/usr/bin/env python3
"""
Local HTTP server to simulate Azure Functions HTTP triggers
"""

import os
import sys
import json
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class MockFunctionRequest:
    """Mock Azure Functions HttpRequest for local testing"""
    def __init__(self, method, url, headers, body):
        parsed_url = urlparse(url)
        self.method = method
        self.url = url
        self.headers = headers
        self.params = parse_qs(parsed_url.query)
        # Flatten single-item lists
        self.params = {k: v[0] if len(v) == 1 else v for k, v in self.params.items()}
        self._body = body
    
    def get_body(self):
        return self._body.encode() if isinstance(self._body, str) else self._body
    
    def get_json(self):
        if self._body:
            return json.loads(self._body)
        return {}

class MockFunctionResponse:
    """Mock Azure Functions HttpResponse for local testing"""
    def __init__(self, body, status_code=200, mimetype="text/plain", headers=None):
        self.body = body
        self.status_code = status_code
        self.mimetype = mimetype
        self.headers = headers or {}

class LocalFunctionsHandler(BaseHTTPRequestHandler):
    """HTTP handler for local Azure Functions testing"""
    
    def do_GET(self):
        self.handle_request('GET')
    
    def do_POST(self):
        self.handle_request('POST')
    
    def handle_request(self, method):
        # Load local settings
        self.load_local_settings()
        
        # Get request body for POST
        body = ""
        if method == 'POST':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
        
        # Create mock request
        mock_req = MockFunctionRequest(method, self.path, dict(self.headers), body)
        
        try:
            # Route to appropriate function
            if self.path.startswith('/api/collect_pricing'):
                response = self.call_collect_pricing(mock_req)
            elif self.path.startswith('/api/pricing/status'):
                response = self.call_pricing_status(mock_req)
            elif self.path.startswith('/api/pricing/reset_lock'):
                response = self.call_reset_lock(mock_req)
            elif self.path.startswith('/api/debug'):
                response = self.call_debug_modules(mock_req)
            else:
                response = MockFunctionResponse("Not Found", 404)
            
            # Send response
            self.send_response(response.status_code)
            self.send_header('Content-type', response.mimetype)
            for header, value in response.headers.items():
                self.send_header(header, value)
            self.end_headers()
            
            body_bytes = response.body.encode() if isinstance(response.body, str) else response.body
            self.wfile.write(body_bytes)
            
        except Exception as e:
            print(f"❌ Error handling request: {e}")
            import traceback
            traceback.print_exc()
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = json.dumps({
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            self.wfile.write(error_response.encode())
    
    def load_local_settings(self):
        """Load local.settings.json or use existing environment variables"""
        try:
            with open('local.settings.json', 'r') as f:
                settings = json.load(f)
                for key, value in settings.get('Values', {}).items():
                    if not value.startswith('REPLACE_WITH_YOUR'):  # Skip placeholder values
                        os.environ[key] = value
        except FileNotFoundError:
            pass  # Use existing environment variables
    
    def call_collect_pricing(self, req):
        """Call the collect_pricing function"""
        print(f"🚀 Local call: collect_pricing")
        
        # Import the actual function (create a simple wrapper)
        from pricing_pipeline import run_pricing_pipeline_azure_function
        
        # Parse parameters
        target_date = req.params.get('target_date')
        max_cards = req.params.get('max_cards')
        
        if not target_date:
            target_date = datetime.now().date().isoformat()
        
        if max_cards:
            try:
                max_cards = int(max_cards)
            except ValueError:
                max_cards = None
        
        # Handle POST body
        if req.method == 'POST':
            try:
                body_data = req.get_json()
                target_date = body_data.get('target_date', target_date)
                max_cards = body_data.get('max_cards', max_cards)
            except:
                pass
        
        print(f"📅 Target date: {target_date}")
        print(f"🔢 Max cards: {max_cards}")
        
        # Run the function
        result = run_pricing_pipeline_azure_function(
            target_date=target_date,
            max_cards=max_cards
        )
        
        # Format response
        response_data = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "function": "pricing_collection_local",
            **result
        }
        
        return MockFunctionResponse(
            json.dumps(response_data, indent=2),
            200,
            "application/json"
        )
    
    def call_pricing_status(self, req):
        """Call pricing status"""
        return MockFunctionResponse(
            json.dumps({"status": "local_mode", "message": "Running in local development mode"}),
            200,
            "application/json"
        )
    
    def call_reset_lock(self, req):
        """Reset lock (always works in local mode)"""
        return MockFunctionResponse(
            json.dumps({
                "status": "success",
                "message": "Lock reset (local mode)",
                "was_running": False,
                "now_running": False
            }),
            200,
            "application/json"
        )
    
    def call_debug_modules(self, req):
        """Debug modules"""
        return MockFunctionResponse(
            json.dumps({"modules": list(sys.modules.keys())[:10]}),
            200,
            "application/json"
        )

def start_local_server(port=7071):
    """Start the local development server"""
    print(f"🌐 Starting local Azure Functions server on port {port}")
    print(f"📍 Available endpoints:")
    print(f"   GET  http://localhost:{port}/api/collect_pricing")
    print(f"   POST http://localhost:{port}/api/collect_pricing")
    print(f"   GET  http://localhost:{port}/api/pricing/status")
    print(f"   POST http://localhost:{port}/api/pricing/reset_lock")
    print(f"")
    print(f"💡 Example usage:")
    print(f"   curl 'http://localhost:{port}/api/collect_pricing?max_cards=5'")
    print(f"")
    print(f"🛑 Press Ctrl+C to stop")
    
    server = HTTPServer(('localhost', port), LocalFunctionsHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n🛑 Stopping local server")
        server.server_close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Local Azure Functions HTTP server')
    parser.add_argument('--port', type=int, default=7071, help='Port to run server on')
    
    args = parser.parse_args()
    start_local_server(args.port)