# 공통 모듈 (엔지/저장 함수)

import json
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine

# SQLAlchemy 엔진 생성
def get_engine(engine_url: str):
    return create_engine(engine_url) 

# pandas DataFrame을 JSON 구조로 변환
def dataframe_to_json_file(df: pd.DataFrame, root_key: str, output_path: str):
    # NaN -> None 치환 (JSON 직렬화 안정화)
    df = df.where(pd.notnull(df), None)
    # Timestamp / datetime 컬럼 JSON 직렬화 가능하게 문자열로 변환
    dt_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns
    for c in dt_cols:
        df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S")

    payload = {root_key: df.to_dict(orient="records")}

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

# db 연결, select 쿼리 실행, DataFrame으로 변환, JSON 파일로 저장
def export_table_to_json(engine_url: str, table_name: str, root_key: str, output_path: str,
                         columns: list[str] | None = None,
                         where: str | None = None):
    engine = get_engine(engine_url)
    try:
        cols = "*" if not columns else ", ".join([f"`{c}`" for c in columns])
        sql = f"SELECT {cols} FROM `{table_name}`"
        if where:
            sql += f" WHERE {where}"

        df = pd.read_sql(sql, con=engine)
        dataframe_to_json_file(df, root_key=root_key, output_path=output_path)

        return len(df)
    finally:
        engine.dispose()