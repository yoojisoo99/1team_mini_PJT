import os
import sys
import traceback

# app.py의 load_latest_data/ensure_data_exists를 그대로 재사용하고 싶으면 import해도 되지만,
# mailer는 "배치" 성격이므로 여기서는 data 로딩을 간단하게 처리하는 걸 추천해요.
import glob
import pandas as pd
import json

from mailer.env_loader import Settings
from mailer.db import get_engine, fetch_subscribed_users
from mailer.newsletter import build_newsletter_for_user
from mailer.smtp_client import send_email

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

def load_latest_files():
    stock_files = sorted(glob.glob(os.path.join(DATA_DIR, "stock_data_*.csv")))
    news_files = sorted(glob.glob(os.path.join(DATA_DIR, "stock_news_*.csv")))
    signal_files = sorted(glob.glob(os.path.join(DATA_DIR, "analysis_signals_*.json")))

    stock_df = pd.read_csv(stock_files[-1]) if stock_files else pd.DataFrame()
    news_df = pd.read_csv(news_files[-1]) if news_files else pd.DataFrame()

    signals_df = pd.DataFrame()
    if signal_files:
        with open(signal_files[-1], "r", encoding="utf-8") as f:
            data = json.load(f)
        signals_df = pd.DataFrame(data["analysis_signals"] if isinstance(data, dict) and "analysis_signals" in data else data)

    return stock_df, news_df, signals_df

def main():
    s = Settings()
    if not s.db_url:
        raise RuntimeError("DB_URL이 비어있습니다. .env 확인 필요")
    if not s.smtp_user:
        raise RuntimeError("SMTP_USER가 비어있습니다. .env 확인 필요")
    if not s.dry_run and not s.smtp_app_password:
        raise RuntimeError("DRY_RUN=0인데 SMTP_APP_PASSWORD가 비어있습니다.")

    stock_df, news_df, signals_df = load_latest_files()
    if stock_df.empty:
        raise RuntimeError("stock_df가 비어있습니다. data/stock_data_*.csv 생성 필요")

    engine = get_engine(s.db_url)
    users_df = fetch_subscribed_users(engine)

    if users_df.empty:
        print("user_check=1 대상자가 없습니다.")
        return

    sent = 0
    for _, row in users_df.iterrows():
        user_id = row["user_id"]
        email = row["user_email"]
        investor_type = row["type_name"]  # '안정형'...'공격투자형'

        try:
            newsletter = build_newsletter_for_user(
                stock_df=stock_df,
                news_df=news_df,
                signals_df=signals_df,
                investor_type=investor_type,
                user_id=user_id,
            )

            send_email(
                host=s.smtp_host,
                port=s.smtp_port,
                user=s.smtp_user,
                app_password=s.smtp_app_password,
                from_name=s.from_name,
                to_email=email,
                subject=newsletter["title"],
                body=newsletter["content"],
                dry_run=s.dry_run,
            )
            sent += 1
        except Exception as e:
            print(f"[FAIL] user_id={user_id} email={email} type={investor_type} err={e}")
            traceback.print_exc()

    print(f"완료: {sent}/{len(users_df)} 발송 처리 (DRY_RUN={s.dry_run})")

if __name__ == "__main__":
    main()