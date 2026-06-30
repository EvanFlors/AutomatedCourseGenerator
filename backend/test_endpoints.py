#!/usr/bin/env python3
"""Quick script to verify all endpoints are registered and documented."""

import sys
sys.path.insert(0, 'src')

from cogenai.interfaces.api.app import app

print("=" * 70)
print("FASTAPI ENDPOINT REGISTRATION CHECK")
print("=" * 70)

# Check registered routes
print("\n1. REGISTERED ROUTES (from app.routes):")
print("-" * 70)
http_routes = []
ws_routes = []

for route in app.routes:
    if hasattr(route, 'methods') and route.methods:
        methods = sorted(route.methods - {'HEAD', 'OPTIONS'})
        if methods:
            http_routes.append((methods, route.path))
    elif hasattr(route, 'path'):
        ws_routes.append(route.path)

for methods, path in sorted(http_routes, key=lambda x: x[1]):
    method_str = ', '.join(methods)
    print(f"   {method_str:20} {path}")

if ws_routes:
    for path in sorted(ws_routes):
        print(f"   {'WEBSOCKET':20} {path}")

# Check OpenAPI schema
print("\n2. OPENAPI SCHEMA (what appears in /docs):")
print("-" * 70)
schema = app.openapi()
paths = schema.get('paths', {})

for path in sorted(paths.keys()):
    methods = list(paths[path].keys())
    for method in methods:
        endpoint_data = paths[path][method]
        summary = endpoint_data.get('summary', 'No summary')
        print(f"   {method.upper():20} {path}")
        print(f"   {'':20} └─ {summary}")

print("\n3. SUMMARY:")
print("-" * 70)
print(f"   Total HTTP routes registered: {len(http_routes)}")
print(f"   Total WebSocket routes: {len(ws_routes)}")
print(f"   Total in OpenAPI schema: {len(paths)}")
print(f"   Missing from docs: {len(http_routes) - len(paths)}")

if len(http_routes) - len(paths) > 0:
    print("\n⚠️  Some HTTP endpoints are NOT in the OpenAPI schema!")
    registered_paths = {path for _, path in http_routes}
    documented_paths = set(paths.keys())
    missing = registered_paths - documented_paths - {'/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'}
    if missing:
        print(f"   Missing: {missing}")
else:
    print("\n✅ All HTTP endpoints are properly documented!")

print("\n" + "=" * 70)
print(f"\nView docs at: http://localhost:8000/docs")
print(f"View OpenAPI JSON at: http://localhost:8000/openapi.json")
print("=" * 70)
