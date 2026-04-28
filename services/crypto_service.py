import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class CryptoService:
    """
    Service for fetching cryptocurrency prices using CoinGecko API
    No authentication required for basic usage
    """
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    CACHE_DURATION = timedelta(minutes=2)  # Cache for 2 minutes (crypto changes fast)
    
    def __init__(self):
        self._cache: Dict[str, tuple[datetime, Any]] = {}
    
    def _get_cached(self, key: str) -> Any:
        """Get cached data if still valid"""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if datetime.now() - timestamp < self.CACHE_DURATION:
                return data
        return None
    
    def _set_cache(self, key: str, data: Any):
        """Set cache data"""
        self._cache[key] = (datetime.now(), data)
    
    async def get_precio_simple(
        self,
        ids: List[str],
        vs_currencies: List[str] = ["usd", "ars"],
        include_24hr_change: bool = True,
        include_market_cap: bool = True
    ) -> Dict[str, Any]:
        """
        Get simple price for cryptocurrencies
        
        Args:
            ids: List of crypto IDs (e.g., ["bitcoin", "ethereum"])
            vs_currencies: List of currencies (e.g., ["usd", "ars"])
            include_24hr_change: Include 24h price change
            include_market_cap: Include market cap
        
        Returns:
            Dict with prices and additional data
        """
        cache_key = f"price_{'_'.join(ids)}_{'_'.join(vs_currencies)}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            params = {
                "ids": ",".join(ids),
                "vs_currencies": ",".join(vs_currencies),
                "include_24hr_change": str(include_24hr_change).lower(),
                "include_market_cap": str(include_market_cap).lower()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/simple/price",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            raise ValueError(f"Error fetching crypto prices: {str(e)}")
    
    async def get_crypto(self, crypto_id: str) -> Dict[str, Any]:
        """
        Get price for a single cryptocurrency in USD and ARS
        
        Args:
            crypto_id: Crypto ID (bitcoin, ethereum, cardano, etc.)
        
        Returns:
            Dict with normalized price data
        """
        data = await self.get_precio_simple([crypto_id], ["usd", "ars"])
        
        if crypto_id not in data:
            raise ValueError(f"Cryptocurrency '{crypto_id}' not found")
        
        crypto_data = data[crypto_id]
        
        return {
            "id": crypto_id,
            "nombre": crypto_id.title(),
            "precio_usd": crypto_data.get("usd"),
            "precio_ars": crypto_data.get("ars"),
            "cambio_24h_usd": crypto_data.get("usd_24h_change"),
            "market_cap_usd": crypto_data.get("usd_market_cap"),
            "fecha_actualizacion": datetime.now().isoformat()
        }
    
    async def get_top_cryptos(
        self,
        vs_currency: str = "usd",
        limit: int = 10,
        order: str = "market_cap_desc"
    ) -> List[Dict[str, Any]]:
        """
        Get top cryptocurrencies by market cap
        
        Args:
            vs_currency: Currency (usd, ars, eur, etc.)
            limit: Number of results (1-250)
            order: Sort order (market_cap_desc, volume_desc, etc.)
        
        Returns:
            List of top cryptocurrencies with detailed data
        """
        cache_key = f"top_{limit}_{vs_currency}_{order}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            params = {
                "vs_currency": vs_currency,
                "order": order,
                "per_page": limit,
                "page": 1,
                "sparkline": False
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/coins/markets",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Normalize response
                results = []
                for coin in data:
                    results.append({
                        "id": coin.get("id"),
                        "simbolo": coin.get("symbol", "").upper(),
                        "nombre": coin.get("name"),
                        "precio_actual": coin.get("current_price"),
                        "market_cap": coin.get("market_cap"),
                        "volumen_24h": coin.get("total_volume"),
                        "cambio_24h": coin.get("price_change_percentage_24h"),
                        "imagen": coin.get("image"),
                        "moneda": vs_currency.upper()
                    })
                
                self._set_cache(cache_key, results)
                return results
        except Exception as e:
            raise ValueError(f"Error fetching top cryptos: {str(e)}")
    
    async def get_multiples_cryptos(self, crypto_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get prices for multiple cryptocurrencies
        
        Args:
            crypto_ids: List of crypto IDs
        
        Returns:
            List of crypto price data
        """
        data = await self.get_precio_simple(crypto_ids, ["usd", "ars"])
        
        results = []
        for crypto_id in crypto_ids:
            if crypto_id in data:
                crypto_data = data[crypto_id]
                results.append({
                    "id": crypto_id,
                    "nombre": crypto_id.title(),
                    "precio_usd": crypto_data.get("usd"),
                    "precio_ars": crypto_data.get("ars"),
                    "cambio_24h_usd": crypto_data.get("usd_24h_change"),
                    "market_cap_usd": crypto_data.get("usd_market_cap")
                })
        
        return results

# Singleton instance
_crypto_service_instance = None

def get_crypto_service() -> CryptoService:
    """Get singleton crypto service instance"""
    global _crypto_service_instance
    if _crypto_service_instance is None:
        _crypto_service_instance = CryptoService()
    return _crypto_service_instance
