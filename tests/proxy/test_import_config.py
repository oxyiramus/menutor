"""Check that both Nginx hops allow multipart overhead with a default-size file."""

import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "filename,location", [("nginx.conf", "/api/"), ("host-nginx.conf.example", "/")]
)
def test_import_transport_allows_multipart_overhead(filename, location):
    config = Path(__file__).resolve().parents[2] / ".docker" / "prod" / filename
    block = re.search(rf"location\s+{location}\s*\{{([^}}]+)\}}", config.read_text())
    assert block is not None
    limit = re.search(r"client_max_body_size\s+(\d+)m;", block[1])
    assert limit is not None
    assert int(limit[1]) >= 2
