-- Equivalent of the pandas logic in src/p2p_exceptions.py / build_excel.py's
-- Summary KPIs sheet, expressed as SQL over the Parquet case-features file.
-- Run with DuckDB, e.g.:
--   duckdb -c ".read sql/exception_summary.sql"

SELECT
    COUNT(*) AS total_cases,
    ROUND(100.0 * SUM(CASE WHEN has_exception THEN 1 ELSE 0 END) / COUNT(*), 2) AS exception_rate_pct,
    ROUND(SUM(net_worth_eur), 0) AS total_net_worth_eur,
    ROUND(SUM(CASE WHEN has_exception THEN net_worth_eur ELSE 0 END), 0) AS exception_net_worth_eur,
    ROUND(MEDIAN(cycle_time_days), 2) AS median_cycle_time_days,
    ROUND(QUANTILE_CONT(cycle_time_days, 0.90), 2) AS p90_cycle_time_days
FROM read_parquet('../data/processed/case_features.parquet');
