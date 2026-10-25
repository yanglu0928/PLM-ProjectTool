# AUD-03-A06-A02-P02-A01：取消追溯存储

日期2026-09-26；版本0.1.0.dev0；Phase2；结果CANCEL_HISTORY_SCHEMA_PASS。不是受权取消/协作确认/到期恢复验收。

## 编码前检查 / Changed / Files

实际核查DM-04明确cancel_requested_by/reason，而现有Job只有state枚举，没有取消信息字段。正式总控V1.1及实施方案V2.1已核对。实施前登记CR-JOB-002及DEC-20260926-199，自主补齐冻结基线实现遗漏，不猜旧数据。只解决必要存储前置；模块Jobs、实体Job；不跨Phase实施AI任务。

新增0039、Job ORM三nullable字段、三项unit、独立Schema验证，更新head合同测试；旧acceptance回归的多步DDL失败版本断言用ScriptDirectory实际head，避免新迁移后仍猜0038。0001～0038及冻结64cdf09保留。

cancel_requested_by为Auth User FK，cancel_reason为1～1024字符trim文本，cancel_requested_at为有限UTC时点且不早于Job创建；三字段全空或全非空，后者只合法于CANCEL_REQUESTED/CANCELLED。FK不是当前授权。首次写入仅允许从可运行前态进入取消态，旧取消/终态无信息行不回填。首次信息固定，禁止清空/修改，以及换Job身份/Owner/类型/Scope/Project/Actor/Trace/payload/幂等键；取消终态不复活、不改完成时点。含取消信息的Job禁止删除，整表truncate含取消信息拒绝。不自动清理Job/Lease/Attempt或审计。

## Migration / Review / Tests / Result

0039仅增量三列、FK/CHECK及保护trigger/function。down先ACCESS EXCLUSIVE锁Job，任何取消信息拒绝；离线down关闭，无信息可撤新增结构，旧字段和行保持。生产升级需要人工备份/维护窗口，本轮未操作生产。

Win11/Python3.13/PostgreSQL18独立库空up/down/re-up、Job ORM parity无diff；在0038创建六类旧状态行，0039 up/down/re-up旧列逐字段完整、全NULL无猜回填。错误成组、空/过长/未trim中文原因、零/不存在申请人、早于创建或无限时点、非取消态拒绝；旧取消/终态回填拒绝。首信息/技术身份不可改/不可删/truncate、合法REQUESTED→CANCELLED、终态复活或改完成时点拒绝。down持表排他锁时实际竞争ROW EXCLUSIVE超时；有取消历史down拒绝、head0039/全行完整。验证使用合成元数据转换，不冒充真正受权取消或Worker执行。finally清理独立库，无客户数据外发。

首次验证脚本的空payload字典缺psycopg Jsonb包装导致夹具插入失败，已修复并重跑通过；非产品代码故障。后端860项无失败，2项既有Windows符号链接权限跳过。真实Lease checkpoint、原双Worker租约、acceptance Schema、完整受权原子提交/并发/故障/40P01回归通过（License合成）。开发wheel通过，SHA-256 `4067701485a6489119b3afe0db7860da9acd45fdbf73ae27141401528d159656`，非正式安装包。

## API / Compatibility / Known Issues / Next

无公开API/Scope/角色/依赖变化；Schema增量需0039，有取消信息不能降回0038，不删历史绕过。Schema不能证明申请人权限、文本无Secret或真正取消已完成；应用安全原因校验/受控Audit投影和协作状态流程仍待。尚无公开取消/导出POST，文件发布链未完成。Server2025本轮未验，Debian13暂缓但目标保留，完整Scope/质量/实际业务Owner/正式信任源/性能/Gate3/UAT/可用包仍待。

下一项AUD-03-A06-A02-P02-A02：Jobs owned实际取消请求、当前Worker协作确认和到期恢复事务公共Port，再接Audit当前权限/资源/receipt/Audit原子编排及发布竞争；状态机不能伪装回滚已发布不可变成果。
