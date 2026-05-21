# FastAPI IP2Location Middleware

A high-performance, asynchronous FastAPI middleware that automatically geolocates incoming requests using the [IP2Location](https://www.ip2location.com/) database or the [IP2Location.io](https://www.ip2location.io/) API. It seamlessly injects the geolocation data directly into the `request.state.location` object for easy access in your route handlers.

## Features

- **Dual Mode Support**: Use a local `.BIN` database for ultra-fast, zero-latency lookups, or use the IP2Location.io API if you don't want to host the database.
- **Async & Connection Pooling**: Built with `httpx` for non-blocking API calls, utilizing connection pooling to ensure high throughput.
- **Proxy Aware**: Automatically extracts the real client IP from headers like `X-Forwarded-For` or `X-Real-IP` when deployed behind load balancers or reverse proxies (like Nginx, Cloudflare, or AWS ALB).
- **Local Development Friendly**: Includes a `test_ip` parameter to easily override `127.0.0.1` and test specific geographic locations locally.
- **Multilingual Support**: Supports the `language` parameter (API mode) to return localized names for countries, regions, and cities.
- **Graceful Degradation**: Never crashes your app. If a lookup fails, it safely injects an error message into the state object so your app can decide how to handle it.

## Installation

Install the package via pip:

```bash
pip install fastapi-ip2location
```

## Prerequisites

You need at least one of the following to use this middleware:

- Local Database (.BIN): Download a free IP2Location Lite database (e.g., DB11) from IP2Location Lite.

- API Key: Sign up for an API key at IP2Location.io.

## Usage Examples

1. Using the Local Database (Recommended for Production)

```python
from fastapi import FastAPI, Request
from fastapi_ip2location import IP2LocationMiddleware

app = FastAPI()

app.add_middleware(
    IP2LocationMiddleware, 
    bin_path="IP2LOCATION-LITE-DB11.BIN", # Path to your downloaded .BIN file
    # use_memory=True # Only use this if you have plenty of memory.
)

@app.get("/")
async def get_location(request: Request):
    return {"your_location": request.state.location}
```

2. Using the IP2Location.io API
```python
import os
from fastapi import FastAPI, Request
from fastapi_ip2location import IP2LocationMiddleware

app = FastAPI()

app.add_middleware(
    IP2LocationMiddleware, 
    api_key=os.getenv("IP2LOCATION_API_KEY")
)

@app.get("/")
async def get_location(request: Request):
    return {"your_location": request.state.location}
```

## Advanced Configuration

You can fully customize the middleware to suit your environment:

```python
app.add_middleware(
    IP2LocationMiddleware,
    bin_path="IP2LOCATION-LITE-DB11.BIN",
    api_key="OPTIONAL_FALLBACK_KEY",
    
    # Checks these headers first for the real IP. 
    # Defaults to ["X-Forwarded-For", "X-Real-IP"]
    ip_headers=["X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"], 
    
    # If the user connects from localhost (127.0.0.1), pretend they are 
    # connecting from this IP instead. Great for local testing!
    test_ip="8.8.8.8", 
    
    # Translate country/city names (Requires API mode and a supported plan)
    language="fr" 
)
```

## Accessing the Data

The middleware standardizes the output regardless of whether you use the .BIN file or the API. The dictionary injected into request.state.location includes the following keys:

```json
{
    "ip": "8.8.8.8",
    "country_short": "US",
    "country_long": "United States",
    "region": "California",
    "city": "Mountain View",
    "latitude": 37.40599,
    "longitude": -122.078514,
    "zipcode": "94043",
    "timezone": "-07:00",
    "error": null
}
```

*(Note: Premium data fields like isp, domain, netspeed, weather, and proxy data will also be populated if your specific .BIN file or API plan supports them).*

## License

This project is licensed under the MIT License.