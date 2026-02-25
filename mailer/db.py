import os
import json
import glob
import pandas as pd
from typing import Dict, Any, List, Tuple

TYPE_ID_TO_NAME = {1:"안정형", 2:"안정추구형", 3:"위험중립형", 4:"적극투자형", 5:"공격투자형"}

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def load_users(users_path: str) -> Dict[str, Dict[str, Any]]:
    """users_db.json -> {user_id: {user_email, user_password}} 형태로 반환"""
    data = load_json(users_path, {})
    # {"users":[...]} 형태도 처리
    if isinstance(data, dict) and "users" in data:
        out = {}
        for u in data["users"]:
            uid = u.get("user_id")
            if uid:
                out[uid] = {
                    "user_email": u.get("user_email", ""),
                    "user_password": u.get("user_password", ""),
                }
        return out
    return data if isinstance(data, dict) else {}

def load_agreed_user_types(user_type_path: str) -> List[Tuple[str, int]]:
    """
    user_type_db.json에서 newsletter_agree==true 인 사용자만
    [(user_id, type_id), ...] 반환
    """
    data = load_json(user_type_path, {"user_type": []})
    rows = data.get("user_type", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    agreed = []
    for r in rows:
        uid = r.get("user_id")
        type_id = r.get("type_id")
        agree = r.get("newsletter_agree", False)
        if uid and isinstance(type_id, int) and agree is True:
            agreed.append((uid, type_id))
    return agreed

def latest_csv(data_dir: str, pattern: str) -> str:
    files = sorted(glob.glob(os.path.join(data_dir, pattern)))
    return files[-1] if files else ""

def load_latest_dataframes(data_dir: str):
    """
    최신 stock/news CSV 로드
    signals는 없으면 app에서 생성 가능하니 여기선 생략(단순화)
    """
    stock_path = latest_csv(data_dir, "stock_data_*.csv")
    news_path = latest_csv(data_dir, "stock_news_*.csv")

    stock_df = pd.read_csv(stock_path) if stock_path else pd.DataFrame()
    news_df = pd.read_csv(news_path) if news_path else pd.DataFrame()
    return stock_df, news_df

def type_name_from_id(type_id: int) -> str:
    return TYPE_ID_TO_NAME.get(type_id, "위험중립형")