# 样例视频结构拆解与沉淀标准

> **文档性质**：第一性原理标准，定义「从爆款样例视频中提取什么、为何提取、如何沉淀为可复用经验」。  
> **适用范围**：相同或相似题材/类型/平台的新视频创作任务中的结构迁移。  
> **边界**：本文不绑定任何现有系统实现、字段名或 pipeline 设计。

---

## 0. 导读：四轨拆解视图

完整标准见 §3–§4；日常讨论、分工与评审时，可先用**四轨视图**建立共同语言。四轨不是替代细维度的简化版，而是**同一套结构的四种读法**，均须落回时间轴并对齐证据。

| 轨道 | 回答什么 | 典型参数化产物 | 对应细维度（§3） |
|------|----------|----------------|------------------|
| **文本轨（逻辑层）** | 论证顺序、Hook、信息密度、CTA | `hookTemplate`、`outlineTimeline`、`ctaMechanism` | §3.2 叙事、§3.4 Verbal |
| **视觉轨（画面层）** | 切镜、B-roll 逻辑、上屏与包装 | `cutRateProfile`、`conceptVisualMap`、`packagingSpec` | §3.5 视觉、§3.6 包装、§3.3 切镜 |
| **听觉轨（氛围层）** | 人声、BGM、音效与情绪起伏 | `voProfile`、`audioEventRules`、`emotionTriggers` | §3.3 节奏/音频、§3.2 情绪基调 |
| **策略轨（迁移层）** | 为何有效、差异化、适用边界 | `differentiationLever`、`successHypothesis`、`transfer` | §3.1 语境、§3.9 迁移、§3.7 槽位 |

**多 Agent / 工作流分工建议**（可选）：文案 Agent 主责文本轨；分镜/素材 Agent 主责视觉轨；音频/后期 Agent 主责听觉轨；策略/质检 Agent 主责策略轨并校验四轨时间对齐。

---

## 1. 目的与边界

### 1.1 我们要解决什么问题

给定一条表现优异的样例视频，目标是：

1. **理解**它为何在目标场景下可能有效（注意力、信任、转化等机制）；
2. **抽象**其可复用的创作结构，而非复制具体内容；
3. **沉淀**为可在新选题、新素材、新时长条件下重新实例化的经验；
4. **支撑**后续生成时的 slot 匹配、素材缺口识别、分镜/口播/包装决策。

### 1.2 交付心智：逆向工程，而非观后感

样例分析的本质是对爆款视频的**逆向工程**：把感性上的「好看、好懂、想下单」拆解为**结构化、参数化、可执行**的生成约束。

**最终交付物不是分析报告，而是「生成约束配置包」**——逻辑上可表现为一份结构化文档（JSON/YAML 等）、一组按轨道组织的 System Prompt 约束，或层 B `VideoStructure` + 若干具名子产物（见 §4.2）。下游生成流只应消费这些约束，而非样例像素或原文。

### 1.3 什么不是目标

| 不做 | 原因 |
|------|------|
| 复制样例的台词、画面、商标、具体产品信息 | 侵权风险；无迁移价值 |
| 只做镜头/切点级别的物理描述 | 缺少「为何这样排」的叙事与转化逻辑 |
| 只输出一条自然语言摘要 | 无法程序化匹配素材、无法验证迁移是否走样 |
| 把样例当成唯一真理 | 结构应标注适用条件、置信度与可替换方案 |

### 1.4 「结构」的操作性定义

**视频结构** = 在特定平台与内容类型约束下，为实现特定传播/转化目标，对**时间、信息、情绪、视觉与包装**进行编排的一套**可参数化模式**。

可迁移的结构至少包含：

- **分段逻辑**：视频由哪些功能段组成，各段承担什么叙事/留存/转化职责；
- **时间预算**：各段占全片的比例或典型时长区间；
- **表达策略**：每段用什么话术机制、什么视觉机制、什么包装机制；
- **约束与反模式**：哪些元素不可省略、哪些写法/画面属于套模板废话；
- **实例化接口**：换选题后，每段应填入什么类型的素材与文案意图。

---

## 2. 第一性原理：拆解时应回答的六个问题

对任何样例，分析产出应能回答：

| # | 问题 | 对应沉淀 |
|---|------|----------|
| Q1 | 这是什么类型的视频？在什么平台语境下有效？ | 类型框架与适用边界 |
| Q2 | 全片讲了一个怎样的「故事/论证链」？ | 宏观叙事架构 |
| Q3 | 时间如何花——快慢、切镜、停顿、高潮在哪？ | 节奏与时间结构 |
| Q4 | 观众在每个阶段看到什么、听到什么、感受到什么？ | 视听与包装层（≈ §0 文本/视觉/听觉三轨） |
| Q5 | 哪些段落是「可替换填充位」，填充规则是什么？ | 结构槽（迁移单元） |
| Q6 | 上述判断依据是什么，有多确定？ | 证据、置信度、质量标记 |

若缺少 Q5，则无法迁移；若缺少 Q6，则无法解释与迭代。

---

## 3. 分析维度体系

以下维度构成完整拆解的「观察坐标系」。§0 四轨是阅读入口；本节是**执行细则**。各维度通过**时间段**对齐，并应产出 §4.2 所列具名子产物（在适用时）。

### 3.1 语境与类型框架（Context）——策略轨

**目的**：限定结构的适用域，避免把「剧情号套路」迁移到「硬广口播」。

应提取：

- **内容类型**：口播带货、测评对比、Vlog 种草、剧情短剧、教程、开箱、混剪、技术科普/干货等；
- **商业意图**：拉新曝光 / 种草心智 / 促进转化 / 品牌认知（可多选，标注主次）；
- **平台与画幅**：如竖屏 9:16、前 3 秒停滑假设、静音观看比例假设；
- **受众与场景**：面向谁、在什么决策阶段观看；
- **题材标签**：品类、价格带、决策复杂度（低客单冲动 vs 高客单理性）；
- **成功假说（`successHypothesis`）**：一句话说明「这条片可能为什么有效」（待验证，非事实）。

**沉淀形式**：类型画像 + 适用条件 + 不适用条件。

---

### 3.2 宏观叙事架构（Narrative Architecture）——文本轨 + 策略轨

**目的**：把握「论证/讲故事的顺序」，这是结构迁移的核心骨架。

应提取：

- **整体叙事模式**：如痛点-方案-证明-促单、结果前置-过程拆解-信任背书、反差-揭秘-清单等；
- **功能分段（Segments）**：每段应用标准角色标注，建议角色集包括：
  - `hook`：停滑 / 建立悬念 / 结果预告
  - `problem`：痛点、共鸣、场景代入
  - `solution`：产品/方法出场
  - `proof`：演示、数据、对比、证言
  - `benefit`：利益点展开
  - `comparison`：竞品或旧方案对比
  - `cta`：行动号召、限时、路径指引
  - `transition`：段间过渡、节奏缓冲
- **每段要素**：
  - 起止时间（或占全片比例）；
  - **脚本意图**（说什么、用什么修辞）；
  - **视觉意图**（看什么、什么景别/运动）；
  - **情绪基调**与**留存作用**（停滑、信任、urgency 等）；
  - **信息增量**：该段相对前段新增了什么认知。
- **全片摘要**：2–4 句中文，描述结构而非内容细节。
- **大纲时间轴（`outlineTimeline`）**：将「引入 → 展开 → 转折/升华 → 总结/CTA」映射为**时间戳节点表**（各阶段起止秒数 + 占全片比例），供 Prompt 约束与 human review 一览。

**注意**：叙事分段（通常 5–12 段）与物理切镜（可能数十镜）是**不同层次**，不可混为一谈。

---

### 3.3 节奏与时间结构（Rhythm & Timing）——三轨交叉

**目的**：迁移时保持「观感相似」，即使总时长变化。

应提取：

- **总时长**与建议伸缩区间（如 25–35s 可线性缩放，hook 不可压缩低于 X 秒）；
- **分段时长占比**（`durationSharePct`）及绝对秒数参考；
- **节奏档位**：全片及分段的 tempo（慢 / 中 / 快 / 混合）；
- **物理切点（Shot boundaries）**：镜头切换时间点、切镜密度、是否与口播/BGM 对齐；
- **切镜参数（`cutRateProfile`）**：如平均镜头时长（秒/镜）、快切段起止区间、opening 窗口内切镜频率；可作为后期切割与分镜脚本的数值约束；
- **叙事节拍点（Beat points）**：情绪或信息转折点（可与切点重合，也可不重合）；
- **语音节奏**：语速（字/分钟或相对档位）、停顿、反问、叠词等高能量片段位置；
- **音频结构**：口播/BGM/原声/静音段分布；BGM 是否驱动切镜；
- **音频事件规则（`audioEventRules`）**：参数化的 IF-THEN 描述，例如「核心金句出现时 → 降低 BGM 音量 + 触发提示音效」；每条规则须含时间锚或触发语义；
- **前 N 秒策略**：专门描述 opening 的信息密度与切镜频率（平台关键窗口）。

**沉淀原则**：beat 偏「叙事/情绪」，shot 偏「物理编辑」；迁移时 beat 优先保形，shot 可随素材重剪。

---

### 3.4 Verbal 层（Script & Voice）——文本轨

**目的**：迁移话术**机制**，不是迁移原句。

应提取：

- **Hook 机制**：反问、数字冲击、结果前置、身份代入、禁忌/损失厌恶等；
- **Hook 句式模板（`hookTemplate`）**：符号化模板，非样例原文。示例：`[身份/场景痛点] + [普遍误区] + [反直觉结论]` 或 `[结果前置] + [如何做到的悬念]`；
- **分段话术模板**：每段的句式模式（非原文），如「第二人称痛点问句 + 15 字内结论」；
- **信息密度结构**：核心论点首次出现的时间点；**干货 vs 润滑剂比例**（`infoLubricantRatio`）——干货（概念、数据、步骤）与润滑剂（案例、比喻、段子、过渡）的时间占比或段落配比（知识类题材尤其重要，见 §3.11）；
- **关键信息锚点**：必须传达的 3–7 个命题（可映射到新选题）；
- **修辞设备**：对比、排比、反讽、权威引用、社会证明等；
- **人称与口吻**：博主/品牌/用户视角；正式/口语/紧迫；
- **口播风格（`voProfile` / VO style）**：语速、能量、persona；供 TTS 选音色或克隆时的参数参考；
- **CTA 模式**：软性引导 vs 硬促单；是否叠加价格/限时/scarcity；
- **CTA 心理机制（`ctaMechanism`）**：如互惠、稀缺、社会证明、损失厌恶等（机制名 + 在样例中的体现方式，非原句）；
- **迁移边界**：
  - `mustMention` 类：新片必须出现的**信息类型**（非原词）；
  - `avoidMention` 类：样例中有但新片应避免的（竞品名、违规表述等）。

---

### 3.5 视觉层（Visual & Scene）——视觉轨

**目的**：定义每段「画面应完成什么任务」，供素材匹配与 AIGC 补全。

应提取：

- **视觉规格（Visual spec）**（按段）：
  - 景别：特写 / 中景 / 全景 / 屏幕录制等；
  - 主体：人脸、产品、Hands-on、场景、字幕卡；
  - 镜头运动：固定、推近、快切、跟拍；
  - 画面密度：低/中/高信息；
  - 色调/氛围。
- **抽象→具象映射（`conceptVisualMap`）**：当口播涉及抽象概念（如「算法」「风口」「效率」）时，画面采用的具象意象；条目形如 `{ "concept": "…", "visualMetaphor": "…", "timeSec": …, "assetHint": "…" }`，供素材库检索或 AIGC prompt 生成；
- **画面-文案关系**：口播主导 vs 画外音+B-roll；是否依赖字幕才能看懂；
- **证据型画面类型**：实测过程、前后对比、使用场景、数据图表、包装特写；
- **文字上屏策略**：关键词条、全字幕、仅 hook 大字、贴纸强调；
- **B-roll 与 A-roll 比例**及切换逻辑；
- **段间视觉连续性**：跳切、匹配剪辑、转场类型。

**迁移时**：输出「视觉意图」与「所需素材类型」，而非要求复现同一 JPG/同一机位。

---

### 3.6 包装与后期（Packaging & Post）——视觉轨

**目的**：很多「爆款感」来自包装节奏，而非仅来自内容。

应提取：

- **包装规范（`packagingSpec`）**：可复用的 UI/字幕规范摘要（如字幕位置、字号档位、强调色、贴纸密度上限）；
- **字幕/ caption 策略**：样式、出现时机、是否逐字跟读；
- **标题卡/花字**：出现段落、停留时长、功能（强调卖点 vs 过渡）；
- **贴纸/箭头/圈画**：是否用于引导视线；
- **转场**：硬切、闪白、缩放、风格化转场及其触发条件；
- **音效**：切镜音效、提示音、环境音；
- **视觉密度曲线**：全片包装元素疏密随时间变化；
- **封面/首帧逻辑**（若可推断）：是否与 hook 共用同一视觉锚点。

---

### 3.7 结构槽（Structure Slots）——迁移的最小单元

**目的**：把叙事段进一步拆成**可匹配用户素材、可检测缺口、可生成补全**的原子位。

每个 slot 应包含：

| 字段语义 | 说明 |
|----------|------|
| `id` | 槽位唯一标识 |
| `segmentId` | 所属叙事段 |
| `role` | 槽位功能角色（如 hook_visual、product_closeup、usage_scene、proof、cta 等） |
| `startSec` / `endSec` 或 `durationSharePct` | 时间范围或占比 |
| `requiredAssetType` | 所需素材类型：实拍视频、图片、生成画面、口播、包装元素等 |
| `visualIntent` | 该槽画面要完成的视觉任务（具体、可执行） |
| `scriptIntent` | 该槽口播/字幕要完成的表达任务（与 visualIntent 语义分离） |
| `importance` | must_have / recommended / optional |
| `constraints` | 时长、景别、是否必须露脸、是否必须含产品等 |
| `migrationTemplate` | 换题后如何实例化（「将样例中的 X 类场景替换为新产品的等效使用场景」） |
| `packagingRequirements` | 该槽依赖的包装元素 |
| `antiPatterns` | 该槽应避免的空洞写法或无效画面 |

**原则**：

- 一槽一职责；避免「一个大槽什么都装」；
- `visualIntent` 与 `scriptIntent` 必须可区分；
- 槽位是**迁移接口**，不是样例内容的索引。

---

### 3.8 证据与可解释性（Evidence & Provenance）

**目的**：让结构「可核对、可审计、可改进」，支撑 UI 展示与 knowledge 晋升。

每条关键结论（尤其是分段边界、hook 机制、proof 类型、CTA 强度）应绑定证据：

| 证据类型 | 典型用途 |
|----------|----------|
| 口播/ASR | 话术机制、关键句、时间范围 |
| 关键画面时刻 | 视觉意图、产品露出、对比画面 |
| 切镜/镜头检测 | 节奏密度、快切段 |
| 音频分析 | BGM drop、静音、语速变化 |
| OCR/上屏文字 | 包装策略、关键词条 |
| 推理标注 | 无直接感知支撑时的 LLM 推断，须降置信度 |

每条证据宜含：`targetId`（指向 segment 或 slot）、`source`、`summary`（含时间锚点）、`confidence`、`excerpt`（如有）。

**禁止**：无时间锚、无依据的模板化空话（如「engaging opening captures viewer attention」）。

---

### 3.9 迁移元数据（Transfer Metadata）——策略轨

**目的**：指导「这条结构怎么用到新任务上」。

应提取：

- **结构族（Structure family）**：可归类的模板名称或标签；
- **差异化杠杆（`differentiationLever`）**：在同类竞品中「最不按套路出牌」的核心变量（如新颖图解、反差人设、极端前 3 秒）；说明**可迁移的结构创新点**，而非样例专属表面元素；
- **情绪触发点（`emotionTriggers`）**：观众可能产生「意外/共鸣/学到」等反应的时间点列表，每项含 `{ "timeSec", "triggerType", "segmentId", "mechanism" }`，用于指导新片情绪曲线设计；
- **可伸缩规则**：哪些段可合并/拆分、最短/最长时长；
- **参数化变量**：选题、卖点数量、证据强度、价格带等对结构的影响；
- **变体提示**：同一结构在高点击 vs 高转化导向下的微调方向；
- **素材需求清单（Material requirements）**：按 slot 汇总所需素材类型与缺口风险；
- **相似题材推荐**：该结构更适用的题材/更不适用的题材；
- **不可迁移元素清单**：样例中与特定品牌/人物/季节绑定的元素。

---

### 3.10 质量与完整度（Analysis Quality）

**目的**：标记分析是否达到「可迁移」门槛。

应产出：

- **locale**：输出语言（如 zh）；
- **warnings**：如 hook 过短、proof 段缺失、证据不足、叙事段重叠、槽位未覆盖全片等；
- **confidence**：全结构置信度；
- **深度档位**：fast / standard / deep 下各维度的覆盖说明；
- **晋升就绪（Promote-ready）**：是否满足写入结构技能库的门禁（见 §6）。

---

### 3.11 知识密集类视频的附加提取项

当内容类型为**技术科普、干货分享、教程、方法论**等知识密集题材时，在 §3 通用项之外，**强烈建议**补齐：

| 附加项 | 说明 |
|--------|------|
| `infoLubricantRatio` | 干货段 vs 润滑段的时间/段落占比 |
| `conceptVisualMap` | 每个抽象概念对应的具象画面（见 §3.5） |
| `outlineTimeline` | 论点引入 / 展开 / 转折 / 收束的时间节点表 |
| 核心论点时间戳 | 首次抛出核心结论的秒数（关系完播与信息密度） |
| 图表/演示槽 | 单独 slot 标注「数据可视化 / 屏幕录制 / 板书」类 must_have |

此类题材的迁移瓶颈常在 **B-roll 与概念可视化**，而非 hook 话术本身；分析深度不足时，应显式写入 `analysisQuality.warnings`。

---

## 4. 标准产出物：应落盘的信息清单

一次完整的样例结构分析，建议落盘为**分层产物**（逻辑上可合并为一份文档或拆为多文件，此处只规定语义）。

### 4.1 层 A：感知事实（Perception Facts）

来自算法/多模态的**低解释**观测，供上层引用，一般不单独作为迁移依据：

- 视频 metadata（时长、分辨率、fps、是否有音轨）；
- 口播转写（带时间戳）；
- 镜头切点列表；
- 音频 profile（有无口播/BGM、onset、语速等）；
- （可选）关键帧或视觉批次摘要；
- 分析路由/深度/警告（过程元数据）。

### 4.2 层 B：结构解释（Video Structure + 具名子产物）

**核心可迁移资产**。主干结构如下，并**在适用题材下**填充 §4.2.1 具名子产物（可内嵌于同一文档，或拆为并列 JSON 片段）。

```text
VideoStructure
├── context                 # §3.1（含 successHypothesis）
├── metadata
├── narrative
│   ├── summary
│   ├── segments[]
│   └── outlineTimeline     # 推荐子产物
├── rhythm                  # shotBoundaries、beatPoints、tempo、cutRateProfile
├── verbal                  # 逻辑聚合（或分散在 narrative/slots 中）
│   ├── hookTemplate
│   ├── infoLubricantRatio  # 知识类推荐
│   ├── voProfile
│   └── ctaMechanism
├── visual
│   └── conceptVisualMap[]  # 推荐子产物
├── audio
│   └── audioEventRules[]   # 推荐子产物
├── packaging               # §3.6（含 packagingSpec）
├── slots[]                 # §3.7
├── evidence[]              # §3.8
├── transfer                # §3.9（含 differentiationLever）
│   └── emotionTriggers[]
├── analysisQuality         # §3.10
└── confidence
```

#### 4.2.1 具名参数化子产物（生成约束配置包）

| 子产物 | 所属轨道 | 用途 |
|--------|----------|------|
| `hookTemplate` | 文本 | Hook Prompt / scriptIntent 约束 |
| `outlineTimeline` | 文本 | 全片大纲时间占比与节点 |
| `infoLubricantRatio` | 文本 | 知识类信息密度与完播结构 |
| `ctaMechanism` | 文本 | CTA 写作与转化策略 |
| `cutRateProfile` | 视觉 | 剪辑节奏、分镜时长 |
| `conceptVisualMap` | 视觉 | 素材检索、AIGC 画面 prompt |
| `packagingSpec` | 视觉 | 字幕/花字/贴纸规范 |
| `voProfile` | 听觉 | TTS 音色与语速参数 |
| `audioEventRules` | 听觉 | 后期混音与音效触发 |
| `emotionTriggers` | 策略 | 情绪曲线与 retention 设计 |
| `differentiationLever` | 策略 | 同类差异化与结构创新点 |

**消费方式**：自动化生成流应优先读取 `slots[]` + `narrative` + `rhythm` 预算，并按轨道引用上表子产物作为**硬约束或软提示**（须在 `transfer` 或 `analysisQuality` 中标注约束强度）。

### 4.3 层 C：可复用经验（Structure Skill / Knowledge）

面向人读与跨项目复用的**压缩表达**（可由层 B 派生）：

- **结构技能说明（Markdown）**：用自然语言教「何时用、怎么用、常见坑」；建议按 §0 四轨组织章节；
- **结构 JSON 快照**：层 B 的权威机器可读版本；
- **条目元数据**：来源样例、品类、标签、晋升时间、适用边界。

层 C 是「经验库」条目；层 B 是单次分析的权威结果。

---

## 5. 信息之间的关系（对齐规则）

1. **时间轴对齐**：`segments`、`slots`、`evidence`、`rhythm.beatPoints`、`emotionTriggers`、`conceptVisualMap` 必须可映射到同一时间线。
2. **segment ⊃ slot**：每个 slot 归属唯一 segment；segment 内可有多个 slot。
3. **rhythm.shotBoundaries ⊥ narrative.segments**：切镜数量可远大于叙事段数；禁止用切镜数代替叙事段数。
4. **visualIntent ≠ scriptIntent**：同一 segment/slot 上两者语义不得高度重复。
5. **evidence → target**：每条证据必须指向 segment 或 slot；segment 至少有一条有效 evidence。
6. **四轨一致**：文本轨 `outlineTimeline` 与视觉轨 `cutRateProfile`、听觉轨 `audioEventRules` 在时间上不得自相矛盾；矛盾须写入 `warnings`。
7. **迁移只读 slots + narrative + rhythm 预算 + 具名子产物**：生成阶段不应依赖样例原始像素或原文。

---

## 6. 质量门槛（Promote-ready 最低标准）

满足以下条件，方可视为「可沉淀为可复用经验」：

| 门槛 | 要求 |
|------|------|
| 叙事完整 | ≥4 个功能段，且含 hook 与 cta（或类型等价段） |
| 时间覆盖 | segments 合计覆盖 ≥85% 全片时长，无明显大空洞 |
| 槽位覆盖 | must_have slots 覆盖 hook、核心卖点展示、证明、cta 四类职责 |
| 意图可执行 | 无「泛泛而谈」的 visual/script intent（过短或黑名单套话） |
| 证据 | 每个 segment 至少 1 条含时间锚的有效 evidence |
| 节奏 | 给出 tempo + beatPoints；物理切点与时长自洽 |
| 迁移 | 至少 3 个 slot 含 migrationTemplate 或等效实例化说明 |
| 边界 | 标明 content-specific 与 transferable 的区分 |
| Hook 可复用 | 存在 `hookTemplate` 或等效的机制+模板描述 |
| 策略可辨识 | 存在 `differentiationLever` 或等效的成功假说+创新点说明 |

**知识密集类（§3.11）附加**：建议存在 `conceptVisualMap`（≥2 条）或 `infoLubricantRatio`；缺失时须在 warnings 中说明。

未达门槛的分析可保留为 draft，但不得作为默认结构绑定到新项目 generation。

---

## 7. 反模式（分析时应避免）

| 反模式 | 表现 | 正确方向 |
|--------|------|----------|
| 内容抄写 | 结构里充满样例原句、品牌名 | 抽象为机制与意图 |
| 切镜=叙事 | 58 个 shot 当成 58 个「结构段」 | 先 narrative，后 rhythm |
| 空洞模板 | hook 写「engaging opening」 | `hookTemplate` + 时间 + evidence |
| 单维分析 | 只有文案或只有镜头表 | 四轨齐全，时间对齐 |
| 无边界迁移 | 不标注适用题材 | 写清适用/不适用条件 |
| 证据缺失 | 分段无任何依据 | 每段至少一条可核对 evidence |
| 槽位膨胀 | 每镜一个 slot | 按功能合并，控制 slot 数量 |
| 观后感式结论 | 只有「很好看、很干货」 | 参数化子产物 + 生成约束 |

---

## 8. 与新生成任务的对接（消费方视角）

下游「结构迁移 / 生成」应仅依赖层 B/C，按以下顺序消费：

1. **类型匹配**：新 brief 与 `context` 是否同族；
2. **结构绑定**：选用 VideoStructure 或 Structure Skill；
3. **策略校准**：读取 `differentiationLever`、`emotionTriggers`，确定变体方向；
4. **Slot 映射**：用户素材 ↔ slots（matched / weak / missing）；`conceptVisualMap` 辅助 weak/missing 的视觉补全；
5. **Gap 规划**：对 missing/weak 槽制定补全策略（实拍/AIGC/包装）；
6. **Master narration / 分镜**：在 `outlineTimeline`、`hookTemplate`、`rhythm` 预算与 `cutRateProfile` 约束下写新稿；
7. **包装与 timeline**：按 `packagingSpec`、`audioEventRules` 与 slot 约束组装；
8. **验收**：对照 `analysisQuality` 与 transfer 规则检查是否走样。

---

## 9. 附录：术语表

| 术语 | 定义 |
|------|------|
| 四轨视图 | 文本 / 视觉 / 听觉 / 策略四种读法，见 §0 |
| 生成约束配置包 | 层 B 及 §4.2.1 子产物的集合，供自动化生成消费 |
| 叙事段（Segment） | 承担单一叙事/转化功能的时间连续区间 |
| 结构槽（Slot） | 可独立匹配素材、生成补全的原子迁移单元 |
| 物理切镜（Shot） | 视觉上的镜头切换，不等于叙事段 |
| 节拍点（Beat） | 信息或情绪上的转折时刻，可与切点重合 |
| hookTemplate | Hook 的符号化句式模板，非样例原文 |
| conceptVisualMap | 抽象概念到具象画面意象的映射表 |
| audioEventRules | 口播/BGM/音效触发的 IF-THEN 规则 |
| emotionTriggers | 观众情绪共鸣点的时间分布 |
| differentiationLever | 相对同类的核心差异化结构变量 |
| 结构技能 | 从单次分析晋升的、带适用边界的可复用经验条目 |
| 迁移 | 在新选题与素材下实例化同一结构模式，而非复制内容 |

---

## 11. 实现映射（p1-v3 schema）

| 标准 §4.2.1 子产物 | `video-structure.json` 字段 |
|-------------------|------------------------------|
| 内容类型 / 平台 / 意图 | `context.contentCategory`, `platformFormat`, `primaryIntent` |
| 成功假设 / 适用边界 | `context.successHypothesis`, `context.applicability` |
| hookTemplate | `verbal.hookTemplate` |
| outlineTimeline | `verbal.outlineTimeline`（coercer 由 segments 派生） |
| ctaMechanism | `verbal.ctaMechanism` |
| conceptVisualMap | `visual.conceptVisualMap` |
| cutRateProfile | `visual.cutRateProfile`（coercer 由 shots 派生） |
| packagingSpec | `visual.packagingSpec` |
| voProfile / audioEventRules | `audio.voProfile`, `audio.audioEventRules` |
| structureFamily / differentiationLever | `transfer.structureFamily`, `transfer.differentiationLever` |
| emotionTriggers | `transfer.emotionTriggers` |
| promote 门禁 | `analysisQuality.promoteReady` + `warnings` |

---

## 10. 文档维护

- **版本**：1.1（2026-06-07）
- **变更摘要（1.0 → 1.1）**：新增 §0 四轨导读、§1.2 交付心智、§4.2.1 具名参数化子产物、§3.11 知识密集类附加项；各维度补充 hookTemplate、conceptVisualMap、audioEventRules 等可执行沉淀形态。
- **状态**：标准草案，作为样例分析产出设计与质量评审的参照基线
- **后续修订**：当新增平台类型（如直播切片、图文转视频）或新的迁移场景时，扩展 §3.1 与 §3.7 的角色/槽位枚举，以及 §4.2.1 子产物表，而非推翻整体框架
