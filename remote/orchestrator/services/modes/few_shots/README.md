# Few-shot 扩展预留

当前版本先把 few-shot 示例写在 `services/modes/instructions/*.md` 中，避免扩大 `ModePolicy` 改动面。

后续可以在 `ModePolicy` 中增加：

- `few_shot_path`
- `few_shots`

建议每个模式一个文件，例如：

- `care.md`
- `accompany.md`
- `learning.md`
- `game.md`

接入时由对应 `ModeService` 加载，并由 `LLMClient` 在 system prompt 中按模式注入。
