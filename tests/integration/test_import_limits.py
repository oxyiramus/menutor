import json

import pytest

from tests.integration.api_isolation_helpers import request_ok
from tests.integration.test_derived_data_isolation import import_rows


@pytest.mark.parametrize("fmt", ["csv", "json"])
@pytest.mark.parametrize("configured", [False, True])
def test_import_record_limit(isolation_users, monkeypatch, fmt, configured):
    client, (alice, _) = isolation_users
    limit = 3 if configured else 1000
    if configured:
        monkeypatch.setenv("IMPORT_MAX_RECORDS", str(limit))
    else:
        monkeypatch.delenv("IMPORT_MAX_RECORDS", raising=False)

    rows = [
        dict(alice["bodies"]["products"], name=f"Imported {index}")
        for index in range(limit + 1)
    ]
    before = request_ok(client, "GET", "products", alice["headers"])
    rejected = import_rows(client, alice, "products", fmt, rows)
    assert rejected.status_code == 413
    assert request_ok(client, "GET", "products", alice["headers"]) == before

    accepted = import_rows(client, alice, "products", fmt, rows[:-1])
    assert accepted.status_code == 200
    assert accepted.json()["created"] == limit


@pytest.mark.parametrize("fmt", ["csv", "json"])
@pytest.mark.parametrize("configured", [False, True])
def test_import_file_limit(isolation_users, monkeypatch, fmt, configured):
    client, (alice, _) = isolation_users
    limit = 512 if configured else 1048576
    if configured:
        monkeypatch.setenv("IMPORT_MAX_FILE_BYTES", str(limit))
    else:
        monkeypatch.delenv("IMPORT_MAX_FILE_BYTES", raising=False)

    row = dict(alice["bodies"]["products"], name="Imported")
    if fmt == "json":
        data = json.dumps([row]).encode().ljust(limit)
    else:
        data = (",".join(row) + "\n" + ",".join(map(str, row.values())) + "\n").encode()
        data = data.ljust(limit, b"\n")

    def upload(payload, length_header):
        start = (
            f'--upload\r\nContent-Disposition: form-data; name="file"; '
            f'filename="upload.{fmt}"\r\n\r\n'
        ).encode()
        return client.post(
            f"/api/products/import/{fmt}",
            headers={
                **alice["headers"],
                "Content-Type": "multipart/form-data; boundary=upload",
                **length_header,
            },
            content=iter((start, payload, b"\r\n--upload--\r\n")),
        )

    assert len(data) == limit
    before = request_ok(client, "GET", "products", alice["headers"])
    for headers in ({}, {"Content-Length": "1"}):
        assert upload(data + b"\n", headers).status_code == 413
        assert request_ok(client, "GET", "products", alice["headers"]) == before
    accepted = upload(data, {})
    assert accepted.status_code == 200
    assert accepted.json()["created"] == 1
