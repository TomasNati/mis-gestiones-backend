import yfinance as yf

def get_current_price_value(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # fast_info.last_price returns a float
        price = ticker.fast_info.last_price
        
        if price is None or price <= 0:
            return None
            
        return float(price)
    except Exception:
        return None

