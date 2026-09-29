from pipeline.http_json import _allowed


def test_allow_list_accepts_deepinfra_and_openai():
    assert _allowed("https://api.deepinfra.com/v1/openai/chat/completions")
    assert _allowed("https://api.openai.com/v1/chat/completions")
    assert _allowed("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts")
    assert _allowed("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts")


def test_allow_list_refuses_unknown_hosts():
    assert not _allowed("https://evil.example/v1/chat/completions")
    assert not _allowed("https://example.com/v1")
    assert not _allowed("ftp://api.openai.com/v1")
