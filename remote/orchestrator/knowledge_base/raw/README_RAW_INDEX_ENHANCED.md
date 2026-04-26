# A22 RAG 增强版 raw/ 索引

本目录是在第一版 raw/ 基础上，直接应用第二、三、四阶段优化后的增强版知识库原始文档。

## 已应用的优化

### 第二阶段：主题原子化拆分
将原先较大的主题文档，拆成更适合 chunk、rerank、debug 的原子文档。

### 第三阶段：用户类型维度扩展
新增面向老年人、家属/陪伴者的场景文档，使知识库更贴合 A22 赛题中的老年情感陪护背景。

### 第四阶段：对话问答对增强
新增 FAQ/示例问答类文档，帮助模型在真实问法下更稳地召回与组织答案。

## 目录结构

### 1. 焦虑专题
- anxiety_signs.md
- anxiety_daily_support.md
- anxiety_sleep_link.md
- anxiety_escalation.md

### 2. 抑郁/情绪低落专题
- depression_signs.md
- depression_support.md
- depression_escalation.md

### 3. 双相风险专题
- bipolar_warning_signs.md
- bipolar_safe_response.md

### 4. 睡眠与压力专题
- sleep_support.md
- stress_support.md

### 5. 对话模板专题
- support_templates_empathy.md
- support_templates_clarification.md
- support_templates_encouragement.md

### 6. 安全升级专题
- safety_self_harm_escalation.md
- safety_severe_insomnia_escalation.md
- safety_mania_risk_escalation.md

### 7. 用户类型扩展专题
- elder_loneliness_support.md
- family_companion_guidance.md
- older_adult_sleep_and_anxiety.md

### 8. FAQ / 示例问答专题
- faq_anxiety_support.md
- faq_depression_support.md
- faq_sleep_stress_support.md
- faq_risk_escalation.md

## 当前 source 策略
当前文档暂以 `internal_curated` 为主，适合用于：
- loader/chunker 开发
- metadata 过滤开发
- 初版 RAG 测试集构建
- prompt 调试

## 下一步建议
1. 先用本目录跑通 loader/chunker 和 FAISS 建库。
2. 再基于权威公开资料做第五阶段优化：
   - 给核心知识文档补权威来源字段
   - 用 NIMH / NHS / WHO 内容替换或增强关键段落
   - 提升“专业性、可追溯性、可答辩性”
3. 最后再做评测集与输出安全调优。
