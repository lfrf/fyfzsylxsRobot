# 输出约束扩展预留

当前版本的全局 TTS 输出约束写在 `LLMClient._build_system_prompt()` 中，模式专属格式要求写在 `instructions/*.md` 中。

后续可以在 `ModePolicy` 中增加：

- `output_constraint_path`
- `output_constraints`

建议用于承载更细的模式输出约束，例如：

- care：短句、慢节奏、安全边界
- accompany：自然口语、少建议、轻追问
- learning：最多三步、定义加例子、自测最多三题
- game：每次推进一步、不声称完整计分系统
