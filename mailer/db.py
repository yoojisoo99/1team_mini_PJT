import pandas as pd
from sqlalchemy import create_engine, text

def get_engine(db_url: str):
    return create_engine(db_url, pool_pre_ping=True)

def fetch_subscribed_users(engine) -> pd.DataFrame:
    """
    user_check=1 인 사용자 + 성향(type_name) + 이메일 조회
    """
    q = text("""
        SELECT
            u.user_id,
            u.user_email,
            ut.type_name,
            ut.type_id
        FROM users u
        JOIN user_type ut ON u.user_id = ut.user_id
        WHERE ut.user_check = 1
          AND u.user_email IS NOT NULL
          AND u.user_email <> ''
    """)
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    return df