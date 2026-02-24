"""
📊 투자 성향별 주식 추천 시스템
================================
Streamlit 기반 대시보드 웹앱

페이지 구성:
  🏠 메인 대시보드  - 시장 개요 및 거래량 상위 종목
  📋 투자 성향 설문  - 11문항 기반 5단계 성향 분류
  ⭐ 맞춤 종목 추천  - 성향별 추천 종목 리스트 및 차트
  📰 종목 뉴스      - 추천 종목 관련 최신 뉴스
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import os
import glob
from datetime import datetime

from analyzer import (
    SURVEY_QUESTIONS, classify_investor_type, score_stocks,
    get_top_recommendations, generate_analysis_summary,
    TYPE_DESCRIPTIONS, WEIGHT_PROFILES,
    generate_analysis_signals, generate_newsletter,
)

# ── 한글 폰트 설정 (matplotlib) ──
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 페이지 설정 ──
st.set_page_config(
    page_title="📊 투자 성향별 주식 추천 시스템",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 0. 데이터 로드
# ============================================================
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


@st.cache_data(ttl=300)
def load_latest_data():
    """data/ 디렉토리에서 최신 CSV 파일을 로드합니다."""
    stock_files = sorted(glob.glob(os.path.join(DATA_DIR, 'stock_data_*.csv')))
    news_files = sorted(glob.glob(os.path.join(DATA_DIR, 'stock_news_*.csv')))
    hist_files = sorted(glob.glob(os.path.join(DATA_DIR, 'historical_*.csv')))
    signal_files = sorted(glob.glob(os.path.join(DATA_DIR, 'analysis_signals_*.csv')))

    # data/ 폴더에 없으면 프로젝트 루트에서도 탐색
    if not stock_files:
        root_dir = os.path.dirname(os.path.abspath(__file__))
        stock_files = sorted(glob.glob(os.path.join(root_dir, 'stock_data_*.csv')))
        news_files = sorted(glob.glob(os.path.join(root_dir, 'stock_news_*.csv')))

    stock_df = pd.DataFrame()
    news_df = pd.DataFrame()
    hist_df = pd.DataFrame()
    signals_df = pd.DataFrame()

    if stock_files:
        stock_df = pd.read_csv(stock_files[-1])
        st.session_state['data_file'] = os.path.basename(stock_files[-1])
    if news_files:
        news_df = pd.read_csv(news_files[-1])
    if hist_files:
        hist_df = pd.read_csv(hist_files[-1])
    if signal_files:
        signals_df = pd.read_csv(signal_files[-1])

    # signals가 없으면 실시간 생성
    if signals_df.empty and not stock_df.empty:
        signals_df = generate_analysis_signals(stock_df, '1D')

    return stock_df, news_df, hist_df, signals_df


# ============================================================
# CSS 스타일
# ============================================================
st.markdown("""
<style>
    /* 전체 배경색 — 깔끔한 다크 테마 */
    .stApp {
        background: linear-gradient(160deg, #0d1117 0%, #161b22 40%, #1a2332 100%);
    }

    /* 사이드바 */
    [data-testid="stSidebar"] {
        background: rgba(13, 17, 23, 0.97);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    /* 메트릭 카드 */
    [data-testid="stMetric"] {
        background: rgba(22, 27, 34, 0.8);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 16px;
    }

    /* 헤더 스타일 */
    h1 {
        background: linear-gradient(90deg, #58a6ff, #3fb950);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }

    h2, h3 {
        color: #e6edf3 !important;
    }

    /* 성향 결과 카드 */
    .investor-card {
        background: rgba(22, 27, 34, 0.9);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
    }

    .investor-card h2 {
        margin: 0 0 12px 0;
        font-size: 28px;
    }

    .investor-card p {
        color: #8b949e;
        line-height: 1.6;
    }

    /* 추천 종목 카드 */
    .stock-card {
        background: rgba(22, 27, 34, 0.8);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        transition: transform 0.2s, box-shadow 0.2s;
    }

    .stock-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(88,166,255,0.15);
    }

    /* 점수 배지 */
    .score-badge {
        display: inline-block;
        background: linear-gradient(135deg, #238636, #2ea043);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(22, 27, 34, 0.8);
        border-radius: 8px;
        color: #8b949e;
        padding: 8px 24px;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #238636, #2ea043) !important;
        color: white !important;
    }

    /* 설문 라디오 버튼 */
    .stRadio label {
        color: #c9d1d9 !important;
    }

    /* 데이터프레임 */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 사이드바 네비게이션
# ============================================================
with st.sidebar:
    st.markdown("## 📊 주식 추천 시스템")
    st.markdown("---")

    page = st.radio(
        "메뉴 선택",
        ["🏠 메인 대시보드", "📋 투자 성향 설문", "⭐ 맞춤 종목 추천",
         "📈 분석 신호", "📰 종목 뉴스", "📧 뉴스레터"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # 데이터 새로고침 버튼
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # 데이터 파일 정보
    if 'data_file' in st.session_state:
        st.caption(f"📁 {st.session_state['data_file']}")

    st.markdown("---")
    st.markdown(
        "<div style='color:#888; font-size:12px; text-align:center;'>"
        "네이버 증권 데이터 기반<br>"
        "투자 성향 5단계 분류<br>"
        "© 2026 Stock Recommender"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# 📌 데이터 로드
# ============================================================
stock_df, news_df, hist_df, signals_df = load_latest_data()


# ============================================================
# 🏠 메인 대시보드
# ============================================================
if page == "🏠 메인 대시보드":
    st.markdown("# 🏠 시장 개요 대시보드")

    if stock_df.empty:
        st.warning(
            "⚠️ 데이터가 없습니다. 먼저 `python scraper.py`를 실행하여 "
            "데이터를 수집해 주세요."
        )
        st.code("python scraper.py", language="bash")
        st.stop()

    # ── 요약 통계 ──
    summary = generate_analysis_summary(stock_df)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📈 총 종목 수", summary.get('총 종목 수', 0))
    with col2:
        st.metric("🟢 상승", summary.get('상승 종목 수', 0))
    with col3:
        st.metric("🔴 하락", summary.get('하락 종목 수', 0))
    with col4:
        avg_pct = summary.get('평균 등락률(%)', 0)
        st.metric("📊 평균 등락률", f"{avg_pct}%")

    st.markdown("---")

    # ── 시장별 탭 ──
    tab1, tab2, tab3 = st.tabs(["📊 거래량 차트", "🔥 외국인/기관 매매", "📋 전체 데이터"])

    with tab1:
        st.markdown("### 거래량 상위 종목")

        # KOSPI/KOSDAQ 선택
        market_filter = st.selectbox(
            "시장 선택", ["전체", "KOSPI", "KOSDAQ"], key="market_filter_vol"
        )
        filtered = stock_df if market_filter == "전체" else stock_df[stock_df['시장'] == market_filter]

        top20 = filtered.head(20)

        if not top20.empty:
            fig = px.bar(
                top20,
                x='종목명',
                y='거래량',
                color='시장',
                color_discrete_map={'KOSPI': '#667eea', 'KOSDAQ': '#764ba2'},
                title='거래량 상위 종목',
                template='plotly_dark',
            )
            fig.update_layout(
                xaxis_tickangle=-45,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e0e0ff'),
                height=500,
            )
            st.plotly_chart(fig, use_container_width=True)

            # 등락률 산점도
            if '등락률(숫자)' in top20.columns:
                fig2 = px.scatter(
                    top20,
                    x='거래량',
                    y='등락률(숫자)',
                    size='거래대금',
                    color='시장',
                    hover_name='종목명',
                    color_discrete_map={'KOSPI': '#667eea', 'KOSDAQ': '#764ba2'},
                    title='거래량 vs 등락률 (버블 크기 = 거래대금)',
                    template='plotly_dark',
                )
                fig2.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e0e0ff'),
                    height=500,
                )
                st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.markdown("### 외국인/기관 매매 동향")

        if '외국인_순매수량' in stock_df.columns and '기관_순매수량' in stock_df.columns:
            inv_df = stock_df[['종목명', '외국인_순매수량', '기관_순매수량']].dropna()

            if not inv_df.empty:
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(
                    x=inv_df['종목명'],
                    y=inv_df['외국인_순매수량'],
                    name='외국인',
                    marker_color='#667eea',
                ))
                fig3.add_trace(go.Bar(
                    x=inv_df['종목명'],
                    y=inv_df['기관_순매수량'],
                    name='기관',
                    marker_color='#764ba2',
                ))
                fig3.update_layout(
                    title='외국인/기관 순매수량 비교',
                    barmode='group',
                    template='plotly_dark',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e0e0ff'),
                    xaxis_tickangle=-45,
                    height=500,
                )
                st.plotly_chart(fig3, use_container_width=True)

                # Seaborn 히트맵 (matplotlib)
                st.markdown("### 투자 지표 상관관계 히트맵")
                numeric_cols = ['현재가', '거래량', '거래대금', 'PER', 'PBR',
                                '외국인_순매수량', '기관_순매수량']
                available_cols = [c for c in numeric_cols if c in stock_df.columns]

                if len(available_cols) >= 3:
                    corr_data = stock_df[available_cols].apply(
                        pd.to_numeric, errors='coerce'
                    ).corr()

                    fig_heat, ax = plt.subplots(figsize=(10, 6))
                    fig_heat.patch.set_facecolor('#1a1a2e')
                    ax.set_facecolor('#1a1a2e')
                    sns.heatmap(
                        corr_data, annot=True, cmap='coolwarm', fmt='.2f',
                        ax=ax, linewidths=0.5,
                        annot_kws={'color': 'white', 'fontsize': 9},
                        cbar_kws={'label': '상관계수'},
                    )
                    ax.tick_params(colors='white')
                    ax.xaxis.label.set_color('white')
                    ax.yaxis.label.set_color('white')
                    plt.title('투자 지표 상관관계', color='white', fontsize=14)
                    plt.tight_layout()
                    st.pyplot(fig_heat)
                    plt.close()
        else:
            st.info("외국인/기관 매매 데이터가 없습니다.")

    with tab3:
        st.markdown("### 전체 종목 데이터")

        # 필터 옵션
        col_a, col_b = st.columns(2)
        with col_a:
            market_filter2 = st.selectbox(
                "시장", ["전체", "KOSPI", "KOSDAQ"], key="market_filter_all"
            )
        with col_b:
            sort_col = st.selectbox(
                "정렬 기준", ['거래량', '현재가', '등락률(숫자)', '거래대금'],
                key="sort_col"
            )

        display_df = stock_df.copy()
        if market_filter2 != "전체":
            display_df = display_df[display_df['시장'] == market_filter2]

        if sort_col in display_df.columns:
            display_df = display_df.sort_values(sort_col, ascending=False)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=600,
        )


# ============================================================
# 📋 투자 성향 설문
# ============================================================
elif page == "📋 투자 성향 설문":
    st.markdown("# 📋 투자 성향 진단")
    st.markdown(
        "> 한양증권 투자성향진단 기준 **11문항**으로 구성된 설문입니다.\n"
        "> 솔직하게 답변해 주시면 **5단계 투자 성향**을 분류해 드립니다."
    )
    st.markdown("---")

    # ── 설문 폼 ──
    answers = {}
    with st.form("survey_form"):
        for i, q in enumerate(SURVEY_QUESTIONS):
            st.markdown(f"### {i+1}. {q['question']}")
            options = [opt[0] for opt in q['options']]
            selected = st.radio(
                f"Q{i+1}",
                range(len(options)),
                format_func=lambda idx, opts=options: f"{'①②③④⑤⑥'[idx]} {opts[idx]}",
                key=f"q_{q['id']}",
                label_visibility="collapsed",
            )
            answers[q['id']] = selected
            st.markdown("")

        submitted = st.form_submit_button(
            "🔍 투자 성향 진단하기",
            use_container_width=True,
        )

    if submitted:
        investor_type, total_score = classify_investor_type(answers)
        st.session_state['investor_type'] = investor_type
        st.session_state['survey_score'] = total_score
        st.session_state['survey_answers'] = answers

        type_info = TYPE_DESCRIPTIONS[investor_type]

        st.markdown("---")
        st.markdown(
            f"""
            <div class="investor-card">
                <h2>{type_info['emoji']} 당신의 투자 성향: {type_info['title']}</h2>
                <p>{type_info['desc']}</p>
                <p style="color:{type_info['color']}; font-weight:700; font-size:16px;">
                    💡 추천 전략: {type_info['strategy']}
                </p>
                <p style="color:#888; font-size:14px;">총점: {total_score}점</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 5단계 프로그레스
        types_order = ['안정형', '안정추구형', '위험중립형', '적극투자형', '공격투자형']
        current_idx = types_order.index(investor_type)

        st.markdown("### 투자 성향 스케일")
        cols = st.columns(5)
        for i, t in enumerate(types_order):
            info = TYPE_DESCRIPTIONS[t]
            with cols[i]:
                if i == current_idx:
                    st.markdown(
                        f"<div style='text-align:center; padding:12px; "
                        f"background:linear-gradient(135deg, {info['color']}33, {info['color']}66); "
                        f"border:2px solid {info['color']}; border-radius:12px;'>"
                        f"<span style='font-size:24px;'>{info['emoji']}</span><br>"
                        f"<span style='color:white; font-weight:700;'>{t}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='text-align:center; padding:12px; "
                        f"background:rgba(255,255,255,0.03); "
                        f"border:1px solid rgba(255,255,255,0.1); border-radius:12px;'>"
                        f"<span style='font-size:24px;'>{info['emoji']}</span><br>"
                        f"<span style='color:#888;'>{t}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("")
        st.info("👈 좌측 메뉴에서 **⭐ 맞춤 종목 추천**을 선택하시면 추천 결과를 확인할 수 있습니다.")


# ============================================================
# ⭐ 맞춤 종목 추천
# ============================================================
elif page == "⭐ 맞춤 종목 추천":
    st.markdown("# ⭐ 맞춤 종목 추천")

    if stock_df.empty:
        st.warning("⚠️ 주식 데이터가 없습니다. 먼저 `python scraper.py`를 실행해 주세요.")
        st.stop()

    # ── 투자 성향 확인 ──
    if 'investor_type' not in st.session_state:
        st.info("📋 먼저 **투자 성향 설문**을 완료해 주세요.")

        # 임시 선택 옵션
        st.markdown("---")
        st.markdown("### 또는 투자 성향을 직접 선택하세요")
        investor_type = st.selectbox(
            "투자 성향 선택",
            ['안정형', '안정추구형', '위험중립형', '적극투자형', '공격투자형'],
            index=2,
        )
    else:
        investor_type = st.session_state['investor_type']
        type_info = TYPE_DESCRIPTIONS[investor_type]
        st.markdown(
            f"**{type_info['emoji']} 현재 투자 성향: {type_info['title']}** — "
            f"_{type_info['strategy']}_"
        )

    st.markdown("---")

    # ── 추천 개수 설정 ──
    col1, col2 = st.columns([1, 3])
    with col1:
        top_n = st.slider("추천 종목 수", 3, 20, 10)
    with col2:
        market_sel = st.selectbox(
            "시장 필터", ["전체", "KOSPI", "KOSDAQ"], key="rec_market"
        )

    # ── 데이터 필터링 ──
    filtered_df = stock_df.copy()
    if market_sel != "전체":
        filtered_df = filtered_df[filtered_df['시장'] == market_sel]

    # ── 추천 종목 계산 ──
    recommendations = get_top_recommendations(filtered_df, investor_type, top_n)

    if recommendations.empty:
        st.warning("추천 가능한 종목이 없습니다.")
        st.stop()

    # ── 추천 결과 표시 ──
    st.markdown(f"### 🏆 {investor_type} 성향 추천 TOP {len(recommendations)}")

    # 상위 3개 하이라이트
    top3_cols = st.columns(min(3, len(recommendations)))
    for i, col in enumerate(top3_cols):
        if i < len(recommendations):
            row = recommendations.iloc[i]
            with col:
                medals = ['🥇', '🥈', '🥉']
                medal = medals[i] if i < 3 else ''
                change_color = '#3fb950' if row.get('전일비', 0) > 0 else '#f85149'
                st.markdown(
                    f"""
                    <div class="stock-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:18px; font-weight:700; color:#e6edf3;">
                                {medal} {row['종목명']}
                            </span>
                            <span class="score-badge">{row.get('추천점수', 0):.1f}점</span>
                        </div>
                        <div style="margin-top:8px; color:#8b949e;">
                            현재가: <strong style="color:white;">{row['현재가']:,}원</strong>
                            <span style="color:{change_color}; margin-left:8px;">
                                {row.get('등락률', 'N/A')}
                            </span>
                        </div>
                        <div style="margin-top:4px; color:#8b949e; font-size:13px;">
                            {row.get('추천이유', '')}
                        </div>
                        <div style="margin-top:4px; color:#6e7681; font-size:12px;">
                            거래량: {row['거래량']:,} | {row['시장']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("")

    # ── 추천 점수 차트 ──
    tab_a, tab_b, tab_c, tab_d = st.tabs(["📊 추천 점수 차트", "📈 캔들스틱 차트", "📈 종목 비교", "📋 상세 데이터"])

    with tab_a:
        fig_score = px.bar(
            recommendations,
            x='종목명',
            y='추천점수',
            color='추천점수',
            color_continuous_scale='Viridis',
            title=f'{investor_type} 성향 추천 종목 점수',
            template='plotly_dark',
            text='추천점수',
        )
        fig_score.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        fig_score.update_layout(
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e0e0ff'),
            height=500,
            showlegend=False,
        )
        st.plotly_chart(fig_score, use_container_width=True)

        # 레이더 차트 (상위 5개 종목)
        if len(recommendations) >= 3:
            st.markdown("### 📡 상위 종목 레이더 차트")
            radar_metrics = ['거래량', '현재가', '거래대금']
            if 'PER' in recommendations.columns:
                radar_metrics.append('PER')
            if '외국인_순매수량' in recommendations.columns:
                radar_metrics.append('외국인_순매수량')

            available_radar = [m for m in radar_metrics if m in recommendations.columns]
            if len(available_radar) >= 3:
                top5_rec = recommendations.head(5)
                fig_radar = go.Figure()

                for _, row in top5_rec.iterrows():
                    values = []
                    for col in available_radar:
                        val = pd.to_numeric(row.get(col, 0), errors='coerce')
                        values.append(val if pd.notna(val) else 0)

                    # 정규화
                    max_val = max(abs(v) for v in values) if values else 1
                    if max_val == 0:
                        max_val = 1
                    normalized = [v / max_val * 100 for v in values]

                    fig_radar.add_trace(go.Scatterpolar(
                        r=normalized + [normalized[0]],
                        theta=available_radar + [available_radar[0]],
                        name=row['종목명'],
                        fill='toself',
                        opacity=0.5,
                    ))

                fig_radar.update_layout(
                    polar=dict(bgcolor='rgba(0,0,0,0)'),
                    template='plotly_dark',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e0e0ff'),
                    height=500,
                    title='상위 종목 비교 레이더',
                )
                st.plotly_chart(fig_radar, use_container_width=True)

    with tab_b:
        st.markdown("### 📈 개별 종목 캔들스틱 차트")

        if hist_df.empty:
            st.info("⏳ 과거 시세 데이터가 없습니다. `python scraper.py`를 실행하면 pykrx로 5일캡 데이터를 수집합니다.")
        else:
            # 추천 종목 중 선택
            rec_tickers = recommendations['종목코드'].tolist() if '종목코드' in recommendations.columns else []
            rec_names = recommendations['종목명'].tolist() if '종목명' in recommendations.columns else []

            available_tickers = [t for t in rec_tickers if t in hist_df['종목코드'].values]
            if available_tickers:
                ticker_name_map = dict(zip(rec_tickers, rec_names))
                display_options = [f"{ticker_name_map.get(t, t)} ({t})" for t in available_tickers]

                selected_display = st.selectbox("종목 선택", display_options, key="candle_stock")
                selected_ticker = available_tickers[display_options.index(selected_display)]

                stock_hist = hist_df[hist_df['종목코드'] == selected_ticker].sort_values('날짜')

                if not stock_hist.empty:
                    # 캔들스틱 차트
                    fig_candle = go.Figure(data=[go.Candlestick(
                        x=stock_hist['날짜'],
                        open=stock_hist['시가'],
                        high=stock_hist['고가'],
                        low=stock_hist['저가'],
                        close=stock_hist['종가'],
                        increasing_line_color='#3fb950',
                        decreasing_line_color='#f85149',
                    )])
                    fig_candle.update_layout(
                        title=f"{ticker_name_map.get(selected_ticker, selected_ticker)} 5일 캔들스틱",
                        template='plotly_dark',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e6edf3'),
                        height=450,
                        xaxis_rangeslider_visible=False,
                    )
                    st.plotly_chart(fig_candle, use_container_width=True)

                    # 거래량 차트
                    fig_vol = px.bar(
                        stock_hist, x='날짜', y='거래량',
                        title=f"{ticker_name_map.get(selected_ticker, '')} 거래량 추이",
                        template='plotly_dark',
                        color_discrete_sequence=['#58a6ff'],
                    )
                    fig_vol.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e6edf3'),
                        height=300,
                    )
                    st.plotly_chart(fig_vol, use_container_width=True)
            else:
                st.info("추천 종목의 과거 시세 데이터가 없습니다.")

    with tab_c:
        st.markdown("### 추천 종목 등락률 비교")
        if '등락률(숫자)' in recommendations.columns:
            fig_change = px.bar(
                recommendations,
                x='종목명',
                y='등락률(숫자)',
                color='등락률(숫자)',
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                title='추천 종목 등락률',
                template='plotly_dark',
            )
            fig_change.update_layout(
                xaxis_tickangle=-45,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e0e0ff'),
                height=450,
            )
            st.plotly_chart(fig_change, use_container_width=True)

        # PER / PBR 분포 (Seaborn)
        if 'PER' in recommendations.columns and 'PBR' in recommendations.columns:
            st.markdown("### PER / PBR 분포")
            fig_pp, axes = plt.subplots(1, 2, figsize=(14, 5))
            fig_pp.patch.set_facecolor('#1a1a2e')

            for ax in axes:
                ax.set_facecolor('#1a1a2e')
                ax.tick_params(colors='white')
                ax.xaxis.label.set_color('white')
                ax.yaxis.label.set_color('white')

            per_data = pd.to_numeric(recommendations['PER'], errors='coerce').dropna()
            pbr_data = pd.to_numeric(recommendations['PBR'], errors='coerce').dropna()

            if not per_data.empty:
                sns.histplot(per_data, kde=True, ax=axes[0], color='#667eea')
                axes[0].set_title('PER 분포', color='white', fontsize=13)
                axes[0].set_xlabel('PER')

            if not pbr_data.empty:
                sns.histplot(pbr_data, kde=True, ax=axes[1], color='#764ba2')
                axes[1].set_title('PBR 분포', color='white', fontsize=13)
                axes[1].set_xlabel('PBR')

            plt.tight_layout()
            st.pyplot(fig_pp)
            plt.close()

    with tab_d:
        st.markdown("### 추천 종목 상세 데이터")
        display_cols = [
            '종목명', '시장', '현재가', '등락률', '거래량', '거래대금',
            'PER', 'PBR', '배당수익률', '외국인_순매수량', '기관_순매수량',
            '추천점수', '추천이유'
        ]
        avail_cols = [c for c in display_cols if c in recommendations.columns]
        st.dataframe(
            recommendations[avail_cols],
            use_container_width=True,
            hide_index=True,
            height=500,
        )


# ============================================================
# 📰 종목 뉴스
# ============================================================
elif page == "📰 종목 뉴스":
    st.markdown("# 📰 종목 관련 뉴스")

    if news_df.empty:
        st.warning(
            "⚠️ 뉴스 데이터가 없습니다. `python scraper.py`를 실행하여 "
            "뉴스를 수집해 주세요."
        )
        st.stop()

    # 종목별 필터
    if '종목명' in news_df.columns:
        stock_names = ['전체'] + sorted(news_df['종목명'].dropna().unique().tolist())
        selected_stock = st.selectbox("종목 선택", stock_names)

        if selected_stock != '전체':
            display_news = news_df[news_df['종목명'] == selected_stock]
        else:
            display_news = news_df
    else:
        display_news = news_df

    # 뉴스 카드형 표시
    for _, row in display_news.iterrows():
        stock_name = row.get('종목명', row.get('종목코드', ''))
        title = row.get('제목', row.get('뉴스제목', ''))
        date = row.get('날짜', row.get('뉴스날짜', row.get('수집시간', '')))
        source = row.get('출처', row.get('뉴스출처', ''))

        st.markdown(
            f"""
            <div class="stock-card">
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#58a6ff; font-weight:700;">{stock_name}</span>
                    <span style="color:#8b949e; font-size:13px;">{date}</span>
                </div>
                <div style="margin-top:8px; color:#e6edf3; font-size:15px;">
                    📰 {title}
                </div>
                <div style="margin-top:4px; color:#6e7681; font-size:12px;">
                    {source}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 📈 분석 신호 (BUY / HOLD / SELL)
# ============================================================
elif page == "📈 분석 신호":
    st.markdown("# 📈 종목별 분석 신호")

    if signals_df.empty:
        st.warning("⚠️ 분석 신호 데이터가 없습니다. `python scraper.py`를 실행해 주세요.")
        st.stop()

    # 종목명 매핑
    if not stock_df.empty and '종목코드' in stock_df.columns:
        name_map = dict(zip(stock_df['종목코드'].astype(str), stock_df['종목명']))
        signals_df['종목명'] = signals_df['ticker'].astype(str).map(name_map).fillna(signals_df['ticker'])
    else:
        signals_df['종목명'] = signals_df['ticker']

    # 신호 요약 카드
    col1, col2, col3, col4 = st.columns(4)
    buy_cnt = (signals_df['signal'] == 'BUY').sum()
    hold_cnt = (signals_df['signal'] == 'HOLD').sum()
    sell_cnt = (signals_df['signal'] == 'SELL').sum()
    with col1:
        st.metric("📊 총 분석", f"{len(signals_df)}개")
    with col2:
        st.metric("🟢 매수(BUY)", f"{buy_cnt}개")
    with col3:
        st.metric("🟡 보유(HOLD)", f"{hold_cnt}개")
    with col4:
        st.metric("🔴 매도(SELL)", f"{sell_cnt}개")

    st.markdown("---")

    # 신호 필터
    signal_filter = st.selectbox("신호 필터", ['전체', 'BUY', 'HOLD', 'SELL'], key='sig_filter')
    display_signals = signals_df if signal_filter == '전체' else signals_df[signals_df['signal'] == signal_filter]

    # 추세 점수 바 차트
    color_map = {'BUY': '#3fb950', 'HOLD': '#d29922', 'SELL': '#f85149'}
    display_signals = display_signals.sort_values('trend_score', ascending=False)

    fig_sig = px.bar(
        display_signals,
        x='종목명',
        y='trend_score',
        color='signal',
        color_discrete_map=color_map,
        title='종목별 추세 점수 및 매매 신호',
        template='plotly_dark',
        text='trend_score',
    )
    fig_sig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
    fig_sig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e6edf3'),
        height=500,
    )
    # 기준선 추가
    fig_sig.add_hline(y=60, line_dash='dash', line_color='#3fb950',
                      annotation_text='BUY 기준(60)', annotation_position='top left')
    fig_sig.add_hline(y=40, line_dash='dash', line_color='#f85149',
                      annotation_text='SELL 기준(40)', annotation_position='bottom left')
    st.plotly_chart(fig_sig, use_container_width=True)

    # 신호 분포 파이 차트
    col_a, col_b = st.columns(2)
    with col_a:
        fig_pie = px.pie(
            signals_df, names='signal',
            color='signal',
            color_discrete_map=color_map,
            title='신호 분포',
            template='plotly_dark',
        )
        fig_pie.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e6edf3'),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.markdown("### 📊 추세 점수 범위 설명")
        st.markdown("""
        | 점수 | 신호 | 의미 |
        |------|------|------|
        | **≥ 60** | 🟢 **BUY** | 등락률 + 거래량 + 외국인/기관 추세 양호 |
        | **40~59** | 🟡 **HOLD** | 동향 혼재, 관망 유지 |
        | **< 40** | 🔴 **SELL** | 하락 추세 또는 외국인/기관 순매도 |
        """)
        st.markdown("""
        **추세 점수 산출:**
        - 등락률 (40%) + 거래량 (20%) + 외국인 (20%) + 기관 (20%)
        """)

    # 신호별 종목 카드
    st.markdown("---")
    st.markdown("### 종목별 신호 카드")
    for _, row in display_signals.iterrows():
        sig = row['signal']
        sig_emoji = '🟢' if sig == 'BUY' else '🟡' if sig == 'HOLD' else '🔴'
        sig_color = color_map[sig]
        st.markdown(
            f"""
            <div class="stock-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:16px; font-weight:700; color:#e6edf3;">
                        {row['종목명']}
                    </span>
                    <span style="background:{sig_color}; color:white; padding:4px 14px;
                           border-radius:20px; font-weight:700; font-size:14px;">
                        {sig_emoji} {sig}
                    </span>
                </div>
                <div style="margin-top:8px;">
                    <span style="color:#8b949e;">추세 점수:</span>
                    <strong style="color:white; font-size:18px; margin-left:4px;">
                        {row['trend_score']:.1f}
                    </strong>
                    <span style="color:#6e7681; margin-left:12px;">
                        기간: {row.get('window', '1D')}
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 📧 뉴스레터 미리보기
# ============================================================
elif page == "📧 뉴스레터":
    st.markdown("# 📧 투자 뉴스레터 미리보기")

    if stock_df.empty:
        st.warning("⚠️ 데이터가 없습니다.")
        st.stop()

    # 성향 선택
    inv_type = st.selectbox(
        "투자 성향 선택",
        ['안정형', '안정추구형', '위험중립형', '적극투자형', '공격투자형'],
        index=2,
        key='newsletter_type'
    )

    type_info = TYPE_DESCRIPTIONS[inv_type]
    st.markdown(
        f"**{type_info['emoji']} {type_info['title']}** — _{type_info['strategy']}_"
    )

    # 뉴스레터 생성
    scored = score_stocks(stock_df, inv_type)
    newsletter = generate_newsletter(
        stock_df=stock_df,
        scored_df=scored,
        signals_df=signals_df,
        investor_type=inv_type,
        user_id=1,
        news_df=news_df,
    )

    st.markdown("---")
    st.markdown(f"### {newsletter['title']}")

    # 뉴스레터 본문 표시
    st.markdown(
        f"""
        <div style="background:rgba(22,27,34,0.9); border:1px solid rgba(255,255,255,0.1);
             border-radius:12px; padding:24px; font-family:monospace;
             white-space:pre-wrap; color:#c9d1d9; line-height:1.8; font-size:14px;">
{newsletter['content']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 다운로드 버튼
    st.download_button(
        label="💾 뉴스레터 다운로드 (.txt)",
        data=newsletter['content'],
        file_name=f"newsletter_{inv_type}_{datetime.now().strftime('%Y%m%d')}.txt",
        mime='text/plain',
    )
