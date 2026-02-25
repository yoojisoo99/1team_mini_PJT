import pandas as pd
import json
import os
import glob
import pymysql
from sqlalchemy import create_engine

pymysql.install_as_MySQLdb()

json_files = glob.glob(os.path.join('data', 'price_snapshots_*.json'))
if not json_files:
    print("데이터를 찾을 수 없습니다: price_snapshots_*.json")
    exit()

latest_file = max(json_files, key=os.path.getctime)
with open(latest_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

if isinstance(data, dict):
    key = list(data.keys())[0] # "price_snapshots"
    table_df = pd.DataFrame(data[key])
else:
    table_df = pd.DataFrame(data)

engine = create_engine('mysql+pymysql://test:test@25.4.53.12:3306/stock_db?charset=utf8mb4')
try:
    with engine.begin() as conn:
        table_df.to_sql(name='price_snapshots', con=conn, if_exists='append', index=False)
    print("D_price_snapshots_table 누적 데이터 동기화 완료")
finally:
    engine.dispose()