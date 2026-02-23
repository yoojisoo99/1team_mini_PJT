"""
네이버 증권 주식 데이터 스크래핑 & 정제
=======================================
- requests + BeautifulSoup : 거래량 상위 종목 시세 수집
- selenium                 : 종목별 최신 뉴스 수집
- 수집한 데이터는 CSV로 저장
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================
# 1. [requests + BeautifulSoup] 거래량 상위 종목 수집
# ============================================================
def clean_number(text):
    """텍스트에서 숫자(콤마 포함)만 추출하여 정수로 변환합니다."""
    nums = re.sub(r'[^\d]', '', text)
    return int(nums) if nums else 0


def scrape_top_volume(market="KOSPI", limit=20):
    """
    네이버 금융에서 거래량 상위 종목을 스크래핑합니다.

    Args:
        market: "KOSPI" 또는 "KOSDAQ"
        limit:  수집할 종목 수
    Returns:
        pandas DataFrame
    """
    sosok = "0" if market == "KOSPI" else "1"
    base_url = f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    stocks = []
    page = 1

    while len(stocks) < limit:
        url = f"{base_url}&page={page}"
        resp = requests.get(url, headers=headers)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')

        rows = soup.select('table.type_2 tr')
        found = False

        for row in rows:
            cols = row.select('td')
            if len(cols) < 10 or not cols[1].text.strip():
                continue

            found = True
            try:
                name = cols[1].text.strip()
                code = cols[1].find('a')['href'].split('code=')[-1]

                # ── 데이터 정제 ──
                price  = clean_number(cols[2].text)          # 현재가
                volume = clean_number(cols[5].text)          # 거래량

                # 전일비: "하락\n\t\t\t3" 같은 노이즈 제거 → 숫자만 추출
                change_val = clean_number(cols[3].text)

                # 등락률: "+1.05%" / "-2.30%" 그대로 유지
                change_pct = cols[4].text.strip()

                # 등락률 부호를 전일비에 반영 (+/-)
                if '-' in change_pct:
                    change_val = -change_val

                # 거래대금 (백만원)
                trade_val = clean_number(cols[6].text)

                stocks.append({
                    '종목코드': code,
                    '종목명':   name,
                    '시장':     market,
                    '현재가':   price,
                    '전일비':   change_val,
                    '등락률':   change_pct,
                    '거래량':   volume,
                    '거래대금': trade_val,
                    '수집시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })

                if len(stocks) >= limit:
                    break

            except (ValueError, TypeError, AttributeError) as e:
                print(f"  [정제 오류] {e}")
                continue

        if not found:
            break
        page += 1
        time.sleep(0.5)

    df = pd.DataFrame(stocks)
    print(f"[완료] [{market}] 거래량 상위 {len(df)}개 종목 수집 완료")
    return df


# ============================================================
# 2. [Selenium] 종목별 최신 뉴스 수집
# ============================================================
def scrape_news(ticker, limit=3):
    """
    네이버 금융에서 특정 종목의 최신 뉴스 제목을 수집합니다.

    Args:
        ticker: 종목코드 (예: "005930")
        limit:  수집할 뉴스 개수
    Returns:
        list of str
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')

    driver = webdriver.Chrome(options=options)
    titles = []

    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={ticker}&page=1"
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'table.type5'))
        )

        articles = driver.find_elements(By.CSS_SELECTOR, '.title a')
        for i, a in enumerate(articles):
            if i >= limit:
                break
            clean = a.text.strip().replace("'", "").replace('"', '')
            if clean:
                titles.append(clean)

    except Exception as e:
        print(f"  [뉴스 수집 실패] {ticker}: {e}")
    finally:
        driver.quit()

    return titles


# ============================================================
# 3. 메인 실행
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("[START] 네이버 증권 데이터 스크래핑 시작")
    print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # -- STEP 1: 거래량 상위 종목 수집 --
    kospi_df  = scrape_top_volume("KOSPI",  limit=20)
    kosdaq_df = scrape_top_volume("KOSDAQ", limit=20)
    all_df = pd.concat([kospi_df, kosdaq_df], ignore_index=True)

    # -- STEP 2: 상위 5개 종목 뉴스 수집 --
    print("\n[NEWS] 상위 5개 종목 뉴스 수집 중...")
    news_data = []
    for _, row in all_df.head(5).iterrows():
        news_list = scrape_news(row['종목코드'])
        for title in news_list:
            news_data.append({
                '종목코드': row['종목코드'],
                '종목명':   row['종목명'],
                '뉴스제목': title,
                '수집시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
        print(f"  [OK] {row['종목명']}({row['종목코드']}) - {len(news_list)}건")
        time.sleep(1)

    news_df = pd.DataFrame(news_data) if news_data else pd.DataFrame()

    # -- STEP 3: CSV 파일로 저장 --
    today = datetime.now().strftime('%Y%m%d')
    stock_csv = f"top_volume_{today}.csv"
    news_csv  = f"stock_news_{today}.csv"

    all_df.to_csv(stock_csv, index=False, encoding='utf-8-sig')
    if not news_df.empty:
        news_df.to_csv(news_csv, index=False, encoding='utf-8-sig')

    print(f"\n{'='*55}")
    print(f"[DONE] 수집 완료!")
    print(f"   -> {stock_csv} ({len(all_df)}개 종목)")
    print(f"   -> {news_csv} ({len(news_df)}건 뉴스)")
    print(f"{'='*55}")

    # 결과 미리보기
    print("\n[거래량 상위 종목 미리보기]")
    print(all_df.head(10).to_string(index=False))
