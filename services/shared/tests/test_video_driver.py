from model_gateway.video_driver import (
    DEFAULT_DASHSCOPE_I2V_MODEL,
    DEFAULT_DASHSCOPE_T2V_MODEL,
    DEFAULT_SEEDDANCE_MODEL,
    map_seeddance_duration,
    map_seeddance_ratio,
    map_seeddance_resolution,
    normalize_video_model,
    normalize_wan_model_for_mode,
    resolve_effective_video_driver,
)


def test_dashscope_generic_job_resolves_to_wan() -> None:
    driver = resolve_effective_video_driver(
        "generic_job",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    assert driver == "dashscope_wan"


def test_non_dashscope_keeps_generic_job() -> None:
    driver = resolve_effective_video_driver(
        "generic_job",
        "https://api.example.com/v1",
    )
    assert driver == "generic_job"


def test_normalize_video_model_rejects_image_model_on_dashscope() -> None:
    model = normalize_video_model(
        "wan2.7-image-pro",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    assert model == "wan2.7-t2v"


def test_normalize_video_model_migrates_legacy_wan21() -> None:
    model = normalize_video_model(
        "wan2.1-t2v-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    assert model == "wan2.7-t2v"


def test_normalize_wan_model_for_mode_maps_r2v_to_t2v_without_reference() -> None:
    assert (
        normalize_wan_model_for_mode("wan2.7-r2v", mode="t2v")
        == DEFAULT_DASHSCOPE_T2V_MODEL
    )


def test_normalize_wan_model_for_mode_maps_r2v_to_i2v_with_reference_image() -> None:
    assert (
        normalize_wan_model_for_mode("wan2.7-r2v", mode="i2v")
        == DEFAULT_DASHSCOPE_I2V_MODEL
    )


def test_ark_generic_job_resolves_to_seeddance() -> None:
    driver = resolve_effective_video_driver(
        "generic_job",
        "https://ark.cn-beijing.volces.com/api/v3",
    )
    assert driver == "volcengine_seeddance"


def test_explicit_volcengine_seeddance_driver() -> None:
    driver = resolve_effective_video_driver(
        "volcengine_seeddance",
        "https://api.example.com/v1",
    )
    assert driver == "volcengine_seeddance"


def test_normalize_video_model_on_ark_host_maps_wan_to_seeddance() -> None:
    model = normalize_video_model(
        "wan2.7-t2v",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    assert model == DEFAULT_SEEDDANCE_MODEL


def test_normalize_video_model_on_ark_host_keeps_seeddance_model() -> None:
    model = normalize_video_model(
        "doubao-seedance-2-0-fast-260128",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    assert model == "doubao-seedance-2-0-fast-260128"


def test_map_seeddance_duration_clamps_to_official_range() -> None:
    assert map_seeddance_duration(3) == 4
    assert map_seeddance_duration(5.1) == 6
    assert map_seeddance_duration(20) == 15


def test_map_seeddance_resolution_lowercases_tier() -> None:
    assert map_seeddance_resolution("720P") == "720p"
    assert map_seeddance_resolution("1080P") == "1080p"


def test_map_seeddance_ratio_passes_known_values() -> None:
    assert map_seeddance_ratio("9:16") == "9:16"
    assert map_seeddance_ratio("unknown") == "16:9"
