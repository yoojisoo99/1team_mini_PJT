from pykrx import stock
import pandas as pd

# 데이터 가져오기
df = stock.get_market_net_purchases_of_equities(
    "20240101",
    "20240201",
    "KOSPI",
    "외국인"
)

# index → column
df = df.reset_index()

# 종목명 추가
df["종목명"] = df["티커"].apply(stock.get_market_ticker_name)

# 외국인 순매수 정렬
df = df.sort_values("순매수거래대금", ascending=False)

# 컬럼 선택
df = df[[
    "티커",
    "종목명",
    "순매수거래량",
    "순매수거래대금"
]]

# 출력
print(df.head(20))
