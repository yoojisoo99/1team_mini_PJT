from common import export_table_to_json

ENGINE_URL = "mysql+pymysql://test:test@25.4.53.12:3306/stock_db?charset=utf8mb4"

TABLE_NAME = "stocks"
ROOT_KEY = "stocks"
OUTPUT_PATH = "out_data/stocks_export.json"

COLUMNS = ["ticker", "name", "market","total_value"]

def main():
    rows = export_table_to_json(
        engine_url=ENGINE_URL,
        table_name=TABLE_NAME,
        root_key=ROOT_KEY,
        output_path=OUTPUT_PATH,
        columns=COLUMNS
    )
    print(f"✅ stocks export 완료: {OUTPUT_PATH} (rows={rows})")

if __name__ == "__main__":
    main()