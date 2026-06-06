# 直连多模态用户资产理解 E2E 清单

## 前置

- 配置 Model Gateway `videoUnderstanding` provider（baseUrl、model、API key）
- 全局开关 `directMultimodalAnalysisEnabled` 为开启
- 至少 1 个已分析样例 + 已保存 Brief

## 用例

1. **直连路由**
   - 上传 brief + 图片/视频，触发生成
   - 检查 `generations/{id}/asset-inventory.json` 含 `assetUnderstandingRoute=direct_multimodal`

2. **带货 brief + 混合素材**
   - contentCategory=product_commerce，上传产品视频 + 图片
   - candidateMoments 与 extractedFacts 语义自洽（含 visualTags / key_message）

3. **科普 brief**
   - 无 productName，填写 keyPoints + creativeGoal
   - 生成成功，facts 含 `key_message` 或 `goal`

4. **文案素材**
   - 上传 `.txt` 文案 + 可选视频
   - inventory 中体现文案内容（facts 或 moments）

5. **Legacy 降级**
   - 关闭 `directMultimodalAnalysisEnabled` 或未配置 videoUnderstanding
   - `assetUnderstandingRoute=legacy`，schema 仍 valid

6. **Fail-fast**
   - 故意配置错误 API key，直连调用失败
   - 任务 stage=analyzing_assets failed，error code=`direct_multimodal_asset_failed`
   - **不应** silent 回退 legacy

7. **分批合并（可选）**
   - 上传超过 `VIDEOMAKER_ASSET_UNDERSTANDING_MAX_MEDIA_COUNT` 个视频
   - `assetUnderstandingRoute=direct_multimodal_batched`，合并后 moments/facts 完整

## Brief v2 UI

8. 切换内容类型（科普 / Vlog / 带货）时字段标签随之变化
9. 保存 brief 后刷新页面，v2 字段正确回显
