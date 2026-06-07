from __future__ import annotations

from app.stock.stock_query_builder import build_deterministic_stock_query


def test_build_deterministic_stock_query_strips_product_name() -> None:
    payload = build_deterministic_stock_query(
        slot={
            "id": "slot-usage",
            "role": "usage_scene",
            "scriptIntent": "展示 SuperWidget 在厨房的使用场景",
        },
        storyboard=[
            {
                "slotId": "slot-usage",
                "visual": "年轻人在厨房使用 SuperWidget",
                "script": "每天清晨，从一杯好咖啡开始",
            }
        ],
        gap_reason="缺少使用场景素材",
        brief={"productName": "SuperWidget", "topic": "智能咖啡机", "sellingPoints": []},
    )
    assert "superwidget" not in payload["primaryQuery"].lower()
    assert payload["locale"] == "en"
    assert payload["preferVideo"] is True
