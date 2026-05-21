import os
import httpx
import IP2Location
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List

class IP2LocationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app, 
        bin_path: Optional[str] = None, 
        api_key: Optional[str] = None,
        use_memory: bool = True,
        ip_headers: Optional[List[str]] = None,
        test_ip: Optional[str] = None,
        language: Optional[str] = None  # Added language parameter
    ):
        super().__init__(app)
        
        # Validation: Must have at least one method of lookup
        if not bin_path and not api_key:
            raise ValueError(
                "Configuration Error: You must provide either 'bin_path' (for local BIN file) "
                "or 'api_key' (for IP2Location.io API)."
            )
            
        self.db_path = bin_path
        self.api_key = api_key
        self.ip_headers = ip_headers or ["X-Forwarded-For", "X-Real-IP"]
        self.test_ip = test_ip
        self.language = language
        
        self.ip2loc_db = None
        self.http_client = None  # Placeholder for our HTTP connection pool
        
        # Initialize Local DB if a path is provided
        if self.db_path:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"IP2Location database not found at {self.db_path}")
            try:
                mode = "SHARED_MEMORY" if use_memory else "FILE_IO"
                self.ip2loc_db = IP2Location.IP2Location(self.db_path, mode)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize IP2Location database: {e}")

    def _get_client_ip(self, request: Request) -> str:
        """Extracts the real client IP, respecting proxy headers and test IPs."""
        client_ip = None
        
        # 1. Check Headers first
        for header in self.ip_headers:
            if header in request.headers:
                client_ip = request.headers[header].split(",")[0].strip()
                break
                
        # 2. Fallback to direct connection IP
        if not client_ip:
            client_ip = request.client.host if request.client else "127.0.0.1"

        # 3. OVERRIDE: If it's a local IP and a test_ip is provided, use the test_ip
        if self.test_ip and client_ip in ("127.0.0.1", "::1", "localhost"):
            return self.test_ip
            
        return client_ip

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        # Base location object
        location_data = {
            "ip": client_ip,
            "error": None
        }
        
        try:
            # 1. Prioritize Local DB if both are provided (faster, no network latency)
            if self.ip2loc_db:
                record = self.ip2loc_db.get_all(client_ip)
                location_data.update({
                    "country_short": getattr(record, 'country_short', None),
                    "country_long": getattr(record, 'country_long', None),
                    "region": getattr(record, 'region', None),
                    "city": getattr(record, 'city', None),
                    "district": getattr(record, 'district', None),
                    "isp": getattr(record, 'isp', None),
                    "latitude": getattr(record, 'latitude', None),
                    "longitude": getattr(record, 'longitude', None),
                    "domain": getattr(record, 'domain', None),
                    "zipcode": getattr(record, 'zipcode', None),
                    "timezone": getattr(record, 'timezone', None),
                    "netspeed": getattr(record, 'netspeed', None),
                    "idd_code": getattr(record, 'idd_code', None),
                    "area_code": getattr(record, 'area_code', None),
                    "weather_code": getattr(record, 'weather_code', None),
                    "weather_name": getattr(record, 'weather_name', None),
                    "mcc": getattr(record, 'mcc', None),
                    "mnc": getattr(record, 'mnc', None),
                    "mobile_brand": getattr(record, 'mobile_brand', None),
                    "elevation": getattr(record, 'elevation', None),
                    "usage_type": getattr(record, 'usage_type', None),
                    "address_type": getattr(record, 'address_type', None),
                    "category": getattr(record, 'category', None),
                    "asn": getattr(record, 'asn', None),
                    "as_name": getattr(record, 'as_name', None),
                    "as_domain": getattr(record, 'as_domain', None),
                    "as_usagetype": getattr(record, 'as_usagetype', None),
                    "as_cidr": getattr(record, 'as_cidr', None),
                })
                
            # 2. Fallback to API if DB is not configured
            elif self.api_key:
                # Initialize the httpx client once per application lifecycle (Connection Pooling)
                if self.http_client is None:
                    self.http_client = httpx.AsyncClient()
                
                # Construct the API URL
                api_url = f"https://api.ip2location.io/?key={self.api_key}&ip={client_ip}"
                
                # Append the language parameter if provided (ignored if free plan drops it)
                if self.language:
                    api_url += f"&lang={self.language}"
                
                # Make the non-blocking asynchronous request using the pooled client
                response = await self.http_client.get(api_url)
                response.raise_for_status()
                data = response.json()
                
                # Map API response keys to match our standard format
                location_data.update({
                    "country_short": data.get("country_code"),
                    "country_long": data.get("country_name"),
                    "region": data.get("region_name"),
                    "city": data.get("city_name"),
                    "district": data.get("district"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "zipcode": data.get("zip_code"),
                    "timezone": data.get("time_zone"),
                    "asn": data.get("asn"),
                    "as": data.get("as"),
                    "isp": data.get("isp"),
                    "domain": data.get("domain"),
                    "net_speed": data.get("net_speed"),
                    "idd_code": data.get("idd_code"),
                    "area_code": data.get("area_code"),
                    "weather_station_code": data.get("weather_station_code"),
                    "weather_station_name": data.get("weather_station_name"),
                    "mcc": data.get("mcc"),
                    "mnc": data.get("mnc"),
                    "mobile_brand": data.get("mobile_brand"),
                    "elevation": data.get("elevation"),
                    "usage_type": data.get("usage_type"),
                    "address_type": data.get("address_type"),
                    "ads_category": data.get("ads_category"),
                    "ads_category_name": data.get("ads_category_name"),
                    # AS info data
                    "as_name": data.get("as_info", {}).get("as_name"),
                    "as_number": data.get("as_info", {}).get("as_number"),
                    "as_domain": data.get("as_info", {}).get("as_domain"),
                    "as_cidr": data.get("as_info", {}).get("as_cidr"),
                    "as_usage_type": data.get("as_info", {}).get("as_usage_type"),
                    # Continent data
                    "continent_name": data.get("continent", {}).get("name"),
                    "continent_code": data.get("continent", {}).get("code"),
                    "continent_hemisphere": data.get("continent", {}).get("hemisphere"),
                    "continent_translation": data.get("continent", {}).get("translation"),
                    # Country data
                    "country_name": data.get("country", {}).get("name"),
                    "country_alpha3_code": data.get("country", {}).get("alpha3_code"),
                    "country_numeric_code": data.get("country", {}).get("numeric_code"),
                    "country_demonym": data.get("country", {}).get("demonym"),
                    "country_flag": data.get("country", {}).get("flag"),
                    "country_capital": data.get("country", {}).get("capital"),
                    "country_total_area": data.get("country", {}).get("total_area"),
                    "country_population": data.get("country", {}).get("population"),
                    "country_currency": data.get("country", {}).get("currency"),
                    "country_language": data.get("country", {}).get("language"),
                    "country_tld": data.get("country", {}).get("tld"),
                    "country_translation": data.get("country", {}).get("translation"),
                    # Region data
                    "region_name": data.get("region", {}).get("name"),
                    "region_code": data.get("region", {}).get("code"),
                    "region_translation": data.get("region", {}).get("translation"),
                    # City data
                    "city_name": data.get("city", {}).get("name"),
                    "city_translation": data.get("city", {}).get("translation"),
                    # Time Zone Info data
                    "time_zone_olson": data.get("time_zone_info", {}).get("olson"),
                    "time_zone_current_time": data.get("time_zone_info", {}).get("current_time"),
                    "time_zone_gmt_offset": data.get("time_zone_info", {}).get("gmt_offset"),
                    "time_zone_is_dst": data.get("time_zone_info", {}).get("is_dst"),
                    "time_zone_abbreviation": data.get("time_zone_info", {}).get("abbreviation"),
                    "time_zone_dst_start_date": data.get("time_zone_info", {}).get("dst_start_date"),
                    "time_zone_dst_end_date": data.get("time_zone_info", {}).get("dst_end_date"),
                    "time_zone_sunrise": data.get("time_zone_info", {}).get("sunrise"),
                    "time_zone_sunset": data.get("time_zone_info", {}).get("sunset"),
                    # Geotargeting data
                    "geotargeting_metro": data.get("geotargeting", {}).get("metro"),
                    "is_proxy": data.get("is_proxy"),
                    "fraud_score": data.get("fraud_score"),
                    # Proxy data
                    "proxy_last_seen": data.get("proxy", {}).get("last_seen"),
                    "proxy_type": data.get("proxy", {}).get("proxy_type"),
                    "proxy_threat": data.get("proxy", {}).get("threat"),
                    "proxy_provider": data.get("proxy", {}).get("provider"),
                    "proxy_is_vpn": data.get("proxy", {}).get("is_vpn"),
                    "proxy_is_tor": data.get("proxy", {}).get("is_tor"),
                    "proxy_is_data_center": data.get("proxy", {}).get("is_data_center"),
                    "proxy_is_public_proxy": data.get("proxy", {}).get("is_public_proxy"),
                    "proxy_is_web_proxy": data.get("proxy", {}).get("is_web_proxy"),
                    "proxy_is_web_crawler": data.get("proxy", {}).get("is_web_crawler"),
                    "proxy_is_ai_crawler": data.get("proxy", {}).get("is_ai_crawler"),
                    "proxy_is_residential_proxy": data.get("proxy", {}).get("is_residential_proxy"),
                    "proxy_is_spammer": data.get("proxy", {}).get("is_spammer"),
                    "proxy_is_scanner": data.get("proxy", {}).get("is_scanner"),
                    "proxy_is_botnet": data.get("proxy", {}).get("is_botnet"),
                    "proxy_is_bogon": data.get("proxy", {}).get("is_bogon"),
                    "proxy_is_consumer_privacy_network": data.get("proxy", {}).get("is_consumer_privacy_network"),
                    "proxy_is_enterprise_private_network": data.get("proxy", {}).get("is_enterprise_private_network"),
                })
                    
        except Exception as e:
            location_data["error"] = f"Lookup failed: {str(e)}"

        # Inject into the FastAPI request state with the generic 'location' key
        request.state.location = location_data

        # Continue the request lifecycle
        return await call_next(request)