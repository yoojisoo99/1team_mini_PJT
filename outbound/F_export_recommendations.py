from common import export_table_to_json

ENGINE_URL = "mysql+pymysql://test:test@25.4.53.12:3306/stock_db?charset=utf8mb4"

TABLE_NAME = "recommendations"
ROOT_KEY = "recommendations"
OUTPUT_PATH = "out_data/recommendations_export.json"

COLUMNS = ["user_id", "ticker", "as_of", "score", "reason"]


def main():
    rows = export_table_to_json(
        engine_url=ENGINE_URL,
        table_name=TABLE_NAME,
        root_key=ROOT_KEY,
        output_path=OUTPUT_PATH,
        columns=COLUMNS,
    )
    print(f"[Success] recommendations export completed: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()