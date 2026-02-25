# 📋 주식 추천 시스템 — 주요 코드 설명 보고서

> 평가 항목별 주요 코드 분석 및 설명서
> **1팀 | 2026-02-24**

---

## 1. 프로젝트 기획 및 주제 적절성 _(10점)_

### 1-1. 주제 선정 배경 및 문제 정의

주식 투자 입문자는 **"어떤 종목을 언제 사야 하는가"** 라는 정보 불균형 문제에 자주 직면합니다.  
본 프로젝트는 이를 해결하기 위해 아래 3가지 핵심 목표를 설정하였습니다.

| 문제 | 해결 접근 |
|------|-----------|
| 좋은 종목을 어떻게 고르나? | 거래량·외국인/기관 매매 데이터 기반 신호 분석 |
| 내 성향에 맞지 않는 추천 | 한양증권 기준 11문항 투자 성향 진단 |
| 정보 획득의 진입 장벽 | Streamlit 기반 시각화 대시보드 제공 |

### 1-2. 시스템 아키텍처

```
[데이터 수집]       [분석/처리]         [서비스]
scraper.py  ──▶  analyzer.py  ──▶   app.py (Streamlit)
scheduler   ──▶  rtd_analyzer ──▶   실시간 RTD 차트
                 db_manager   ──▶   MySQL / CSV
```

---

## 2. 데이터 수집 및 정제 _(25점)_

### 2-1. `requests` + `BeautifulSoup` — 거래량 상위 종목 수집

네이버 금융 `sise_quant.naver` 페이지에서 KOSPI/KOSDAQ 상위 100종목 데이터를 수집합니다.

```python
# scraper.py - scrape_top_volume() 함수

def create_session(retries=3, backoff=0.5):
    """재시도 로직이 포함된 requests.Session 생성"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],  # 서버 오류 시 자동 재시도
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)  # User-Agent 헤더 위장
    return session

def scrape_top_volume(market="KOSPI", limit=100, session=None):
    sosok = "0" if market == "KOSPI" else "1"
    url = f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}&page={page}"

    resp = session.get(url, timeout=10)
    resp.encoding = 'euc-kr'                          # 한글 인코딩 처리
    soup = BeautifulSoup(resp.text, 'html.parser')

    rows = soup.select('table.type_2 tr')             # CSS 셀렉터로 테이블 파싱
    for row in rows:
        cols = row.select('td')
        name  = cols[1].text.strip()
        code  = cols[1].find('a')['href'].split('code=')[-1]
        price = clean_number(cols[2].text)             # 숫자 정제 함수 적용
```

**핵심 포인트:**
- `Retry` 객체로 서버 불안정 시 자동 재시도 (최대 3회)
- `euc-kr` 인코딩 처리로 한글 깨짐 방지
- CSS 셀렉터(`table.type_2 tr`)로 정확한 데이터 위치 추출

---

### 2-2. 데이터 정제 함수

```python
# scraper.py - 데이터 정제 유틸리티

def clean_number(text):
    """텍스트에서 숫자를 추출하여 정수로 변환 (음수 지원)"""
    text = str(text).strip()
    is_negative = text.startswith('-') or '▼' in text  # 하락 기호 감지
    nums = re.sub(r'[^\d]', '', text)                  # 숫자 외 문자 제거
    result = int(nums) if nums else 0
    return -result if is_negative else result

def clean_float(text):
    """실수(소수점) 추출"""
    text = text.strip().replace(',', '')
    match = re.search(r'[-+]?\d+\.?\d*', text)
    return float(match.group()) if match else None

def parse_change_pct(pct_text):
    """'+2.35%' → 2.35, '-1.05%' → -1.05 변환"""
    pct_text = pct_text.strip().replace('%', '')
    return float(pct_text)
```

---

### 2-3. `Selenium` — 외국인/기관 매매 동향 수집

동적 렌더링이 필요한 페이지는 Selenium으로 수집합니다.

```python
# scraper.py - get_investor_trading() 함수

def get_driver():
    """Headless Chrome 드라이버 설정"""
    options = Options()
    options.add_argument('--headless')         # 화면 없이 실행
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=options)

def scrape_news_selenium(ticker, name, driver=None):
    """종목 뉴스 수집 (JavaScript 렌더링 필요)"""
    url = f"https://finance.naver.com/item/news_news.naver?code={ticker}"
    driver.get(url)
    # 페이지 로딩 대기
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'table.type5'))
    )
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    rows = soup.select('table.type5 tr')
```

---

### 2-4. `pykrx` — 과거 시세 데이터 (API 호출)

네이버 스크래핑 대신 pykrx API로 정확한 OHLCV 데이터를 수집합니다.

```python
# scraper.py - scrape_historical_data() 함수

from pykrx import stock

def scrape_historical_data(tickers, days=7):
    """
    pykrx API를 사용하여 종목의 과거 시세를 가져옵니다.
    pykrx는 한국거래소(KRX) 공식 데이터를 API 형태로 제공합니다.
    """
    end = datetime.today().strftime('%Y%m%d')
    start = (datetime.today() - timedelta(days=days)).strftime('%Y%m%d')

    dfs = []
    for ticker in tickers:
        df = stock.get_market_ohlcv(start, end, ticker)  # OHLCV 수집
        df['종목코드'] = ticker
        dfs.append(df)

    return pd.concat(dfs).reset_index()  # 날짜 인덱스 → 컬럼으로 변환
```

---

### 2-5. 데이터 구조화 결과 (`pandas DataFrame`)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `종목코드` | str | 6자리 KRX 종목코드 |
| `종목명` | str | 종목 이름 |
| `시장` | str | KOSPI / KOSDAQ |
| `현재가` | int | 현재 주가 (원) |
| `등락률` | str | 전일 대비 등락률 |
| `거래량` | int | 당일 누적 거래량 |
| `거래대금` | int | 당일 총 거래금액 (백만원) |
| `외국인_순매수량` | int | 외국인 순매수 수량 |
| `기관_순매수량` | int | 기관 순매수 수량 |

---

## 3. 데이터 분석 및 시각화 _(30점)_

### 3-1. `pandas` — 주식 데이터 분석

#### (1) 추세 점수(trend_score) 산출

```python
# analyzer.py - generate_analysis_signals() 함수

def generate_analysis_signals(df, window='1D'):
    """
    등락률, 거래량, 외국인/기관 매매를 가중 합산하여
    0~100 스케일의 추세 점수를 계산합니다.
    """
    result = df.copy()

    # 1) 등락률 점수 (40% 가중치)
    pct_col = '등락률(숫자)' if '등락률(숫자)' in df.columns else '등락률_num'
    result['등락점수'] = _normalize_series(
        pd.to_numeric(df[pct_col], errors='coerce'), ascending=True
    )  # 0~100 정규화

    # 2) 거래량 점수 (20% 가중치)
    result['거래량점수'] = _normalize_series(df['거래량'], ascending=True)

    # 3) 외국인 순매수 점수 (20% 가중치)
    if '외국인_순매수량' in df.columns:
        result['외국인점수'] = _normalize_series(df['외국인_순매수량'], ascending=True)
    else:
        result['외국인점수'] = 50  # 데이터 없으면 중립값

    # 4) 기관 순매수 점수 (20% 가중치)
    if '기관_순매수량' in df.columns:
        result['기관점수'] = _normalize_series(df['기관_순매수량'], ascending=True)
    else:
        result['기관점수'] = 50

    # 5) 최종 가중 합산
    result['trend_score'] = (
        result['등락점수']   * 0.40 +
        result['거래량점수'] * 0.20 +
        result['외국인점수'] * 0.20 +
        result['기관점수']   * 0.20
    ).round(1)

    # 6) BUY / HOLD / SELL 분류
    result['signal'] = result['trend_score'].apply(
        lambda s: 'BUY' if s >= 60 else ('SELL' if s < 40 else 'HOLD')
    )
    return result
```

#### (2) 투자 성향별 종목 스코어링

```python
# analyzer.py - score_stocks() 함수

WEIGHT_PROFILES = {
    '안정형':    {'배당수익률': 0.30, '시가총액_순위': 0.25, '변동폭_역순위': 0.25, ...},
    '위험중립형': {'외국인_순매수': 0.25, 'PER_적정': 0.20, '거래량_순위': 0.20, ...},
    '공격투자형': {'거래량_순위': 0.35, '등락률_절대값': 0.30, '변동폭_순위': 0.20, ...},
}

def score_stocks(df, investor_type):
    weights = WEIGHT_PROFILES.get(investor_type)

    # 지표별 정규화 후 가중치 적용
    score = pd.Series(0.0, index=df.index)
    for metric, weight in weights.items():
        score += _normalize_series(df[metric]) * weight

    df['추천점수'] = score.round(1)
    return df.sort_values('추천점수', ascending=False)
```

#### (3) 투자 성향 5단계 분류 알고리즘

```python
# analyzer.py - classify_investor_type() 함수

def classify_investor_type(answers):
    """
    11문항 점수를 합산하여 최대 가능 점수 대비 비율로 5단계 분류
    """
    total_score = 0
    max_possible = 0

    for q in SURVEY_QUESTIONS:
        selected_idx = answers.get(q['id'], 0)
        total_score  += q['options'][selected_idx][1]          # 선택 점수 합산
        max_possible += max(score for _, score in q['options']) # 최대 점수 합산

    ratio = total_score / max_possible  # 점수 비율 계산

    # 비율 구간별 성향 분류
    if   ratio <= 0.25: return '안정형',    total_score
    elif ratio <= 0.40: return '안정추구형', total_score
    elif ratio <= 0.60: return '위험중립형', total_score
    elif ratio <= 0.80: return '적극투자형', total_score
    else:               return '공격투자형', total_score
```

---

### 3-2. `seaborn` / `matplotlib` — 시각화

#### (1) seaborn — 거래량 급증 모멘텀 바 차트

```python
# app.py - RTD 실시간 분석 탭

import seaborn as sns
import matplotlib.pyplot as plt

fig_surge, ax_surge = plt.subplots(figsize=(8, 5))
fig_surge.patch.set_facecolor('#2b2622')  # 배경색 지정
ax_surge.set_facecolor('#2b2622')

# seaborn 수평 바 차트 (YlOrBr 황금 팔레트)
sns.barplot(
    x='시간당_순거래량',  # 직전 시간 대비 증가 거래량
    y='종목명',           # Y축: 종목명
    data=surge_df,        # 급증 TOP 10 데이터
    palette='YlOrBr_r',   # 웜 테마 색상
    ax=ax_surge
)

# 텍스트 색상 설정 (다크 배경 대응)
ax_surge.tick_params(colors='#f2ece4')
plt.title('직전 시간 대비 거래량 순증가 TOP 10', color='#dcb98c', fontsize=12)
plt.tight_layout()
st.pyplot(fig_surge)  # Streamlit에 Matplotlib 차트 삽입
plt.close()           # 메모리 해제
```

#### (2) matplotlib — 현재가 대비 거래대금 산점도

```python
# app.py - RTD 실시간 분석 탭

fig_scatter, ax_scatter = plt.subplots(figsize=(8, 5))
fig_scatter.patch.set_facecolor('#2b2622')
ax_scatter.set_facecolor('#2b2622')

# 산점도 (현재가 vs 거래대금)
ax_scatter.scatter(
    latest_df['현재가'],     # X축: 주가
    latest_df['거래대금'],   # Y축: 당일 거래대금
    c='#dcb98c',             # 점 색상
    alpha=0.6,               # 투명도 (점 겹침 시 밀도 파악)
    edgecolors='none'
)

plt.xlabel("현재가 (원)", color='#f2ece4')
plt.ylabel("거래대금", color='#f2ece4')
plt.title(f'가격대별 거래대금 분산 ({latest_time} 기준)', color='#dcb98c')
st.pyplot(fig_scatter)
plt.close()
```

#### (3) plotly — 인터랙티브 BUY/HOLD/SELL 바 차트

```python
# app.py - 분석 신호 페이지

import plotly.express as px

color_map = {'BUY': '#3fb950', 'HOLD': '#d29922', 'SELL': '#f85149'}

fig_sig = px.bar(
    signals_df,
    x='종목명',
    y='trend_score',        # 추세 점수 높이 = 막대 높이
    color='signal',         # 신호에 따라 색상 분기
    color_discrete_map=color_map,
    title='종목별 추세 점수 및 매매 신호',
    template='plotly_dark',
)

# BUY/SELL 기준선 추가
fig_sig.add_hline(y=60, line_dash='dash', line_color='#3fb950',
                  annotation_text='BUY 기준(60)')
fig_sig.add_hline(y=40, line_dash='dash', line_color='#f85149',
                  annotation_text='SELL 기준(40)')

st.plotly_chart(fig_sig, use_container_width=True)
```

---

## 4. 대시보드(웹앱) 구현 _(30점)_

### 4-1. Streamlit — 페이지 구성

```python
# app.py - 사이드바 네비게이션

import streamlit as st

# 6개 메뉴 라디오 버튼
page = st.radio(
    "메뉴 선택",
    ["🏠 메인 대시보드", "📋 투자 성향 설문", "⭐ 맞춤 종목 추천",
     "📈 분석 신호",    "📰 종목 뉴스",   "📧 뉴스레터"],
    label_visibility="collapsed",
)

# 페이지별 조건 분기 라우팅
if page == "🏠 메인 대시보드":
    show_main_dashboard()
elif page == "📋 투자 성향 설문":
    show_survey()
elif page == "⭐ 맞춤 종목 추천":
    if not st.session_state['logged_in']:
        st.warning("⚠️ 로그인이 필요합니다.")
        st.stop()
    show_recommendations()
```

### 4-2. 결과 시각화 연동 — Top 50 실시간 시세 패널

```python
# app.py - 메인 대시보드 Top 50 그리드

top50_df = stock_df.sort_values(by='거래량', ascending=False).head(50)

# 5열 그리드 배치
with st.expander("👀 종목 리스트 펼쳐보기 (Top 50)", expanded=True):
    cols = st.columns(5)
    for i, row in enumerate(top50_df.itertuples()):
        col_idx = i % 5                          # 5열로 순환 배치
        label_with_rank = f"{i+1}. {row.종목명}" # 1. 삼성전자 형태

        cols[col_idx].metric(
            label=label_with_rank,
            value=f"{row.현재가:,}",             # 3자리마다 쉼표 (₩ 표기)
            delta=f"{row.등락률}",               # 등락률 → 초록/빨강 arrow 자동
            delta_color="normal"
        )
```

### 4-3. 회원 인증 시스템 — bcrypt 비밀번호 암호화

```python
# app.py - 회원가입/로그인 구현

import bcrypt as _bcrypt
import json

def _safe_hash(password: str) -> str:
    """비밀번호를 bcrypt로 단방향 암호화"""
    pw_bytes = password.encode('utf-8')[:72]      # 72바이트 제한 처리
    return _bcrypt.hashpw(pw_bytes, _bcrypt.gensalt()).decode('utf-8')

def _safe_verify(password: str, hashed: str) -> bool:
    """입력 비밀번호와 저장된 해시 값을 안전하게 비교"""
    pw_bytes = password.encode('utf-8')[:72]
    return _bcrypt.checkpw(pw_bytes, hashed.encode('utf-8'))

# 회원가입 시 JSON 구조로 저장
users[new_id] = {
    "user_password": _safe_hash(new_pw),    # 암호화 저장
    "user_email":    new_email,
    "type_id":       "미정"                  # 설문 완료 전 기본값
}

# 설문 완료 시 type_id 자동 업데이트
if st.session_state.get('logged_in'):
    users[user_id]['type_id'] = investor_type   # 예: '위험중립형'
    save_users(users)
    st.toast(f"✅ 투자 성향({investor_type}) 저장 완료!")
```

### 4-4. 자동 데이터 수집 스케줄러 — UI 일관성 유지

```python
# scheduler_job.py - APScheduler

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone='Asia/Seoul')

# 평일 09시~15시 매 정각 자동 실행
scheduler.add_job(
    job_realtime_market_data,   # 수집 함수
    'cron',
    day_of_week='mon-fri',      # 주중만
    hour='9-15',                # 장 운영 시간
    minute=0                    # 정각
)
scheduler.start()
```

---

## 📊 주요 성과 요약

| 평가 항목 | 구현 내용 | 사용 기술 |
|-----------|-----------|-----------|
| 데이터 수집 | KOSPI/KOSDAQ 200종목, 7일 과거 시세 | `requests`, `BS4`, `Selenium`, `pykrx` |
| 데이터 정제 | 음수 처리, 인코딩, 타입 변환, 결측치 처리 | `pandas`, `re`, `numpy` |
| 통계 분석 | trend_score, 성향별 가중 스코어링 | `pandas`, `numpy` |
| 시각화 | 바차트, 산점도, 파이차트, 캔들스틱, Top50 그리드 | `seaborn`, `matplotlib`, `plotly` |
| 웹앱 구현 | 6페이지 대시보드, 회원 인증, 접근 제어 | `streamlit` |
| 자동화 | 시간별 데이터 수집 → DB/CSV 저장 | `apscheduler` |

---

*© 2026 1팀 미니프로젝트 — 주식 추천 시스템*
