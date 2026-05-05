import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta


class InvalidFilterError(ValueError):
    """Caller did not provide enough filters to perform a search."""


class FCIService:
    """
    Service for fetching mutual fund (FCI) quotes from CAFCI.

    The CAFCI API rejects direct calls with 403 unless the public ficha page
    has been visited first in the same session, so we hit the HTML page to
    pick up cookies and then call the JSON endpoint.

    Flow:
        1. GET https://www.cafci.org.ar/ficha-fondo.html?q=<fondo_id>;<clase_id>
        2. GET https://api.pub.cafci.org.ar/fondo/<fondo_id>/clase/<clase_id>/ficha
    """

    FICHA_URL = "https://www.cafci.org.ar/ficha-fondo.html?q={fondo_id};{clase_id}"
    API_URL = "https://api.pub.cafci.org.ar/fondo/{fondo_id}/clase/{clase_id}/ficha"
    LIST_URL = (
        "https://api.pub.cafci.org.ar/fondo"
        "?estado=1"
        "&include=entidad;depositaria,entidad;gerente,tipoRenta,tipoRentaMixta,"
        "region,benchmark,horizonte,duration,tipo_fondo,clase_fondo"
        "&limit=0"
        "&order=clase_fondos.nombre"
    )
    CACHE_DURATION = timedelta(minutes=15)
    LIST_CACHE_DURATION = timedelta(hours=24)

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    }

    MONEDA_MAP = {
        "1": "ARS",
        "2": "USD",
    }

    def __init__(self):
        self._cache: Dict[str, tuple[datetime, Any]] = {}
        self._list_cache: Optional[tuple[datetime, List[Dict[str, Any]]]] = None

    def _get_cached(self, key: str) -> Any:
        if key in self._cache:
            timestamp, data = self._cache[key]
            if datetime.now() - timestamp < self.CACHE_DURATION:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = (datetime.now(), data)

    @staticmethod
    def _validate_numeric(value: str, field: str) -> str:
        v = value.strip()
        if not v.isdigit():
            raise ValueError(f"{field} must be a positive integer, got '{value}'")
        return v

    @classmethod
    def _normalize_moneda(cls, moneda_id: Any) -> str:
        if moneda_id is None:
            return "ARS"
        return cls.MONEDA_MAP.get(str(moneda_id), str(moneda_id))

    async def get_quote(self, fondo_id: str, clase_id: str) -> Dict[str, Any]:
        """
        Fetch the latest FCI quote.

        Args:
            fondo_id: parent fondo id, the first number in the CAFCI URL
                      `.../fondo/<fondo_id>/clase/<clase_id>/ficha` (e.g. '739').
            clase_id: clase_fondo id, the second number in the same URL
                      (e.g. '1611').

        Returns:
            Dict with fondo_id, clase_id, nombre, moneda, fecha, vcp_unitario,
            fuente, url, fecha_consulta.

        Raises:
            ValueError: invalid input or unparseable response.
            ConnectionError: network error reaching CAFCI.
        """
        fondo_id_v = self._validate_numeric(fondo_id, "fondo_id")
        clase_id_v = self._validate_numeric(clase_id, "clase_id")

        cache_key = f"fci_{fondo_id_v}_{clase_id_v}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        ficha_url = self.FICHA_URL.format(fondo_id=fondo_id_v, clase_id=clase_id_v)
        api_url = self.API_URL.format(fondo_id=fondo_id_v, clase_id=clase_id_v)

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                ficha_resp = await client.get(ficha_url, headers=self.HEADERS)
                if ficha_resp.status_code >= 400:
                    raise ValueError(
                        f"CAFCI ficha page returned status {ficha_resp.status_code} "
                        f"for fondo_id={fondo_id_v} clase_id={clase_id_v}"
                    )

                api_headers = {**self.HEADERS, "Accept": "application/json", "Referer": ficha_url}
                api_resp = await client.get(api_url, headers=api_headers)
        except httpx.RequestError as e:
            raise ConnectionError(
                f"Error reaching CAFCI for fondo_id={fondo_id_v} clase_id={clase_id_v}: {str(e)}"
            )

        if api_resp.status_code == 404:
            raise ValueError(f"FCI not found for fondo_id={fondo_id_v} clase_id={clase_id_v}")
        if api_resp.status_code >= 400:
            raise ValueError(
                f"CAFCI API returned status {api_resp.status_code} for "
                f"fondo_id={fondo_id_v} clase_id={clase_id_v}"
            )

        try:
            payload = api_resp.json()
        except ValueError:
            raise ValueError("CAFCI API returned a non-JSON response")

        if not payload.get("success"):
            raise ValueError(
                f"CAFCI API reported failure for fondo_id={fondo_id_v} clase_id={clase_id_v}"
            )

        data = payload.get("data") or {}
        model = data.get("model") or {}
        actual = ((data.get("info") or {}).get("diaria") or {}).get("actual") or {}

        vcp_raw = actual.get("vcpUnitario")
        if vcp_raw is None:
            raise ValueError(
                f"CAFCI response is missing vcpUnitario for "
                f"fondo_id={fondo_id_v} clase_id={clase_id_v}"
            )

        try:
            vcp_unitario = float(vcp_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Could not parse vcpUnitario '{vcp_raw}'")

        result = {
            "fondo_id": fondo_id_v,
            "clase_id": clase_id_v,
            "nombre": model.get("nombre"),
            "moneda": self._normalize_moneda(model.get("monedaId")),
            "fecha": actual.get("fecha"),
            "vcp_unitario": vcp_unitario,
            "fuente": "cafci.org.ar",
            "url": ficha_url,
            "fecha_consulta": datetime.now().isoformat(timespec="seconds"),
        }
        self._set_cache(cache_key, result)
        return result

    async def list_all(self, clear_cache: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch the full FCI catalog from CAFCI.

        Cached for 24 hours; pass clear_cache=True to force a refresh.
        """
        if not clear_cache and self._list_cache is not None:
            ts, data = self._list_cache
            if datetime.now() - ts < self.LIST_CACHE_DURATION:
                return data

        headers = {**self.HEADERS, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                resp = await client.get(self.LIST_URL, headers=headers)
        except httpx.RequestError as e:
            raise ConnectionError(f"Error reaching CAFCI fondo list: {str(e)}")

        if resp.status_code >= 400:
            raise ValueError(f"CAFCI fondo list returned status {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError:
            raise ValueError("CAFCI fondo list returned a non-JSON response")

        if not payload.get("success"):
            raise ValueError("CAFCI fondo list reported failure")

        data = payload.get("data") or []
        self._list_cache = (datetime.now(), data)
        return data

    @staticmethod
    def _parse_keywords(raw: Optional[str]) -> List[str]:
        """Split a comma-separated keyword list, trim, drop empties."""
        if not raw:
            return []
        return [kw.strip() for kw in raw.split(",") if kw.strip()]

    @staticmethod
    def _name_matches(name: Optional[str], keywords: List[str]) -> bool:
        """All keywords must appear in `name` (case-insensitive)."""
        if not keywords:
            return True
        if not name:
            return False
        haystack = name.lower()
        return all(kw.lower() in haystack for kw in keywords)

    @staticmethod
    def _opt_str(value: Any) -> Optional[str]:
        """Return None for None values; everything else becomes str()."""
        if value is None:
            return None
        return str(value)

    @classmethod
    def _project_clase_fondo(cls, cf: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": cls._opt_str(cf.get("id")) or "",
            "nombre": cf.get("nombre"),
            "monedaId": cls._opt_str(cf.get("monedaId")),
            "fondoId": cls._opt_str(cf.get("fondoId")),
        }

    @classmethod
    def _project_fondo(cls, fondo: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "codigoCNV": cls._opt_str(fondo.get("codigoCNV")) or "",
            "nombre": fondo.get("nombre"),
            "clase_fondos": [
                cls._project_clase_fondo(cf)
                for cf in (fondo.get("clase_fondos") or [])
            ],
        }

    async def search(
        self,
        codigo_cnv: Optional[str] = None,
        nombre: Optional[str] = None,
        clear_cache: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search the CAFCI catalog by `codigoCNV` and/or `nombre`.

        At least one of `codigo_cnv` or `nombre` must be provided.

        Args:
            codigo_cnv: optional exact CNV code.
            nombre: optional comma-separated keyword list. Every keyword must
                appear in the fund's `nombre` (case-insensitive).
            clear_cache: if True, refresh the catalog cache (24h) and this
                search's result cache before searching.

        Returns:
            List of dicts, each with `codigoCNV`, `nombre` and a `clase_fondos`
            list (each clase has `id`, `nombre`, `monedaId`, `fondoId`).
        """
        code = (codigo_cnv or "").strip()
        keywords = self._parse_keywords(nombre)

        if not code and not keywords:
            raise InvalidFilterError(
                "at least one of codigoCNV or nombre must be provided"
            )

        norm_keywords = ",".join(sorted(kw.lower() for kw in keywords))
        cache_key = f"fci_search_{code}|{norm_keywords}"

        if not clear_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        catalog = await self.list_all(clear_cache=clear_cache)

        matches: List[Dict[str, Any]] = []
        for entity in catalog:
            if code:
                entity_code = entity.get("codigoCNV")
                if entity_code is None or str(entity_code).strip() != code:
                    continue
            if keywords and not self._name_matches(entity.get("nombre"), keywords):
                continue

            matches.append(self._project_fondo(entity))

        self._set_cache(cache_key, matches)
        return matches

    async def search_clase_fondos(
        self,
        id: Optional[str] = None,
        nombre: Optional[str] = None,
        fondo_id: Optional[str] = None,
        clear_cache: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search clase_fondos across the entire CAFCI catalog.

        At least one of `id`, `nombre`, or `fondo_id` must be provided.

        Args:
            id: optional exact clase_fondo id.
            nombre: optional comma-separated keyword list. Every keyword must
                appear in the clase_fondo's `nombre` (case-insensitive).
            fondo_id: optional parent fondo id (matches `clase_fondo.fondoId`).
            clear_cache: if True, refresh the catalog cache (24h) and this
                search's result cache before searching.

        Returns:
            List of dicts with `id`, `nombre`, `monedaId`, `fondoId`.
        """
        cf_id = (id or "").strip()
        keywords = self._parse_keywords(nombre)
        parent_id = (fondo_id or "").strip()

        if not cf_id and not keywords and not parent_id:
            raise InvalidFilterError(
                "at least one of id, nombre, or fondoId must be provided"
            )

        norm_keywords = ",".join(sorted(kw.lower() for kw in keywords))
        cache_key = f"cf_search_{cf_id}|{parent_id}|{norm_keywords}"

        if not clear_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        catalog = await self.list_all(clear_cache=clear_cache)

        matches: List[Dict[str, Any]] = []
        for fondo in catalog:
            for cf in (fondo.get("clase_fondos") or []):
                if cf_id and str(cf.get("id", "")).strip() != cf_id:
                    continue
                if parent_id and str(cf.get("fondoId", "")).strip() != parent_id:
                    continue
                if keywords and not self._name_matches(cf.get("nombre"), keywords):
                    continue
                matches.append(self._project_clase_fondo(cf))

        self._set_cache(cache_key, matches)
        return matches


_fci_service_instance = None


def get_fci_service() -> FCIService:
    """Get singleton FCI service instance"""
    global _fci_service_instance
    if _fci_service_instance is None:
        _fci_service_instance = FCIService()
    return _fci_service_instance
