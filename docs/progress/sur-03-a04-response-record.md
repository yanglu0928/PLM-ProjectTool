# SUR-03-A04：Response/Answer/Evidence 追加 Owner

日期：2026-10-06。结论：`SUR_03_A04_RESPONSE_RECORD_PASS`。下一项：`SUR-03-A05` SUBMIT 当前回答、条件、必答、ValidationRule 与 Evidence 完整性 Owner。

## 实现

- 新增单题答复原子 Owner：在一个调用方事务内完成 Session/CSRF、License、Project授权、OPEN Round、Assignment强版本与当前录入主体校验，随后追加Response、唯一Answer、固定Evidence refs、Audit和持久幂等receipt。
- 自助录入只允许显式assignee本人或部门级Assignment的当前同部门成员；ImplementationMember可受权录入。`FACILITATED_RECORD`进一步只允许ImplementationMember，并在同一事务调用Round PROJECT_RECORD proof/append，返回的固定source ref同时进入Response和Answer Evidence。
- 六类基础值规范固定为TEXT规范化非空字符串、固定选项SINGLE/MULTIPLE_CHOICE、ISO DATE、有限NUMBER、以及必须有固定Evidence且不接受客户端值的ATTACHMENT；raw文本独立规范化。
- 更正只追加新Response并引用旧Response；数据库0108继续强制单根、单后继、同Assignment/Question和一Response一Answer。写入仓储显式按Response→Answer→Evidence顺序flush，避免依赖ORM无关系映射时的隐式排序。
- 幂等重放重新读取持久事实并核对actor、来源类型/source ref、Evidence数量、更正关系和Assignment新ETag，异常对象或不一致历史不能变成成功回执。

## 验证

- Windows 11/PostgreSQL 18.6：客户自助、固定Evidence、追加更正、实施代录及Round source同事务、PM代录拒绝、CSRF/License拒绝、Audit故障整笔回滚与同Key恢复、同Key双线程收敛、Response/Answer/Source/Audit/receipt精确计数及Alembic drift均通过。
- 单元覆盖六类answer值的正反规范；后端全量`2888 passed / 3 skipped`、`4188`子断言；wheel`1077`项，SHA-256 `7704683dd77d200f01f35a49abcbce9012562e118f6a4f2648766ae68b59ceba`。wheel不是最终交付安装包。
- 验收夹具首轮触发0108的Assignment target唯一约束，第二轮触发同Round/Question/Evidence来源唯一约束；已按真实业务约束改为五种唯一target和不同PROJECT_RECORD Evidence，从全新临时库重跑通过。产品约束未放宽，失败库均已强制清理。

## 兼容、回滚与已知问题

无Schema/Migration、公开URL/JSON、依赖、Secret或数据外发变化；只增加内部Owner和一项冻结操作策略。未装配Router时外部仍404；停止后续装配可阻止新写，已提交Response/Answer/Evidence/Audit/receipt历史必须保留。A05以后的SUBMIT/VALIDATE/RETURN、Round完整性/CLOSE、HTTP/UI/浏览器、Gate 3/UAT及发行仍待客观验证。
