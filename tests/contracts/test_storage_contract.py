"""Storage seam contract (REQ-02) — every implementation must pass this suite."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest

from academy.adapters.storage import StorageAdapter
from host_stub.storage import InMemoryStorage

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")

KEY = f"org/{ORG}/media/6f0a1c4e-8f11-4b6d-9d0e-2a3b4c5d6e7f/original.mp4"
SEGMENT = f"org/{ORG}/media/6f0a1c4e-8f11-4b6d-9d0e-2a3b4c5d6e7f/hls/360p/seg-0.ts"
FOREIGN_KEY = f"org/{OTHER_ORG}/media/6f0a1c4e-8f11-4b6d-9d0e-2a3b4c5d6e7f/original.mp4"

IMPLEMENTATIONS: dict[str, Callable[[], StorageAdapter]] = {
    "host_stub.InMemoryStorage": InMemoryStorage,
}


@pytest.fixture(params=list(IMPLEMENTATIONS.values()), ids=list(IMPLEMENTATIONS))
def adapter(request: pytest.FixtureRequest) -> StorageAdapter:
    return request.param()


def test_a_missing_object_has_no_stat(adapter: StorageAdapter) -> None:
    assert adapter.stat(KEY) is None


def test_stat_reports_what_was_stored(adapter: StorageAdapter) -> None:
    _store(adapter, KEY, b"0123456789", content_type="video/mp4")

    stat = adapter.stat(KEY)

    assert stat is not None
    assert stat.key == KEY
    assert stat.size_bytes == 10
    assert stat.content_type == "video/mp4"


def test_presigned_urls_name_the_object_and_its_lifetime(adapter: StorageAdapter) -> None:
    put_url = adapter.presign_put(
        KEY, content_type="video/mp4", max_bytes=2 * 1024 * 1024 * 1024, ttl_seconds=900
    )
    get_url = adapter.presign_get(SEGMENT, ttl_seconds=300)

    assert KEY in put_url
    assert "900" in put_url
    assert SEGMENT in get_url
    assert "300" in get_url
    assert put_url != get_url


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/" + KEY,
        KEY + "/",
        f"org/{ORG}/media/../other/original.mp4",
        f"org/{ORG}/media/6f0a1c4e-8f11-4b6d-9d0e-2a3b4c5d6e7f//original.mp4",
        f"org/{ORG}/original.mp4",
        "media/original.mp4",
        FOREIGN_KEY.replace("media", "média"),
    ],
)
def test_keys_outside_the_media_tree_are_refused(adapter: StorageAdapter, key: str) -> None:
    with pytest.raises(ValueError):
        adapter.presign_put(key, content_type="video/mp4", max_bytes=1024, ttl_seconds=900)


@pytest.mark.parametrize("ttl", [0, -1])
def test_a_non_positive_lifetime_is_refused(adapter: StorageAdapter, ttl: int) -> None:
    with pytest.raises(ValueError):
        adapter.presign_get(KEY, ttl_seconds=ttl)
    with pytest.raises(ValueError):
        adapter.presign_put(KEY, content_type="video/mp4", max_bytes=1024, ttl_seconds=ttl)


def test_a_non_positive_size_bound_is_refused(adapter: StorageAdapter) -> None:
    with pytest.raises(ValueError):
        adapter.presign_put(KEY, content_type="video/mp4", max_bytes=0, ttl_seconds=900)


def test_delete_prefix_removes_only_that_asset(adapter: StorageAdapter) -> None:
    asset = KEY.rsplit("/", 1)[0] + "/"
    _store(adapter, KEY, b"original", content_type="video/mp4")
    _store(adapter, SEGMENT, b"segment", content_type="video/mp2t")
    neighbour = asset.replace("6f0a1c4e", "7b1a2d5f") + "original.mp4"
    _store(adapter, neighbour, b"neighbour", content_type="video/mp4")

    removed = adapter.delete_prefix(asset)

    assert removed == 2
    assert adapter.stat(KEY) is None
    assert adapter.stat(SEGMENT) is None
    assert adapter.stat(neighbour) is not None


def test_delete_prefix_requires_a_directory_boundary(adapter: StorageAdapter) -> None:
    _store(adapter, KEY, b"original", content_type="video/mp4")

    with pytest.raises(ValueError):
        adapter.delete_prefix(KEY)


def test_delete_prefix_refuses_the_media_root(adapter: StorageAdapter) -> None:
    with pytest.raises(ValueError):
        adapter.delete_prefix(f"org/{ORG}/media/")


def _store(adapter: StorageAdapter, key: str, data: bytes, *, content_type: str) -> None:
    """Write directly when the implementation offers the test hook; otherwise presign and PUT."""
    put = getattr(adapter, "put", None)
    if put is not None:
        put(key, data, content_type=content_type)
        return
    raise AssertionError("the contract fixture must seed objects through the implementation")
