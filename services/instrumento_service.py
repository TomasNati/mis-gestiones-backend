import re
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class InstrumentoService:
    """
    Service for fetching the latest price of a financial instrument by scraping
    the public IOL quote page.

    The page exposes price + currency symbol inside an outer container:

        <span id="IdTitulo" data-field="IDTitulo" ...>
            <span>US$</span>
            <span data-field="UltimoPrecio">115,45</span>
        </span>
    """

    BASE_URL = "https://iol.invertironline.com/titulo/cotizacion/BCBA/{ticker}"
    CACHE_DURATION = timedelta(minutes=2)

    # Outer container that wraps both the currency symbol and the price.
    # The lazy `.*?</span>` plus `\s*</span>` anchors on two consecutive closing
    # tags (price span + outer container) and keeps the price's closing tag in
    # the captured group so PRICE_PATTERN can still match inside it.
    ID_TITULO_BLOCK = re.compile(
        r'<span[^>]*id=["\']IdTitulo["\'][^>]*>(.*?</span>)\s*</span>',
        re.IGNORECASE | re.DOTALL,
    )
    # First inner <span> that does NOT carry a data-field attribute — the
    # currency symbol ($ for ARS, US$ for USD).
    CURRENCY_PATTERN = re.compile(
        r'<span(?![^>]*data-field)[^>]*>\s*((?:US?)?\$)\s*</span>',
        re.IGNORECASE,
    )
    # Price span.
    PRICE_PATTERN = re.compile(
        r'<span[^>]*data-field=["\']UltimoPrecio["\'][^>]*>([^<]+)</span>',
        re.IGNORECASE,
    )
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    }

    def __init__(self):
        self._cache: Dict[str, tuple[datetime, Any]] = {}

    def _get_cached(self, key: str) -> Any:
        if key in self._cache:
            timestamp, data = self._cache[key]
            if datetime.now() - timestamp < self.CACHE_DURATION:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = (datetime.now(), data)

    @staticmethod
    def _parse_ar_number(raw: str) -> float:
        """Convert AR-formatted '49.480,00' to 49480.00."""
        return float(raw.strip().replace(".", "").replace(",", "."))

    @staticmethod
    def _normalize_currency(symbol: Optional[str]) -> str:
        """Map the raw symbol to an ISO-ish code: 'US$' → 'USD', '$' → 'ARS'."""
        if not symbol:
            return "ARS"
        s = symbol.strip().upper()
        if s == "US$":
            return "USD"
        if s == "$":
            return "ARS"
        return s

    async def get_price(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch the latest price + currency for an instrument.

        Args:
            ticker: instrument symbol as it appears in the IOL URL
                    (e.g., 'AAPL', 'GGAL', 'AL30').

        Returns:
            Dict with ticker, precio (float), precio_raw (str),
            simbolo_moneda (raw, e.g. 'US$'), moneda (normalized, e.g. 'USD'),
            fuente, url, fecha_consulta.

        Raises:
            ValueError: ticker missing, page not found, or price unparseable.
            ConnectionError: network error reaching IOL.
        """
        ticker_upper = ticker.strip().upper()
        if not ticker_upper:
            raise ValueError("ticker must not be empty")

        cache_key = f"instrumento_{ticker_upper}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = self.BASE_URL.format(ticker=ticker_upper)

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.get(url, headers=self.HEADERS)
        except httpx.RequestError as e:
            raise ConnectionError(f"Error reaching IOL page for '{ticker_upper}': {str(e)}")

        if response.status_code == 404:
            raise ValueError(f"Instrument '{ticker_upper}' not found at IOL")
        if response.status_code >= 400:
            raise ValueError(
                f"IOL returned status {response.status_code} for '{ticker_upper}'"
            )

        html = response.text

        block_match = self.ID_TITULO_BLOCK.search(html)
        search_scope = block_match.group(1) if block_match else html

        price_match = self.PRICE_PATTERN.search(search_scope)
        if not price_match:
            raise ValueError(
                f"Could not find latest price element on IOL page for '{ticker_upper}'"
            )

        raw_price = price_match.group(1).strip()
        try:
            price = self._parse_ar_number(raw_price)
        except ValueError:
            raise ValueError(
                f"Could not parse price '{raw_price}' for '{ticker_upper}'"
            )

        currency_match = self.CURRENCY_PATTERN.search(search_scope)
        simbolo_moneda = currency_match.group(1).strip() if currency_match else "$"
        moneda = self._normalize_currency(simbolo_moneda)

        result = {
            "ticker": ticker_upper,
            "precio": price,
            "precio_raw": raw_price,
            "simbolo_moneda": simbolo_moneda,
            "moneda": moneda,
            "fuente": "iol.invertironline.com",
            "url": url,
            "fecha_consulta": datetime.now().isoformat(timespec="seconds"),
        }
        self._set_cache(cache_key, result)
        return result


_instrumento_service_instance = None


def get_instrumento_service() -> InstrumentoService:
    """Get singleton instrumento service instance"""
    global _instrumento_service_instance
    if _instrumento_service_instance is None:
        _instrumento_service_instance = InstrumentoService()
    return _instrumento_service_instance
