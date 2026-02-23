from pykrx import stock

df = stock.get_market_ohlcv("20240101", "20240131", "005930")
print(df.head())