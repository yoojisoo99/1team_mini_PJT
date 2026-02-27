"""
📈 KOSPI / KOSDAQ 일별 지수 스크래핑
====================================
네이버 금융 일별 시세 페이지에서 지수 데이터를 수집합니다.
  - requests + BeautifulSoup 사용
  - data/market_index_YYYYMMDD.csv 로 저장
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import time
import logging

# ============================================================
# 로깅 설정
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# 공통 설정
# ============================================================
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36'
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)


def create_session(retries=3, backoff=0.5):
    """재시도 로직이 포함된 requests.Session을 생성합니다."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def scrape_index_daily(code="KOSPI", pages=10, session=None):
    """
    네이버 금융 일별 시세 페이지에서 지수 데이터를 스크래핑합니다.

    Args:
        code: "KOSPI" 또는 "KOSDAQ"
        pages: 수집할 페이지 수 (1페이지 ≈ 10일, 10페이지 ≈ 100일)
        session: requests.Session (없으면 새로 생성)
    Returns:
        pandas DataFrame (Date, Close, 전일비, 등락률, 거래량, 거래대금, 시장)
    """
    if session is None:
        session = create_session()

    base_url = f"https://finance.naver.com/sise/sise_index_day.naver?code={code}"
    all_rows = []

    logger.info(f"[지수 수집] {code} 일별 시세 수집 시작 ({pages}페이지)")

    for page in range(1, pages + 1):
        url = f"{base_url}&page={page}"
        try:
            resp = session.get(url, timeout=10)
            resp.encoding = 'euc-kr'
            soup = BeautifulSoup(resp.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"  [네트워크 오류] {code} page={page}: {e}")
            break

        # 테이블의 tr 태그에서 데이터 행 추출
        table = soup.select_one('table.type_1')
        if not table:
            logger.warning(f"  [파싱 실패] {code} page={page}: 테이블 없음")
            break

        rows = table.select('tr')
        for row in rows:
            cols = row.select('td')
            if len(cols) < 6:
                continue

            date_text = cols[0].text.strip()
            close_text = cols[1].text.strip()

            # 빈 행 건너뛰기
            if not date_text or not close_text:
                continue

            try:
                # 날짜 파싱 (YYYY.MM.DD → YYYY-MM-DD)
                date_str = date_text.replace('.', '-').strip()
                # 숫자 파싱 (콤마 제거)
                close_val = float(close_text.replace(',', ''))
                change_text = cols[2].text.strip().replace(',', '')
                change_pct = cols[3].text.strip().replace('%', '').strip()
                volume_text = cols[4].text.strip().replace(',', '')
                trade_val_text = cols[5].text.strip().replace(',', '')

                # 전일비의 부호 결정: 등락률로 판별
                change_val = float(change_text) if change_text else 0.0
                pct_val = float(change_pct) if change_pct else 0.0
                if pct_val < 0:
                    change_val = -abs(change_val)

                all_rows.append({
                    'Date': date_str,
                    'Close': close_val,
                    '전일비': change_val,
                    '등락률': pct_val,
                    '거래량': int(volume_text) if volume_text else 0,
                    '거래대금': int(trade_val_text) if trade_val_text else 0,
                    '시장': code,
                })
            except (ValueError, TypeError) as e:
                continue

        time.sleep(0.3)  # 서버 부하 방지

    df = pd.DataFrame(all_rows)

    if not df.empty:
        # 날짜 기준 오름차순 정렬 + 중복 제거
        df = df.drop_duplicates(subset='Date')
        df = df.sort_values('Date').reset_index(drop=True)
        logger.info(f"  -> {code} {len(df)}일치 데이터 수집 완료")
    else:
        logger.warning(f"  -> {code} 데이터 수집 실패 (0건)")

    return df


def scrape_all_indices(pages=10):
    """
    KOSPI + KOSDAQ 지수를 모두 수집하여 하나의 DataFrame으로 반환합니다.

    Args:
        pages: 수집할 페이지 수 (1페이지 ≈ 10일)
    Returns:
        pandas DataFrame
    """
    session = create_session()

    df_kospi = scrape_index_daily("KOSPI", pages=pages, session=session)
    df_kosdaq = scrape_index_daily("KOSDAQ", pages=pages, session=session)

    result = pd.concat([df_kospi, df_kosdaq], ignore_index=True)
    return result


def save_index_data(df, directory=None):
    """지수 데이터를 CSV로 저장합니다."""
    if directory is None:
        directory = DATA_DIR
    os.makedirs(directory, exist_ok=True)

    today = datetime.now().strftime('%Y%m%d')
    filename = f"market_index_{today}.csv"
    filepath = os.path.join(directory, filename)

    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    logger.info(f"  -> 저장 완료: {filepath} ({len(df)}건)")
    return filepath


def load_index_data(directory=None):
    """
    data/ 폴더에서 가장 최근의 market_index_*.csv 를 로드합니다.
    파일이 없으면 빈 DataFrame을 반환합니다.
    """
    if directory is None:
        directory = DATA_DIR

    if not os.path.exists(directory):
        return pd.DataFrame()

    # market_index_*.csv 파일 목록 탐색
    files = sorted([
        f for f in os.listdir(directory)
        if f.startswith('market_index_') and f.endswith('.csv')
    ], reverse=True)

    if not files:
        return pd.DataFrame()

    filepath = os.path.join(directory, files[0])
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        logger.info(f"  -> 로드 완료: {filepath} ({len(df)}건)")
        return df
    except Exception as e:
        logger.error(f"  -> 로드 실패: {filepath}: {e}")
        return pd.DataFrame()


# ============================================================
# CLI 실행
# ============================================================
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("KOSPI / KOSDAQ 지수 스크래핑 시작")
    logger.info("=" * 50)

    df = scrape_all_indices(pages=10)

    if not df.empty:
        save_index_data(df)
        print(f"\n[완료] 수집 완료! 총 {len(df)}건")
        print(df.head(10))
    else:
        print("[실패] 데이터 수집에 실패했습니다.")
