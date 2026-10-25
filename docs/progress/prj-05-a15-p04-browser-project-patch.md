# PRJ-05-A15-P04：项目名称更新 Windows 11 浏览器与隔离数据库验收

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机合成端到端，非正式信任或三平台验收）。输入为 P01～P03、后端名称 PATCH 合同及 DEC-20260929-472。
- Changed/Files：`validation/prj-05-a04-browser-project/serve.py` 增加互斥 `--project-patch-api-only`、`--project-patch-browser` 模式，只修改每轮随机库的合成 OWNED 项目；本进度、决策、版本、状态同步。无生产程序、API、Schema、Migration、权限或依赖变化；回滚可撤夹具新增模式。
- HTTP：匿名 401、非负责人 404、缺 CSRF 403、外项目 404、缺 If-Match 428、非法 Body 400；首次改名 200/`"v1"`、旧版 409、同名再次提交仍 200/`"v2"`，独立详情读取目标名称/v2。API-only 运行 exit0。
- Browser：实际 IAB 从“我的项目”进入 OWNED 项目详情，修改名称表单明示原编号和 `"v0"`、修改范围及不确定结果处理；填写新名称、明确勾选后提交。先显示本次 `"v1"` 回执且旧详情消失，再独立刷新显示新名称/ACTIVE；browser fixture 运行 exit0。没有保存截图工件，证据为当轮可访问性状态及夹具数据库断言。
- Database/cleanup：API-only SQL 核 OWNED 新名 `ACTIVE/v2`、FOREIGN 原名 `ACTIVE/v0`、2 条 `PROJECT_PATCHED` Audit、无 PATCH 收据；浏览器轮核 OWNED 新名 `ACTIVE/v1`、FOREIGN 未变、1 条 Audit、无 PATCH 收据。两轮随机数据库/角色/Vault 精确清理 exit0。
- Environment/compatibility/upgrade：PoC PG 测试前停止、手动启动成功，验收后核查已无进程；日志末尾没有本轮正常关闭记录，停机原因未证实，不能声称 PG 关闭过程正常。兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无升级步骤。
- Tests：新增夹具 Python 语法检查、两轮独立 HTTP/浏览器/SQL/清理验收通过；前端 P03 的 756/756、typecheck、build 已通过，本项未重复运行。正式信任/TLS、Server 2025/Debian、性能、POC-03 AI 质量、Gate3/可用包未验。
- Known Issues/Next：PoC PG 偶发非预期停机原因未证实，后续运行前仍须核查服务状态。下一项按 Phase 2 WBS 继续未完成的可独立功能与集成，不将本地合成验证等同正式发行验收。
