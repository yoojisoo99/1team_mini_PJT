# analyzer 호출해서 user별 newsletter 생성

from analyzer import score_stocks, generate_newsletter

def build_newsletter_for_user(stock_df, news_df, signals_df, investor_type: str, user_id):
    """
    investor_type(type_name)에 맞춰 newsletter dict 생성
    """
    scored_df = score_stocks(stock_df, investor_type)
    newsletter = generate_newsletter(
        stock_df=stock_df,
        scored_df=scored_df,
        signals_df=signals_df,
        investor_type=investor_type,
        user_id=user_id,
        news_df=news_df,
    )
    return newsletter