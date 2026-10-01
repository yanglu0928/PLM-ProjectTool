# JOB-02-A06-P04：包内 Python/PG18 项目 Job 取消矩阵

2026-10-02 / Phase 2。编码前核查：JOB-02-A05 Windows 写组合、JOB-02-A06-P01～P03 前端合同已通过；包内PG18.6/Python3.13及既有一次性数据库 Runner 可复用。仅扩展固定验证入口，不改产品实体/API/Schema/依赖/权限，不触碰既有生产库、服务或用户数据。目标是包内后端合成 ASGI/隔离PG真实执行，不能替代前端真实浏览器。

变更：`validation/job-01-a06-p07/verify.py` 增加仅 `read|cancel` 的固定白名单选择；默认双只读矩阵不变，cancel 模式只执行既有 `validation/job-02-a05-windows-cancel/verify.py` 并核完成标记。数据库仍在明确 ASCII Temp 根下独立创建，端口占用直接拒绝，验证后停机并只清理新建的精确目录。新增未知矩阵拒绝单元测试。

验证：首轮新增拒绝测试因 PG 二进制检查先于参数校验而失败；把固定矩阵选择提前到路径/二进制核查之前后重跑 3/3 PASS。实际使用 P49 清洁包内 Python、PG18.6，在 D:\PLMTemp/127.0.0.1:55432 跑原 Windows 写 Factory/Session-CSRF/项目Job取消/Worker确认/currentGET与历史收据/默认关闭/失败关闭矩阵，脚本退出0并含 `JOB-02-A05 PASS:`。PG停止、临时目录清理及端口无监听复核通过。正向 License/可信材料依然是测试合成；原脚本使用 ASGI TestClient，并未启动外部HTTP监听；本项没有验证浏览器请求、前端保存操作号、正式目标账户/三平台或Gate3。

兼容性：仅验证工具，原 `read` 默认入口不变。升级/回滚：无产品迁移；撤固定 cancel 选项可回滚，不涉及原数据。下一项重建包含 P01～P03 前端的当前应用非发行包并复核清洁映射，正式信任/法律/Gate仍保持阻断。
