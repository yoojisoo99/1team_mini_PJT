import pandas as pd
import json
import os
import pymysql
import sqlalchemy

pymysql.install_as_MySQLdb()
from sqlalchemy import create_engine

# JSON 파일 경로 설정 (data/users_db.json)
current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, '..', 'data', 'users_db.json')

table_df = pd.DataFrame()
if os.path.exists(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, dict) and "users" in data:
            table_df = pd.DataFrame(data["users"])
        elif isinstance(data, list):
            table_df = pd.DataFrame(data)

if table_df.empty:
    print("저장된 유저 데이터(JSON)가 없거나 형식이 올바르지 않습니다.")
else:
    engine = None
    conn = None
    try:
        engine = create_engine('mysql+pymysql://python:kk@49.167.28.157:3307/python_db?charset=utf8mb4')
        conn = engine.connect()    

        table_df.to_sql(name='users_table', con=engine, if_exists='replace', index=True,\
                        index_label='A_id',
                        dtype={
                            'user_id': sqlalchemy.types.VARCHAR(200),
                            'user_password': sqlalchemy.types.VARCHAR(200),
                            'user_email': sqlalchemy.types.VARCHAR(200),
                        })
        print('유저 테이블 생성 완료')
    finally:
        if conn is not None: 
            conn.close()
        if engine is not None:
            engine.dispose()