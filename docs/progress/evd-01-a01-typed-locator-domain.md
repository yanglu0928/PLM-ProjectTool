# EVD-01-A01：九类 EvidenceLocator 内部类型校验

- 日期：2026-09-26；Phase 2 Platform Core；输入：Gate 2 冻结 DM-03、API-02、EVD-01 与 `DEC-20260926-135`。
- Changed：新增 Evidence 模块的纯领域定位器校验。九类 `locator_type` 只接受白名单字段；整数拒绝布尔值；页/节、偏移、矩形、Sheet A1 范围、ParseRecord UUID 和非递归源定位均检查；返回与输入分离的规范副本。非法定位只返回通用领域错误，不回显路径或正文。
- Files：`apps/backend/src/plm_assistant/modules/evidence/domain/locator.py` 及模块入口、`apps/backend/tests/unit/test_evidence_locator.py`。Migration、公开 API、新依赖：无；版本 `0.1.0.dev0`，现有安装无需升级数据库。
- Tests：Windows 11/Python 3.13 九类型与非法形态单元测试 PASS；完整后端 564 项无失败（2 项既有符号链接环境跳过）；开发 wheel 构建 PASS。
- Result：仅内部字段合同 PASS。校验器不验证 DocumentVersion 是否 AVAILABLE、内容指纹是否真实、当前访问权限或是否能在原文件精确重定位；不会赋予 ELIGIBLE 资格，也未挂公开 Viewer。EVD-01 整体、Gate 3 与可用程序包均未因此通过。
- Next：EVD-01-A02 设计并验证 Evidence 持久模型/迁移（固定 DocumentVersion、Scope/Project 与类型化 Locator）；其后再做受权来源解析、资格命令和 Viewer。Server 2025 本项未执行，Debian 13 按用户当前指令暂不验证。
