"""
DB 매니저 (코드 초안)
====================
MySQL 연동을 위한 SQLAlchemy 기반 DB 관리 모듈입니다.
현재는 코드 초안만 구현되어 있으며, 실제 DB 없이 CSV 모드로 동작합니다.

스키마 대응:
  (C) stocks          → save_stocks()
  (D) price_snapshots → save_price_snapshots()
  (E) analysis_signals→ save_analysis_signals()
  (F) recommendations → save_recommendations()
  (G) newsletters     → save_newsletters()
"""
import os
import logging
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME, DATA_DIR

logger = logging.getLogger(__name__)

# SQLAlchemy 엔진 (설치 여부에 따라 동작)
_engine = None


def get_engine():
    """SQLAlchemy 엔진을 생성하거나 캐시된 엔진을 반환합니다."""
    global _engine
    if _engine is not None:
        return _engine

    try:
        from sqlalchemy import create_engine, text
        connection_string = (
            f"mysql+pymysql://{DB_USER}:{DB_PASS}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            f"?charset=utf8mb4"
        )
        _engine = create_engine(connection_string, echo=False)
        # 연결 테스트
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[DB] MySQL 연결 성공")
        return _engine
    except ImportError:
        logger.warning("[DB] sqlalchemy/pymysql 미설치. CSV 모드로 동작합니다.")
        return None
    except Exception as e:
        logger.warning(f"[DB] MySQL 연결 실패: {e}. CSV 모드로 동작합니다.")
        return None


# ============================================================
# 범용 저장/조회
# ============================================================
def save_to_db(df, table_name, if_exists='replace'):
    """DataFrame을 MySQL 테이블에 저장합니다."""
    engine = get_engine()
    if engine is None:
        logger.info(f"[DB] DB 미연결. '{table_name}' CSV로 저장 대체.")
        save_to_csv(df, f"{table_name}_fallback.csv")
        return False

    try:
        df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        logger.info(f"[DB] '{table_name}' 테이블에 {len(df)}건 저장 완료")
        return True
    except Exception as e:
        logger.error(f"[DB] '{table_name}' 저장 실패: {e}")
        logger.info(f"  -> CSV 백업 저장 진행.")
        save_to_csv(df, f"{table_name}_error_backup.csv")
        return False


def load_from_db(query):
    """SQL 쿼리를 실행하고 결과를 DataFrame으로 반환합니다."""
    engine = get_engine()
    if engine is None:
        logger.info("[DB] DB 미연결. 쿼리 실행 불가.")
        return None

    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        logger.error(f"[DB] 쿼리 실행 실패: {e}")
        return None


def save_json(data_list, filename, directory=None):
    """데이터 리스트를 JSON 파일로 저장합니다."""
    import json
    if directory is None:
        directory = str(DATA_DIR)
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        logger.info(f"  -> JSON 저장 완료: {filepath} ({len(data_list.get(list(data_list.keys())[0], [])) if isinstance(data_list, dict) else len(data_list)}건)")
        return filepath
    except Exception as e:
        logger.error(f"[JSON] 저장 실패 ({filename}): {e}")
        return None

def sync_json_to_db(filepath, table_name, if_exists='append'):
    """JSON 파일을 읽어 DataFrame으로 파싱 후 DB에 반영합니다."""
    import json
    engine = get_engine()
    if engine is None:
        logger.info(f"[DB] DB 미연결. '{table_name}' 동기화 생략 (JSON 보관됨).")
        return False

    if not os.path.exists(filepath):
        logger.warning(f"[DB Sync] 파일 없음: {filepath}")
        return False
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 최상위 키가 있는 구조인 경우 (예: {"stocks": [...]}) 리스트 추출
        data_list = []
        if isinstance(data, dict):
            # dict의 첫 번째 value(리스트)를 사용, 아니면 data 자체를 하나의 리스트로 감쌈
            for k, v in data.items():
                if isinstance(v, list):
                    data_list = v
                    break
            if not data_list:
                data_list = [data]
        elif isinstance(data, list):
            data_list = data
            
        if not data_list:
            logger.info(f"[DB Sync] 동기화할 데이터가 없습니다: {table_name}")
            return True
            
        df = pd.DataFrame(data_list)
        df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        logger.info(f"[DB Sync] '{table_name}' 테이블에 {len(df)}건 동기화 완료")
        return True
    except Exception as e:
        logger.error(f"[DB Sync] '{table_name}' 동기화 실패: {e}")
        return False

def save_to_csv(df, filename, directory=None, encoding='utf-8-sig'):
    """DataFrame을 CSV 파일로 저장합니다. (하위 호환 및 DB 미연결 시 대안)"""
    if directory is None:
        directory = str(DATA_DIR)
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    df.to_csv(filepath, index=False, encoding=encoding)
    logger.info(f"  -> CSV 저장: {filepath} ({len(df)}건)")
    return filepath


# ============================================================
# (C) stocks — 종목 마스터
#     ticker(PK), name, market
# ============================================================
def save_stocks(df):
    """
    종목 마스터 정보를 JSON으로 변환 후 테이블에 동기화합니다.

    Args:
        df: 스크래핑된 전체 DataFrame (종목코드, 종목명, 시장 포함)
    """
    if df.empty:
        return
    master = df[['종목코드', '종목명', '시장']].drop_duplicates(subset='종목코드')
    master_db = master.rename(columns={
        '종목코드': 'ticker',
        '종목명': 'name',
        '시장': 'market',
    })

    # 1. JSON 변환 및 저장
    data_records = master_db.to_dict(orient='records')
    json_data = {"stocks": data_records}
    today = datetime.now().strftime('%Y%m%d')
    json_filepath = save_json(json_data, f'stocks_{today}.json')
    
    # 2. JSON 기반으로 DB 동기화
    if json_filepath:
        sync_json_to_db(json_filepath, 'stocks', if_exists='replace')

    # 하위 호환용 CSV 유지
    save_to_csv(master_db, f'stocks_{today}.csv')

    return master_db


# ============================================================
# (D) price_snapshots — 시세 스냅샷
#     ticker(FK), captured_at, price, volume, trade_value
# ============================================================
def save_price_snapshots(df):
    """
    시세 스냅샷을 JSON으로 변환 후 저장 및 테이블 동기화합니다.

    Args:
        df: 스크래핑된 전체 DataFrame (종목코드, 수집시간, 현재가, 거래량, 거래대금 포함)
    """
    if df.empty:
        return

    required = ['종목코드', '수집시간', '현재가', '거래량', '거래대금']
    available = [c for c in required if c in df.columns]
    if len(available) < len(required):
        logger.warning(f"[DB] price_snapshots 필수 컬럼 부족: {set(required) - set(available)}")
        return

    snap = df[required].copy()
    
    # id 필드 추가 요구사항에 맞춰 종목명을 id로 처리 (종목명이 df에 있다면)
    if '종목명' in df.columns:
        snap_db = df[['종목명'] + required].copy()
        snap_db = snap_db.rename(columns={'종목명': 'id'})
    else:
        snap_db = snap.copy()
        snap_db['id'] = snap_db['종목코드']
        
    snap_db = snap_db.rename(columns={
        '종목코드': 'ticker',
        '수집시간': 'captured_at',
        '현재가': 'price',
        '거래량': 'volume',
        '거래대금': 'trade_value',
    })

    # JSON 호환을 위해 datetime 문자열 변환
    if pd.api.types.is_datetime64_any_dtype(snap_db['captured_at']):
        snap_db['captured_at'] = snap_db['captured_at'].dt.strftime('%Y-%m-%dT%H:%M:%S')
        
    # Python int/float 변환 (Numpy 타입 이슈 방지)
    snap_db['price'] = snap_db['price'].apply(lambda x: int(x) if pd.notnull(x) else 0)
    snap_db['volume'] = snap_db['volume'].apply(lambda x: int(x) if pd.notnull(x) else 0)
    snap_db['trade_value'] = snap_db['trade_value'].apply(lambda x: int(x) if pd.notnull(x) else 0)

    # 1. JSON 변환 및 저장
    data_records = snap_db.to_dict(orient='records')
    json_data = {"price_snapshots": data_records}
    today = datetime.now().strftime('%Y%m%d')
    
    # 스케줄러를 위해 분 단위까지 파일명 기록 고려(중복 방지, 여기서는 YYYYMMDD_HHMM으로 확장 추천)
    time_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_filepath = save_json(json_data, f'price_snapshots_{time_suffix}.json')

    # 2. JSON 기반 DB 동기화
    if json_filepath:
        sync_json_to_db(json_filepath, 'price_snapshots', if_exists='append')

    # 하위 호환
    save_to_csv(snap_db, f'price_snapshots_{time_suffix}.csv')

    return snap_db


# ============================================================
# (E) analysis_signals — 분석 결과
#     ticker(FK), as_of, window, trend_score, signal
# ============================================================
def save_analysis_signals(signals_df):
    """
    분석 신호를 JSON으로 변환 후 데이터베이스와 동기화합니다.

    Args:
        signals_df: analyzer.generate_analysis_signals() 결과 DataFrame
                    컬럼: ticker, as_of, window, trend_score, signal
    """
    if signals_df is None or signals_df.empty:
        return

    sign_db = signals_df.copy()
    
    # 'id' 컬럼 요구 반영 (종목명이 있다면 사용)
    if '종목명' in sign_db.columns:
        sign_db.rename(columns={'종목명': 'id'}, inplace=True)
    elif 'name' in sign_db.columns:
        sign_db.rename(columns={'name': 'id'}, inplace=True)
    else:
        sign_db['id'] = sign_db['ticker']

    if pd.api.types.is_datetime64_any_dtype(sign_db['as_of']):
        sign_db['as_of'] = sign_db['as_of'].dt.strftime('%Y-%m-%dT%H:%M:%S')
        
    # 1. JSON 변환 및 저장
    data_records = sign_db.to_dict(orient='records')
    json_data = {"analysis_signals": data_records}
    today = datetime.now().strftime('%Y%m%d')
    json_filepath = save_json(json_data, f'analysis_signals_{today}.json')

    # 2. JSON 기반 DB 동기화
    if json_filepath:
        sync_json_to_db(json_filepath, 'analysis_signals', if_exists='append')

    save_to_csv(sign_db, f'analysis_signals_{today}.csv')

    return sign_db


# ============================================================
# (F) recommendations — 사용자별 추천 결과
#     user_id(FK), ticker(FK), as_of, score, reason
# ============================================================
def save_recommendations(recs_df):
    """
    추천 결과를 JSON으로 변환 후 데이터베이스에 동기화합니다.

    Args:
        recs_df: analyzer.build_recommendations_df() 결과 DataFrame
                 컬럼: user_id, ticker, as_of, score, reason
    """
    if recs_df is None or recs_df.empty:
        return

    recs_db = recs_df.copy()
    if pd.api.types.is_datetime64_any_dtype(recs_db['as_of']):
        recs_db['as_of'] = recs_db['as_of'].dt.strftime('%Y-%m-%d')
        
    # id (PK) 컬럼 요구사항 대응 (없으면 1부터 순번 부여)
    if 'id' not in recs_db.columns:
        recs_db.insert(0, 'id', range(1, len(recs_db) + 1))

    # 1. JSON 저장
    data_records = recs_db.to_dict(orient='records')
    json_data = {"recommendations": data_records}
    today = datetime.now().strftime('%Y%m%d')
    json_filepath = save_json(json_data, f'recommendations_{today}.json')

    # 2. 동기화
    if json_filepath:
        # DB 컬럼 맞춰서 'id' 컬럼은 제외 (Auto Increment 의존)
        sync_json_to_db(json_filepath, 'recommendations', if_exists='append')

    save_to_csv(recs_db, f'recommendations_{today}.csv')

    return recs_db


# ============================================================
# (G) newsletters — 뉴스레터
#     user_id(FK), created_at, title, content
# ============================================================
def save_newsletter(newsletter_dict):
    """
    뉴스레터를 JSON으로 변환 후 데이터베이스와 동기화합니다.

    Args:
        newsletter_dict: analyzer.generate_newsletter() 결과 dict
                         키: user_id, created_at, title, content
    """
    if not newsletter_dict:
        return

    news_df = pd.DataFrame([newsletter_dict])
    
    # ID 필드 부여
    if 'id' not in news_df.columns:
        news_df.insert(0, 'id', [101]) # 기본 샘플 ID
        
    if pd.api.types.is_datetime64_any_dtype(news_df['created_at']):
        news_df['created_at'] = news_df['created_at'].dt.strftime('%Y-%m-%dT%H:%M:%S')

    # 1. JSON 저장
    data_records = news_df.to_dict(orient='records')
    json_data = {"newsletters": data_records}
    today = datetime.now().strftime('%Y%m%d')
    json_filepath = save_json(json_data, f'newsletters_{today}.json')

    # 2. 동기화
    if json_filepath:
        sync_json_to_db(json_filepath, 'newsletters', if_exists='append')

    save_to_csv(news_df, f'newsletters_{today}.csv')

    txt_path = os.path.join(str(DATA_DIR), f'newsletter_{today}.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(newsletter_dict['content'])
    logger.info(f"  -> 뉴스레터 TXT: {txt_path}")

    return news_df


# ============================================================
# 전체 파이프라인 저장 (모든 테이블 일괄)
# ============================================================
def save_all_to_db(stock_df, signals_df=None, recs_df=None,
                   newsletter_dict=None):
    """
    모든 데이터를 DB + CSV에 저장합니다.

    Args:
        stock_df: 통합 주식 데이터
        signals_df: 분석 신호 DataFrame
        recs_df: 추천 결과 DataFrame
        newsletter_dict: 뉴스레터 dict
    """
    logger.info("[DB] 전체 데이터 저장 시작...")

    # (C) stocks
    save_stocks(stock_df)

    # (D) price_snapshots
    save_price_snapshots(stock_df)

    # (E) analysis_signals
    if signals_df is not None:
        save_analysis_signals(signals_df)

    # (F) recommendations
    if recs_df is not None:
        save_recommendations(recs_df)

    # (G) newsletters
    if newsletter_dict is not None:
        save_newsletter(newsletter_dict)

    logger.info("[DB] 전체 데이터 저장 완료")


# ============================================================
# (H) users & user_type — 사용자 및 성향 마스터
# ============================================================
def init_user_type_table():
    """사용자 유형 마스터(user_type) 테이블을 초기화합니다."""
    types = [
        {'type_id': 1, 'type_name': '안정형', 'description': '원금 손실을 최소화하고 안정적인 수익을 추구합니다.'},
        {'type_id': 2, 'type_name': '안정추구형', 'description': '원금 보전을 중시하되, 약간의 위험을 감수하여 추가 수익을 노립니다.'},
        {'type_id': 3, 'type_name': '위험중립형', 'description': '수익과 위험을 균형 있게 고려합니다.'},
        {'type_id': 4, 'type_name': '적극투자형', 'description': '수익 달성을 위해 어느 정도의 위험을 감수합니다.'},
        {'type_id': 5, 'type_name': '공격투자형', 'description': '고수익을 위해 높은 위험을 적극적으로 감수합니다.'},
    ]
    df = pd.DataFrame(types)
    save_to_db(df, 'user_type', if_exists='replace')
    logger.info("[DB] 'user_type' 마스터 테이블 초기화 완료")


def load_users_from_db():
    """DB에서 사용자 정보를 가져와 dict로 반환합니다."""
    query = "SELECT user_id, user_password, user_email FROM users"
    df = load_from_db(query)
    
    users_dict = {}
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            users_dict[row['user_id']] = {
                'user_password': row['user_password'],
                'user_email': row.get('user_email', '')
            }
        return users_dict
        
    # DB 조회 실패 시 CSV (JSON) 폴백
    import json
    csv_path = os.path.join(DATA_DIR, 'users_db.json')
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 새로운 포맷인 경우 {"users": [...]}
                if isinstance(data, dict) and "users" in data:
                    fallback_dict = {}
                    for u in data["users"]:
                        fallback_dict[u["user_id"]] = {
                            "user_password": u.get("user_password", ""),
                            "user_email": u.get("user_email", "")
                        }
                    return fallback_dict
                else:
                    return data # 구버전 호환
        except Exception as e:
            logger.error(f"users_db.json 로드 실패: {e}")
    return {}


def save_users_to_db(users_dict):
    """사용자 dict를 받아 users 테이블과 JSON 백업에 동시 저장합니다."""
    import json
    csv_path = os.path.join(DATA_DIR, 'users_db.json')
    
    # 기존 JSON 구조 읽어오기
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                data = {"users": []}
    except Exception:
        data = {"users": []}
        
    # users 배열 갱신
    new_users_list = []
    for uid, udata in users_dict.items():
        new_users_list.append({
            "user_id": uid,
            "user_password": udata.get("user_password", ""),
            "user_email": udata.get("user_email", "")
        })
    data["users"] = new_users_list

    try:
        with open(csv_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"users_db.json 백업 저장 실패: {e}")
        
    # JSON 파일 기반으로 DB 동기화
    sync_json_to_db(csv_path, 'users', if_exists='replace')


def save_user_profile(user_id, type_id):
    """
    사용자와 투자 성향(type_id) 매핑 정보를 user_profile 테이블에 저장합니다.
    (요청된 JSON 스키마를 위해 user_type_db.json 파일로 분리하여 저장합니다)
    """
    import json
    type_csv_path = os.path.join(DATA_DIR, 'user_type_db.json')
    
    # 1. JSON 구조 업데이트 (user_type 독립 파일)
    try:
        with open(type_csv_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict) or "user_type" not in data:
                data = {"user_type": []}
    except Exception:
        data = {"user_type": []}
        
    type_names = {
        1: "안정형", 2: "안정추구형", 3: "위험중립형", 4: "적극투자형", 5: "공격투자형"
    }
    
    user_type_list = data.get("user_type", [])
    found = False
    for ut in user_type_list:
        if ut.get("user_id") == user_id:
            ut["type_id"] = type_id
            ut["type_name"] = type_names.get(type_id, "Unknown Profile")
            ut["description"] = f"User has been profiled as {ut['type_name']}."
            found = True
            break
            
    if not found:
        user_type_list.append({
            "user_id": user_id,
            "type_id": type_id,
            "type_name": type_names.get(type_id, "Unknown Profile"),
            "description": f"User has been profiled as {type_names.get(type_id, 'Unknown Profile')}."
        })
        
    data["user_type"] = user_type_list
    
    try:
        with open(type_csv_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"user_type_db.json 백업 저장 실패: {e}")

    # JSON 기반 DB 동기화
    sync_json_to_db(type_csv_path, 'user_profile', if_exists='append')
    logger.info(f"[DB] '{user_id}' 투자 성향({type_id}) 프로필 저장 완료")
