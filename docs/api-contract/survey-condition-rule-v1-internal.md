# Survey ConditionRule V1 内部合同

日期：2026-10-06

状态：`SUR-01-A03-P03` 内部 Owner 合同；尚未开放 `/api/v1` HTTP DTO。

`condition_rule` 是有界 JSON AST。叶节点为：

```json
{"question_ref":"UUID","operator":"EQUALS","value":"YES"}
```

- 有值操作符：`EQUALS`、`NOT_EQUALS`、`IN`、`NOT_IN`；后两者的 `value` 是 1～100 个不重复标量。
- 无值操作符：`ANSWERED`、`NOT_ANSWERED`。
- 组合节点只能是 `{"all":[...]}` 或 `{"any":[...]}`，单节点最多 20 个子项、深度最多 8、整棵树最多 100 个叶节点。
- `question_ref` 必须指向同一不可变 SurveyVersion 中顺序更早的问题；缺失、自引用、未来引用和环均使报告失败。
- 选择题条件值必须是被引用问题的固定 option code；文本、数值和日期值必须匹配被引用题型；附件只支持有无回答判断。

`validation_rule` 按题型使用最小白名单：TEXT 为 `min_length/max_length`；NUMBER 为
`minimum/maximum/integer`；DATE 为 ISO 日期 `minimum/maximum`；MULTIPLE_CHOICE 为
`min_selections/max_selections`；ATTACHMENT 为 `min_files/max_files/allowed_extensions`；
SINGLE_CHOICE 的取值集合由固定 options 决定，因此规则对象保持空。

Validate 不修改 SurveyVersion，只把当次内容、题型、条件、来源和目标部门检查结果写入 Audit 与幂等回执。
同一 Idempotency-Key 重放首次报告；使用新 Key 才重新观察外部来源当前性。
