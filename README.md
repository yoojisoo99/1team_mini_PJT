# 📊 투자 성향별 주식 추천 웹앱

## 프로젝트 목표
- 네이버 증권 웹스크래핑으로 거래량·외국인/기관 매매 데이터 수집
- 한양증권 기준 11문항 설문 → **5단계 투자 성향 분류**
- 성향별 맞춤 종목 추천 및 인터랙티브 시각화
- Streamlit 기반 대시보드 웹앱

## 기술 스택

| 분류 | 기술 |
|------|------|
| 웹 스크래핑 | `requests`, `BeautifulSoup`, `Selenium` |
| 데이터 분석 | `pandas`, `numpy` |
| 시각화 | `plotly`, `matplotlib`, `seaborn` |
| 웹앱 | `streamlit` |
| 데이터 저장 | `pymysql`, `sqlalchemy` (초안) / CSV |
| 환경 관리 | `uv`, `python-dotenv` |

## 프로젝트 구조

```
miniproject_1/
├── app.py              # Streamlit 웹앱 (메인)
├── scraper.py          # 네이버 증권 스크래핑 모듈
├── analyzer.py         # 투자 성향 분석 & 추천 엔진
├── config.py           # 환경 설정 관리
├── db_manager.py       # DB 연동 초안 (CSV fallback)
├── schema.sql          # MySQL 스키마 정의
├── .env.example        # 환경 변수 템플릿
├── pyproject.toml      # 의존성 관리
└── data/               # CSV 데이터 저장
    ├── stock_data_YYYYMMDD.csv
    └── stock_news_YYYYMMDD.csv
```

## 투자 성향 5단계

| 성향 | 설명 | 추천 전략 |
|------|------|-----------|
| 🛡️ 안정형 | 원금 손실 미허용 | 고배당 대형 우량주 |
| 🔒 안정추구형 | 안정적 투자, 일부 변동 허용 | 배당+가치주, 기관 매수 |
| ⚖️ 위험중립형 | 일정 손실 감수 | 성장주, 외국인 매수 |
| 🚀 적극투자형 | 높은 수익 추구 | 모멘텀, 고변동성 |
| 🔥 공격투자형 | 시장 초과 수익 추구 | 테마주, 최고 거래량 |

## 설치 및 실행

```bash
# 1. 가상환경 생성 & 의존성 설치
uv sync

# 2. 데이터 수집
uv run python scraper.py

# 3. Streamlit 앱 실행
uv run streamlit run app.py
```

## Pipeline

```
데이터 수집 (scraper.py)
    ├── [requests+BS4] 거래량 상위 종목
    ├── [requests+BS4] 종목 상세 정보 (PER/PBR/배당)
    ├── [Selenium] 외국인/기관 매매 동향
    └── [Selenium] 종목 뉴스
         ↓
데이터 정제 & CSV 저장
         ↓
투자 성향 분석 (analyzer.py)
    ├── 11문항 설문 → 5단계 분류
    └── 성향별 가중치 스코어링
         ↓
Streamlit 대시보드 (app.py)
    ├── 🏠 시장 개요
    ├── 📋 투자 성향 설문
    ├── ⭐ 맞춤 종목 추천
    └── 📰 종목 뉴스
```
