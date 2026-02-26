import pandas as pd
from common import get_engine, dataframe_to_json_file
import time

ENGINE_URL = "mysql+pymysql://test:test@25.4.53.12:3306/stock_db?charset=utf8mb4"
OUTPUT_PATH = "out_data/stocks_export.json"
ROOT_KEY = "stocks"

def main():
    engine = get_engine(ENGINE_URL)
    try:
        # 1. 최신 시세와 종목 정보를 조인하여 가져오는 쿼리
        query = """
        SELECT 
            s.ticker AS 종목코드,
            s.name AS 종목명,
            s.market AS 시장,
            p.price AS 현재가,
            p.volume AS 거래량,
            p.trade_value AS 거래대금
        FROM stocks s
        LEFT JOIN (
            SELECT p1.ticker, p1.price, p1.volume, p1.trade_value
            FROM price_snapshots p1
            INNER JOIN (
                SELECT ticker, MAX(captured_at) as max_at
                FROM price_snapshots
                GROUP BY ticker
            ) p2 ON p1.ticker = p2.ticker AND p1.captured_at = p2.max_at
        ) p ON s.ticker = p.ticker
        """
        
        df = pd.read_sql(query, con=engine)
        
        # 2. 데이터가 없는 경우를 대비해 기본값 처리 및 앱에서 요구하는 컬럼 추가
        df['현재가'] = df['현재가'].fillna(0).astype(int)
        df['거래량'] = df['거래량'].fillna(0).astype(int)
        df['거래대금'] = df['거래대금'].fillna(0).astype(int)
        df['등락률'] = '0.00%'  # 앱 크래시 방지용 더미 데이터
        
        dataframe_to_json_file(df, root_key=ROOT_KEY, output_path=OUTPUT_PATH)
        print(f"[Success] stocks export completed (Joined with price): {OUTPUT_PATH} (rows={len(df)})")
        return len(df)
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()