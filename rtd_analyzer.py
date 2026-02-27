import pandas as pd
import logging
from config import DATA_DIR
import os
import sqlite3

logger = logging.getLogger(__name__)

def load_realtime_market_data():
    """`data/` 폴더 내의 스케줄러가 저장한 JSON에서 실시간 시장 데이터를 로드하여 DataFrame으로 반환합니다."""
    import glob
    import json
    
    # scheduler_market_data_*.json 파일들 로드
    file_pattern = os.path.join(DATA_DIR, 'scheduler_market_data_*.json')
    files = sorted(glob.glob(file_pattern))
    
    all_data = []
    for fpath in files[-10:]: # 최근 10개 파일 정도만 읽기 (당일 데이터 위주)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "stock_market_data" in data:
                    all_data.extend(data["stock_market_data"])
        except Exception as e:
            logger.warning(f"[RTD] 파일 로드 실패 {fpath}: {e}")
            
    if all_data:
        df = pd.DataFrame(all_data)
        df['수집시간'] = pd.to_datetime(df['수집시간'])
        today = pd.Timestamp.now().date()
        df = df[df['수집시간'].dt.date == today]
        logger.info(f"[RTD] JSON에서 오늘 날짜 시세 {len(df)}건 로드 완료")
        return df
        
    return pd.DataFrame()


def analyze_volume_surge(df):
    """
    종목별로 직전 시간 대비 현재 시간의 거래량 급증(Momentum) 순위를 계산합니다.
    Returns: TOP 10 급증 종목 DataFrame
    """
    if df.empty or '수집시간' not in df.columns:
        return pd.DataFrame()
        
    # 시간 순 정렬
    df = df.sort_values(by=['종목코드', '수집시간'])
    
    # 각 종목별 가장 최근 데이터와 그 직전 데이터 추출
    latest_times = sorted(df['수집시간'].unique())
    if len(latest_times) < 2:
        logger.warning("[RTD] 거래량 급증을 비교할 수집 시간대(2개 이상)가 부족합니다.")
        return pd.DataFrame()
        
    t_now = latest_times[-1]
    t_prev = latest_times[-2]
    
    df_now = df[df['수집시간'] == t_now].set_index('종목코드')
    df_prev = df[df['수집시간'] == t_prev].set_index('종목코드')
    
    # 교집합 종목만
    common_idx = df_now.index.intersection(df_prev.index)
    df_now = df_now.loc[common_idx]
    df_prev = df_prev.loc[common_idx]
    
    # 거래량 변화량(Delta) 계산
    surge_df = df_now[['종목명', '시장', '현재가', '등락률_num']].copy()
    surge_df['현재_거래량'] = df_now['거래량']
    surge_df['이전_거래량'] = df_prev['거래량']
    
    # 0으로 나누기 방지
    surge_df['이전_거래량'] = surge_df['이전_거래량'].replace(0, 1)
    
    # 몇 배 급증했는지 비율 (예: 1시간만에 20% 증가 = 1.2)
    # 거래량은 보통 1시간 사이에 누적이므로, (현재 누적거래량 - 이전 누적거래량) 이 순수 해당 시간 거래량임.
    # 하지만 네이버 금융 수집 특성상 하루 누적치일 확률이 크므로 delta 값을 구함
    surge_df['시간당_순거래량'] = surge_df['현재_거래량'] - surge_df['이전_거래량']
    
    # 시간당 순거래량이 0보다 큰 종목 중 가장 많은 거래가 터진 TOP 10
    top10 = surge_df[surge_df['시간당_순거래량'] > 0].sort_values(by='시간당_순거래량', ascending=False).head(10)
    
    return top10.reset_index()
