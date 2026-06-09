## 使用Git提交更改

### 要求：使用git分模块提交我们当前未提交的修改。

### 格式规范：type(scope): 中文标题，正文为中文说明。
示例：
feat(worker): 生成管线口播 TTS 与字幕轨合并

从 storyboard 构建 narration 补全动作，将 script 字幕写入 timeline 的 text/voiceover 轨，并在 material 阶段分流视觉与 TTS、回填 wav 时长。更新 gap 选路与 gap_planner 提示词，补充集成与单测。