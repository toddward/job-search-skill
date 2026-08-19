import parse_args as pa

def test_free_text_is_scan_query():
    r = pa.parse("AI based jobs in the Reston, VA area")
    assert r["command"] == "scan" and r["query"] == "AI based jobs in the Reston, VA area"

def test_pick_numbers_and_flags():
    r = pa.parse('pick 1,3,5 --from 2026-08-19 --no-tailor --note "emphasize K8s"')
    assert r["command"] == "pick" and r["numbers"] == ["1", "3", "5"]
    assert r["flags"]["from"] == "2026-08-19" and r["flags"]["no-tailor"] is True
    assert r["flags"]["note"] == "emphasize K8s"

def test_select_alias_and_fingerprint_tokens():
    r = pa.parse("select 2 b7f3c1a9")
    assert r["command"] == "pick" and r["numbers"] == ["2", "b7f3c1a9"]

def test_no_with_reason_forms():
    assert pa.parse('no 5 "too sales-heavy"')["reason"] == "too sales-heavy"
    r = pa.parse('no 5,9 --reason "wrong level"')
    assert r["numbers"] == ["5", "9"] and r["reason"] == "wrong level"

def test_snooze_show_unhide_submit_setup():
    assert pa.parse("snooze 7 30d")["flags"]["duration"] == "30d"
    assert pa.parse("show 1")["numbers"] == ["1"]
    assert pa.parse("unhide dis-002 --to soft")["flags"]["to"] == "soft"
    r = pa.parse("submit 1 --i-mean-it")
    assert r["flags"]["i-mean-it"] is True
    assert pa.parse("setup")["command"] == "setup"
    assert pa.parse("")["command"] == "help"

def test_apply_url_and_headless_scan():
    r = pa.parse("apply https://jobs.lever.co/acme/123")
    assert r["command"] == "apply" and r["url"] == "https://jobs.lever.co/acme/123"
    r = pa.parse("scan --headless --max 12 --run 9f1c2d3e")
    assert r["flags"]["headless"] is True and r["flags"]["max"] == "12" and r["flags"]["run"] == "9f1c2d3e"

def test_value_flags_without_values_stay_none_and_do_not_eat_flags():
    r = pa.parse("scan --query --headless")
    assert r["query"] is None and r["flags"]["headless"] is True
    r = pa.parse("no 5 --reason")
    assert r["reason"] is None
    r = pa.parse("AI jobs --query --headless")
    assert r["flags"]["headless"] is True and r["query"] == "AI jobs"

def test_cli_main_preserves_quoted_args(capsys):
    pa.main(["no", "5", "wrong level"])
    import json
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "wrong level" and out["numbers"] == ["5"]
