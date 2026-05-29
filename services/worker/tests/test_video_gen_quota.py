from app.runtime.video_gen_quota import VideoGenQuota


def test_consume_allows_up_to_max_calls() -> None:
    quota = VideoGenQuota(max_calls=1)
    assert quota.consume() is True
    assert quota.used == 1
    assert quota.consume() is False
    assert quota.used == 1


def test_from_checkpoint_restores_used() -> None:
    quota = VideoGenQuota.from_checkpoint({"used": 1, "maxCalls": 1})
    assert quota.used == 1
    assert quota.consume() is False


def test_to_checkpoint_round_trip() -> None:
    quota = VideoGenQuota(max_calls=2)
    quota.consume()
    payload = quota.to_checkpoint()
    restored = VideoGenQuota.from_checkpoint(payload)
    assert restored.used == 1
    assert restored.max_calls == 2


def test_has_video_quota_reflects_remaining() -> None:
    quota = VideoGenQuota(max_calls=1, used=1)
    assert quota.remaining == 0
    assert quota.has_video_quota() is False
