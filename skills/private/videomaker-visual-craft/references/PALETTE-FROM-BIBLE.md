# visualStyleBible → CSS 变量

将 payload 中的 **`visualStyleBible`** 落成槽位内可执行的 `--vm-*` token。每个 generation **一套变量**，槽位间一致。

## 必填映射步骤

1. 读 `summary` / `palette` / `lighting` / `mood` / **`avoid`**
2. 在 `composition.styles` 最顶部写 `:root { --vm-bg; --vm-fg; --vm-accent; --vm-muted; }`
3. 槽位内 **只用** `var(--vm-*)` 与透明度衍生 — 禁止逐元素发明新 hex

## palette 词 → 起点色（示例）

从 `palette` 数组选 **1 个主 accent**，其余作辅助语义，不要混用多套 accent：

| 词感 | --vm-bg | --vm-fg | --vm-accent | --vm-muted |
|------|---------|---------|-------------|------------|
| 暖白编辑 / 生活 | `#f5f0e8` | `#1a1a1a` | `#c45c3e` | `#6b6560` |
| 墨绿文献 / 自然 | `#f4f1ea` | `#1c2e26` | `#2d6a4f` | `#5c6b63` |
| 电蓝 B2B / 科技 | `#f7f8fa` | `#0f172a` | `#2563eb` | `#64748b` |
| 深色电影 / 安全 | `#121110` | `#f2ece4` | `#e8a769` | `#9a928a` |
| 纸媒 / 报刊 | `#faf8f4` | `#111111` | `#b91c1c` | `#525252` |

**不要用** palette 词推成紫粉渐变。若 bible 写「科技感」→ 优先电蓝/墨灰，非霓虹紫。

## lighting → 对比

| lighting 关键词 | 调整 |
|-----------------|------|
| 自然光 / 柔阴影 | bg 略暖，fg 非纯黑 `#111` |
| 高对比 / 夜景 | bg 更深，fg 提高，accent 饱和度克制 |
| 暖色室内 | bg 奶油色，避免冷灰 |

## mood → 动效气质

| mood | GSAP 气质 |
|------|-----------|
| 电影感慢 | 较长 duration，`power1.out` |
| 利落促销 | 较短，`power2.out`，stagger 紧 |
| 安静可信 | 少位移，多 opacity + 细线 |

## brandColors

`brandColors` 可覆盖 **accent** 用于 logo/品牌条，须与 `--vm-bg` 有足够对比；不要另起一套背景渐变。

## avoid 强制执行

`visualStyleBible.avoid` 与 ANTI-AI-FINGERPRINTS **同时生效**。即使 palette 含「紫」，若 avoid 含「紫粉渐变」，仍用单色或换色相。

## 示例 styles 头

```css
:root {
  --vm-bg: #f5f0e8;
  --vm-fg: #1a1a1a;
  --vm-accent: #c45c3e;
  --vm-muted: #6b6560;
}
#root {
  background: var(--vm-bg);
  color: var(--vm-fg);
  font-family: system-ui, "Noto Sans SC", sans-serif;
}
```
