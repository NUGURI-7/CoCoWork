from app.agents.runtime.adapter import _BINARY_PLACEHOLDER, _without_binary


def test_string_result_untouched():
    assert _without_binary("ok") == "ok"


def test_base64_image_replaced_text_kept():
    content = [{"type": "text", "text": "说明"}, {"type": "image", "base64": "iVBOR", "mime_type": "image/png"}]
    assert _without_binary(content) == [
        {"type": "text", "text": "说明"},
        {"type": "text", "text": _BINARY_PLACEHOLDER},
    ]


def test_data_url_image_replaced_both_shapes():
    content = [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
        {"type": "image_url", "image_url": "data:image/jpeg;base64,BBB"},
        {"type": "image_url", "image_url": {"url": "https://example.com/a.png"}},
    ]
    out = _without_binary(content)
    assert out[0] == out[1] == {"type": "text", "text": _BINARY_PLACEHOLDER}
    assert out[2] == content[2]
