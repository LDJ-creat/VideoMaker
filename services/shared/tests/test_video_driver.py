from model_gateway.video_driver import (
    DEFAULT_DASHSCOPE_I2V_MODEL,
    DEFAULT_DASHSCOPE_T2V_MODEL,
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
