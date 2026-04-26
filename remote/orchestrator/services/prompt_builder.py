from models import ContextMessage


class PromptBuilder:
    def build_system_prompt(
        self,
        base_prompt: str,
        *,
        context_summary: str,
        rag_context: str | None = None,
        route_label: str | None = None,
    ) -> str:
        sections = [base_prompt]

        if context_summary:
            sections.append(f"Recent context summary:\n{context_summary}")

        if rag_context:
            sections.append(rag_context)
            sections.append(self._build_rag_boundary(route_label))

        return "\n\n".join(section for section in sections if section.strip())

    def build_reasoning_hint(self, context_messages: list[ContextMessage]) -> str | None:
        if not context_messages:
            return "fresh-session"

        roles = ",".join(message.role for message in context_messages[-4:])
        return f"context-roles:{roles}"

    def _build_rag_boundary(self, route_label: str | None) -> str:
        base_rules = [
            "【回答边界】",
            "你是情感陪护数字人，不是医生或急救服务。",
            "可以基于知识库参考提供支持性、教育性、陪伴性建议，但不能给出医学诊断、处方、停药或改药建议。",
            "如果知识库没有相关依据，要保持一般性支持，不要编造专业结论或来源。",
        ]
        if route_label == "risk_escalation":
            base_rules.extend(
                [
                    "当前路由提示存在较高风险信号。回复要短、稳、明确，优先确认用户当前安全。",
                    "建议用户立即联系身边可信赖的人、家属、专业人员、当地紧急服务或危机干预资源。",
                    "不要只给普通安慰，不要承诺替代线下帮助。",
                ]
            )
        else:
            base_rules.append("回复应先共情，再给一到两个低负担、可执行的下一步。")
        return "\n".join(base_rules)


prompt_builder = PromptBuilder()
