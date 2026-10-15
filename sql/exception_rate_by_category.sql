-- Equivalent of src/build_charts.py's exception-rate-by-category chart, as SQL.
-- Run with DuckDB, e.g.:
--   duckdb -c ".read sql/exception_rate_by_category.sql"

SELECT
    "Item Category",
    COUNT(*) AS case_count,
    SUM(CASE WHEN has_exception THEN 1 ELSE 0 END) AS exception_count,
    ROUND(100.0 * SUM(CASE WHEN has_exception THEN 1 ELSE 0 END) / COUNT(*), 2) AS exception_rate_pct
FROM read_parquet('../data/processed/case_features.parquet')
GROUP BY "Item Category"
ORDER BY exception_rate_pct DESC;
