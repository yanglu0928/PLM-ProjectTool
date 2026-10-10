# PRT-01-A08-A02：RequirementPrototypeLink Schema

日期：2026-10-08。结论：`PRT_01_A08_A02_LINK_SCHEMA_PASS`。下一项：
`PRT-01-A08-A03` RequirementPrototypeLink CREATE/LIST Owner。

## 实现

- 新增Migration0134与`RequirementPrototypeLinkRow`，同时保存Requirement/Prototype逻辑身份、固定Version和
  Project，并以两组复合外键关闭错端点及跨项目引用；replacement使用Link+Project延迟复合自引用。
- purpose固定为`ILLUSTRATES / VALIDATES / ACCEPTANCE_REFERENCE`；Coverage固定schema version 1、两个精确
  顶层数组、covered非空、总规模/存储有界。UUID规范、全集分区、理由及当前事实证明留给A03业务Owner，
  Schema不把JSON形状冒充业务完整性。
- 状态固定为`ACTIVE / REVOKED / SUPERSEDED`。触发器只允许初始ACTIVE/lock0及一次终态转换，端点、purpose、
  coverage、Actor/时间不可改，删除/截断失败关闭，终态不能恢复。
- 同一Project、Requirement身份、Prototype身份和purpose只允许一条ACTIVE Link。替换先终结旧唯一键、再插入
  预生成ID的新ACTIVE行；延迟闭包在提交时证明replacement同Project/逻辑身份/purpose且规范载荷确有变化。
- 本项不新增Application Service或公开Router；A03前没有受支持的业务写入口。

## 验证

- Windows 11 / PostgreSQL 18.6：0133→0134有数据升级、空表降级/重升、Alembic drift、复合端点、purpose、
  Coverage形状、ACTIVE唯一性、不可逆撤销/替换、相同载荷替换回滚、删除/截断拒绝及有历史拒降通过；隔离
  数据库已销毁。既有RAG opclass/computed-default drift告警未变化。
- 首轮实库发现计划中的`jsonb_object_length`不是PostgreSQL函数，改为连续减去两个允许键后必须等于空对象，
  从新库完整重跑；规则未放宽。首轮全量回归误用仅含数据库依赖的临时venv，产生146个缺FastAPI/YAML等
  导入错误；切换既有完整Python 3.13运行环境后3157项通过、3项既有环境跳过。
- Schema/ORM定向24项、compileall通过。开发wheel共1214项，SHA-256
  `1ebf51a5cf49e9ab5f78954ad41d0213fb494ac2decd72b27c4271124c588d94`，不是正式发行包。

Schema head升至0134；无公开API、依赖、Secret、客户数据或外发变化。空Link历史可降0133；存在Link历史后
拒绝物理降级并要求前向修复。Server 2025未外推，Debian 13按用户指令跳过。
