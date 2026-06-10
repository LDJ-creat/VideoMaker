# 内容驱动动效（GSAP 槽位版）

先问：**这一槽画面在演什么？** 再选 GSAP 手段。禁止「不知道演什么就先 fade-in」。

## 纪律

- 使用 shell 注入的 `tl` — 禁止 `const tl = gsap.timeline()`
- 动画在 `slotTiming.durationSec` 内完成，末帧 **hold** 到槽位结束
- 单槽内 **主导动作至少 2 种**（如 scale + y，或 stagger + opacity）
- 避免所有元素同一 duration/ease

## 关系 → 动作

| 内容关系 | 推荐 `timelineScript` | 避免 |
|----------|----------------------|------|
| 金句/钩子 | 主句 `from` y+12 + opacity；副标延迟 0.15s | 纯 blur-in |
| 数字冲击 | scale 0.6→1 + 可选数字步进；accent 线 `scaleX` | 无意义的旋转 |
| 对比/A vs B | 左右 `from` x 或 wipe 遮罩 | 两卡相同 fade |
| 列表 2–3 项 | `stagger` 0.12–0.2s，前项降 opacity 保留上下文 | 一项一个槽却一次全出 |
| 产品/底片 | 轻 ken-burns `scale` 1→1.08；overlay 后入 | 全屏闪白 |
| CTA/收束 | 主文案 + 细下划线 draw；hold 1s+ | 弹跳药丸按钮 |

## 时长分配（示意）

设 `D = slotTiming.durationSec`：

- 入场：约 25–40% 的 D（短槽偏上限）
- 阅读 hold：约 40–55%
- 可选尾动效：≤ 15%

`D < 2s` 时只做 1 个主入场 + hold，不要复杂序列。

## 与 variant `motionTempo`

| motionTempo | 调整 |
|-------------|------|
| fast | 缩短 stagger、snappier ease（`power2.out`） |
| medium | 略长 hold，ease 偏 `power1` |

## 持续微动

最多 **1 个** ambient（如背景 glow `scale` 1↔1.03，周期 ≥ 3s）。不要全屏呼吸闪烁。

## 交卷前

对照 ANTI-AI：若整段只有 `opacity`/`filter:blur` 入场 → 回去补内容语义动效。
