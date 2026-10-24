from collector.import_pipeline import records_from_csv


def test_csv_import_normalizes_and_reports_duplicates():
    csv_text = """full_name,country,role,email,phone,certificates,languages,eu_citizen,availability,rate
Jan Kowalski,PL,Welder,jan@example.com,+48111111111,135;136,EN,yes,AVAILABLE NOW,20
Jan Kowalski,PL,welding,JAN@example.com,,141,PL,true,OPEN TO OFFERS,21
Bad Row,PL,,,,,,,UNKNOWN,
"""
    records, report = records_from_csv(csv_text, source="licensed-export")
    assert report.total_rows == 3
    assert report.accepted_rows == 2
    assert report.rejected_rows == 1
    assert report.duplicates_removed == 1
    assert len(records) == 1
    assert records[0].role == "welder"
    assert set(records[0].certificates) == {"135", "136", "141"}
