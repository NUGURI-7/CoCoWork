"""段内插图签直链：meta → [{index, url}]，命中结果按段 id 回填。不连存储、不连库。"""
from uuid import uuid4

import pytest

from app.schemas.knowledge import RetrievalHit
from app.services.knowledge import figure_urls


class _FakeStorage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def generate_download_url(self, key: str, expires: int = 3600, **_) -> str:
        self.calls.append((key, expires))
        return f"https://signed.example/{key}"


@pytest.fixture
def fake_storage(monkeypatch) -> _FakeStorage:
    fake = _FakeStorage()
    monkeypatch.setattr(figure_urls, "storage", fake)
    return fake


async def test_sign_figures_sorted_by_index(fake_storage):
    meta = {"page": 1, "figures": [{"index": 2, "key": "k/2.png"}, {"index": 1, "key": "k/1.png"}]}

    figures = await figure_urls.sign_figures(meta)

    assert [(f.index, f.url) for f in figures] == [
        (1, "https://signed.example/k/1.png"),
        (2, "https://signed.example/k/2.png"),
    ]
    assert {expires for _, expires in fake_storage.calls} == {figure_urls.FIGURE_URL_EXPIRES}


async def test_sign_figures_without_figures(fake_storage):
    assert await figure_urls.sign_figures({"page": 3}) == []
    assert fake_storage.calls == []


def _hit(paragraph_id) -> RetrievalHit:
    return RetrievalHit(
        paragraph_id=paragraph_id, document_id=uuid4(), doc_name="d.pdf",
        content="正文", chunk_text="正文", score=0.9,
    )


async def test_attach_hit_figures_by_paragraph_id(fake_storage, monkeypatch):
    with_fig, without_fig, missing = uuid4(), uuid4(), uuid4()
    rows = [
        {"id": with_fig, "meta": {"figures": [{"index": 1, "key": "k/1.png"}]}},
        {"id": without_fig, "meta": {"page": 2}},
    ]
    queried: list = []

    class _QS:
        async def values(self, *fields):
            return rows

    def _filter(**kwargs):
        queried.append(kwargs["id__in"])
        return _QS()

    monkeypatch.setattr(figure_urls.Paragraph, "filter", _filter)
    hits = [_hit(with_fig), _hit(without_fig), _hit(missing)]

    await figure_urls.attach_hit_figures(hits)

    assert len(queried) == 1  # 一次查询取回全部
    assert [f.index for f in hits[0].figures] == [1]
    assert hits[1].figures == []
    assert hits[2].figures == []  # 查不到 meta 当无图，不报错


async def test_attach_hit_figures_empty_skips_query(monkeypatch):
    def _filter(**_):
        raise AssertionError("空命中不该查库")

    monkeypatch.setattr(figure_urls.Paragraph, "filter", _filter)

    await figure_urls.attach_hit_figures([])


async def test_sign_paragraph_figures_keys_and_owner_filter(fake_storage, monkeypatch):
    """键 = figure_ref(段 id, 编号)；查询条件里必须带上「库是本人建的」。"""
    pid = uuid4()
    user = object()
    rows = [{"id": pid, "meta": {"figures": [{"index": 1, "key": "k/1.png"}, {"index": 2, "key": "k/2.png"}]}}]
    seen: dict = {}

    class _QS:
        async def values(self, *fields):
            return rows

    def _filter(**kwargs):
        seen.update(kwargs)
        return _QS()

    monkeypatch.setattr(figure_urls.Paragraph, "filter", _filter)

    urls = await figure_urls.sign_paragraph_figures(user, [pid])

    assert seen["knowledge_base__created_by"] is user
    assert urls == {
        figure_urls.figure_ref(pid, 1): "https://signed.example/k/1.png",
        figure_urls.figure_ref(pid, 2): "https://signed.example/k/2.png",
    }


async def test_sign_paragraph_figures_empty_skips_query(monkeypatch):
    def _filter(**_):
        raise AssertionError("空列表不该查库")

    monkeypatch.setattr(figure_urls.Paragraph, "filter", _filter)

    assert await figure_urls.sign_paragraph_figures(object(), []) == {}
