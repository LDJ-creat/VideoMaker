skill 机制本质上是一种**渐进式上下文注入**策略，核心思想是：避免把所有文档一次性塞进 system prompt，而是让 agent 在需要时"按需取阅"。

让我先画一张架构图，再展开讲实现细节。整个机制分三层，下面逐一讲清楚。

---

## 一、为什么需要渐进式披露

直觉上你可能会想把所有 skill 文档全塞进 system prompt。这行不通：

- Token 浪费：每次请求都携带大量无关文档
- 注意力稀释：模型在超长 context 中容易忽略重要内容
- 扩展性差：skill 数量增长后 prompt 会失控

**正确的做法是两级结构**：始终注入"目录"，按需注入"正文"。

---

## 二、第一层：Skill 目录注入 System Prompt

在 system prompt 里注入的不是 skill 的详细内容，而是一个**结构化的 skill 清单**，每条只包含触发判断所需的最少信息：

```xml
<available_skills>
  <skill>
    <name>docx</name>
    <description>
      处理 Word 文档（.docx）的创建、读取、编辑。触发条件：用户提及
      Word 文件、.docx、需要带格式的正式文档输出时。
    </description>
    <location>/mnt/skills/docx/SKILL.md</location>
  </skill>

  <skill>
    <name>pptx</name>
    <description>
      处理演示文稿（.pptx）。任何涉及"幻灯片"、"deck"、"presentations"
      或 .pptx 文件的任务，无论输入还是输出，都应使用此 skill。
    </description>
    <location>/mnt/skills/pptx/SKILL.md</location>
  </skill>
</available_skills>
```

关键设计点：

- `<description>` 写触发条件而非功能列表，让模型能准确判断"何时用"
- `<location>` 给出文件路径，是 agent 后续读取的线索
- 每条 skill 控制在 50 字以内，整个目录不超过 1000 tokens

---

## 三、第二层：Agent 读取 Skill 详细内容

在 system prompt 中加一条指令，要求 agent 在执行任务前必须先读取相关 skill：

```xml
<skill_usage_rule>
Before writing any code, creating any file, or running any command,
first scan <available_skills> and `view` every plausibly-relevant
SKILL.md. This step is mandatory — skills encode environment-specific
constraints that are not in your training data.
</skill_usage_rule>
```

Agent 收到任务后的行为链：

```
用户："帮我做一个 pptx"
  → 扫描 available_skills，匹配 pptx
  → 调用 view("/mnt/skills/pptx/SKILL.md")
  → SKILL.md 内容进入 context window
  → 按其中的约束执行任务
```

`view` 这个工具就是你 agent toolset 里的文件读取工具，不需要额外实现，只要路径可访问即可。

---

## 四、SKILL.md 的内容结构

SKILL.md 是真正的知识载体，应该包含训练数据里没有的**环境特定约束**：

```markdown
# PPTX Skill

## 环境依赖
使用 python-pptx 库（已安装）。
输出路径：/mnt/user-data/outputs/

## 必须的第一步
始终先读取模板文件（如果有）：
view /mnt/user-data/uploads/template.pptx

## 坑点记录
- 不要用 Slide.width 直接赋值，会破坏 aspect ratio
- 中文字体必须显式指定，否则渲染为方块
- 图片插入后需要 save() 才会写入磁盘

## 代码模板
\`\`\`python
from pptx import Presentation
from pptx.util import Inches, Pt
prs = Presentation()
# ...
prs.save('/mnt/user-data/outputs/output.pptx')
\`\`\`
```

好的 SKILL.md 有几个特征：
- 不是通用文档，而是**这个运行环境特有的约束**
- 包含已踩过的坑，防止 agent 重复犯错
- 提供可直接使用的代码片段，减少 agent 的推理负担

---

## 五、多 Skill 组合的处理

有些任务需要多个 skill 协同，比如"读取一个 PDF，然后生成 PPTX 总结"。在 system prompt 里应明确说明：

```xml
<skill_usage_rule>
Several skills may apply to one request. Read ALL plausibly-relevant
SKILL.md files before starting. The mapping from task to skill is not
always obvious from the skill name — scan descriptions carefully.
</skill_usage_rule>
```

Agent 的行为会变成：

```
view("/mnt/skills/pdf-reading/SKILL.md")   # 先读如何读 PDF
view("/mnt/skills/pptx/SKILL.md")          # 再读如何写 PPTX
→ 综合两份约束执行任务
```

---

## 六、Skill 路由的可靠性保障

纯靠 description 让 LLM 自己判断有时会漏掉。几个加固手段：

**1. 在 description 里写负例**（告诉模型什么时候不用）：
```
不适用：PDF 操作、Google Slides、纯文本输出
```

**2. 设置一个 catch-all 的 file-reading skill**，专门处理"文件已上传但 agent 不确定如何读取"的情况

**3. 在 skill_usage_rule 里加兜底规则**：
```
When in doubt about whether a skill applies, read it — 
the read cost is cheap, the miss cost is expensive.
```

**4. 对于高风险操作（写文件、执行 bash），可以强制要求 agent 在工具调用前 explain which skill it's following**，这个 CoT 本身就会促使它去查阅

---

## 七、Skill 文件的管理建议

```
/mnt/skills/
├── public/          # 平台级 skill，所有 agent 共享
│   ├── docx/SKILL.md
│   ├── pptx/SKILL.md
│   └── pdf/SKILL.md
├── private/         # 项目/团队私有 skill
│   └── videomaker/SKILL.md
└── user/            # 用户自定义 skill（如你的 imagegen skill）
    └── custom/SKILL.md
```

在 system prompt 的 available_skills 里，三类来源的 skill 都可以列，但 description 要写清楚触发范围，避免 user skill 覆盖 public skill 的判断。

---

总结一下这套机制的设计哲学：**system prompt 是目录索引，SKILL.md 是按需加载的参考手册，agent 的工具调用是两者之间的桥梁**。这样你的 skill 数量可以无限扩展，而每次请求的实际 context 始终保持精简。