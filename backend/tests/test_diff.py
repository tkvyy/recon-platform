from app.engine.diff import diff_scans


def asset(host, **kw):
    base = {"hostname": host, "ips": ["1.1.1.1"], "cname": [], "http_status": 200,
            "title": "T", "redirect_url": None, "tech_stack": ["nginx"]}
    base.update(kw)
    return base


def test_added_and_removed():
    d = diff_scans([asset("a.x.com"), asset("b.x.com")], [asset("b.x.com"), asset("c.x.com")])
    assert d["added"] == ["c.x.com"]
    assert d["removed"] == ["a.x.com"]
    assert d["unchanged"] == 1


def test_changed_fields_reported():
    old = [asset("a.x.com")]
    new = [asset("a.x.com", http_status=403, ips=["2.2.2.2"])]
    d = diff_scans(old, new)
    assert d["changed"][0]["hostname"] == "a.x.com"
    assert d["changed"][0]["changes"]["http_status"] == {"old": 200, "new": 403}
    assert d["changed"][0]["changes"]["ips"] == {"old": ["1.1.1.1"], "new": ["2.2.2.2"]}


def test_list_order_does_not_count_as_change():
    old = [asset("a.x.com", ips=["1.1.1.1", "2.2.2.2"])]
    new = [asset("a.x.com", ips=["2.2.2.2", "1.1.1.1"])]
    d = diff_scans(old, new)
    assert d["changed"] == [] and d["unchanged"] == 1


def test_identical_scans_have_no_differences():
    d = diff_scans([asset("a.x.com")], [asset("a.x.com")])
    assert d == {"added": [], "removed": [], "changed": [], "unchanged": 1}
