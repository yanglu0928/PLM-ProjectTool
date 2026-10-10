# AI-04-A02-P02：Invocation/Context/外发授权 Schema

日期：2026-10-02；版本：0.1.0.dev0。Changed：依据 DEC-699 新增 AIInvocation、不可变Context引用、逐次外发授权快照、AITask当前Attempt复合引用及数据库状态/历史守卫；Alembic增量至0064，AI-04-A02物理Schema切片完成。无API、厂商SDK调用或真实数据外发。

Migration：Win11隔离PostgreSQL 18空库 up/down/re-up、既有0063用户/项目/Provider/Model/Prompt/Task数据升级、drift=0；同Task Scope/Project、Provider区域、类别唯一、外部调用强授权、Attempt连续编号、ACTIVE Provider/AVAILABLE Model/当前ACTIVE Prompt、Schema VALID成功、当前Attempt、Context及终态不可变、无Secret/正文列、非空拒降均PASS。首轮PL/pgSQL局部变量与列名歧义，改为显式表别名/变量前缀后完整重跑PASS。

Tests：迁移/ORM定向7项PASS；首轮全量误用数据库最小虚拟环境，2020项中12项因环境缺`pydantic-settings`导入失败，非产品断言失败；切换仓库完整Python3.13验证环境后2100运行/3跳过PASS。开发wheel包含0064和ORM，SHA-256 `f6e46044844a1ad9fb2dbc99d429cca607a4185d6d544673edbbbb8a47295d3e`，非交付包。

兼容/升级/回滚：正式库先备份并受控升0064；无新历史可降0063，有历史拒降并保留。Known Issues：输入Owner真实版本/权限解析、内部Task创建与幂等、统一AIService/Job执行、正式Prompt/Provider信任、真实外发/质量、Server2025/Debian、Gate3/UAT/可用包仍待。Next：`AI-04-A03` 先做内部AITask创建、Project授权/幂等与输入版本准入前置核查和实现切分。
