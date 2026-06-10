# 反 AI 视觉指纹

LLM 生成网页/动效时的共有「审美默认值」。**默认禁止**；仅当 `finishIntent`、scene 角色或用户指令明确要求时，才可例外并需在脑中注明理由。

## 硬禁止（默认）

| 指纹 | 典型表现 | 替代 |
|------|----------|------|
| 紫粉 / 蓝紫对角渐变底 | `linear-gradient(135deg, #667eea, #764ba2)` 类 | solid `--vm-bg` + 可选单点 `radial-gradient` accent glow（opacity ≤ 0.12） |
| 圆角卡片 + 彩色左边框 | `border-left: 4px solid` + `border-radius: 12px` + 白底半透明 | 发丝分割线 `.rule`、左对齐大字层级、或 lower-third 条带（无左边框） |
| 渐变文字标题 | `background-clip: text` + 彩虹渐变 | solid `--vm-fg` 或单色 accent 下划线 / 标记线 |
| 药丸渐变按钮 | 大圆角 CTA + 双色渐变 | 文字链 + 细边框矩形，或 registry 字幕样式 |
| emoji 当图标 | 📈🚀✨ 列表前缀 | 无图标、细线符号、或 SVG 几何 |
| 假数据 / 假 logo | 「10万+用户」、随机品牌名 | 用文案真实信息；缺素材用 neutral placeholder 文案 |
| 全场同一种入场 | 每元素 `opacity:0→1` + `blur` | 见 MOTION-BY-CONTENT：按内容关系换动作 |
| 持续呼吸光晕 | 全屏 pulse / 闪烁装饰 | 最多 1~2 个慢速 ambient（scale 1↔1.03），不抢主信息 |
| 右下角 mono 角标 | 每屏 `01/05` 装饰 | 去掉；信息放进主标题或字幕轨 |

## 颜色红线

以下 hex **不得**作为背景主色或大面积渐变端点（小面积 accent 标点除外，且需符合 bible）：

- `#7c3aed` `#8b5cf6` `#a855f7` `#6366f1` `#667eea` `#764ba2`
- 霓虹青紫组合（cyan + magenta 双描边）

若品牌色本身是紫色：用 **单色铺底 + 低饱和**，禁止对角渐变。

## 允许但需理由

- **真实产品 UI mock**：卡片网格、侧栏 — 须像真实界面，非装饰性信息卡
- **居中庄严收束**：片尾单句 slogan 居中
- **高转化 variant 的「丰富包装」**：仍禁止左边框卡片；用角标、lower third、对比行

## 缺素材时

承认缺失 — placeholder 卡片写「配图 · 16:9」类中性文案。**不要** emoji、无关 stock 描述、编造数字。

## 与 `visualStyleBible.avoid` 的关系

payload 中 `avoid` 数组与上表**叠加生效**。交卷前扫描 `styles` + `bodyHtml` 是否仍含禁止模式。
