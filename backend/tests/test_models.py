from sqlalchemy import inspect

EXPECTED_TABLES = {
    "users",
    "clients",
    "ad_data_uploads",
    "analysis_runs",
    "waste_reports",
    "segment_metrics",
    "recommendations",
    "invoices",
    "payment_methods",
    "payments",
    "audit_log",
}


def test_all_tables_from_design_doc_exist(session):
    names = set(inspect(session.get_bind()).get_table_names())
    assert EXPECTED_TABLES <= names, EXPECTED_TABLES - names
