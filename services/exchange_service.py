import httpx
from typing import Dict, Any, List
from datetime import datetime, timedelta

class ExchangeService:
    """
    Service for fetching exchange rates using DolarAPI
    No authentication required
    """
    
    BASE_URL = "https://dolarapi.com/v1"
    CACHE_DURATION = timedelta(minutes=15)  # Cache for 15 minutes
    
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
    
    async def get_all_dolares(self) -> List[Dict[str, Any]]:
        """Get all USD/ARS exchange rates"""
        cache_key = "all_dolares"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.BASE_URL}/dolares", timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            raise ValueError(f"Error fetching exchange rates: {str(e)}")
    
    async def get_dolar_especifico(self, tipo: str) -> Dict[str, Any]:
        """
        Get specific USD/ARS rate
        
        Args:
            tipo: Type of dollar (oficial, blue, bolsa, contadoconliqui, mayorista, cripto, tarjeta)
        
        Returns:
            Dict with compra, venta, fechaActualizacion
        """
        cache_key = f"dolar_{tipo}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.BASE_URL}/dolares/{tipo}", timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                # Normalize response
                result = {
                    "tipo": tipo,
                    "moneda": data.get("moneda", "USD"),
                    "casa": data.get("casa", tipo),
                    "nombre": data.get("nombre", tipo.title()),
                    "compra": data.get("compra"),
                    "venta": data.get("venta"),
                    "fecha_actualizacion": data.get("fechaActualizacion")
                }
                
                self._set_cache(cache_key, result)
                return result
        except Exception as e:
            raise ValueError(f"Error fetching {tipo} rate: {str(e)}")
    
    async def get_dolar_mep(self) -> Dict[str, Any]:
        """Get MEP (Bolsa) rate"""
        return await self.get_dolar_especifico("bolsa")
    
    async def get_dolar_blue(self) -> Dict[str, Any]:
        """Get Blue rate"""
        return await self.get_dolar_especifico("blue")
    
    async def get_dolar_oficial(self) -> Dict[str, Any]:
        """Get Official rate"""
        return await self.get_dolar_especifico("oficial")
    
    async def get_dolar_ccl(self) -> Dict[str, Any]:
        """Get CCL (Contado con Liquidación) rate"""
        return await self.get_dolar_especifico("contadoconliqui")
    
    async def get_dolar_tarjeta(self) -> Dict[str, Any]:
        """Get card/tourist rate"""
        return await self.get_dolar_especifico("tarjeta")

# Singleton instance
_exchange_service_instance = None

def get_exchange_service() -> ExchangeService:
    """Get singleton exchange service instance"""
    global _exchange_service_instance
    if _exchange_service_instance is None:
        _exchange_service_instance = ExchangeService()
    return _exchange_service_instance
