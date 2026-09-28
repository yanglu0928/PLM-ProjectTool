# AUT05A05 浏览器登录验证

2026-09-27～28 / 0.1.0.dev0 / PASS（Windows 11 合成浏览器范围）。

编码前：Phase2/AUT05A05；前置A04实际网络与临时源清理已通过、A02页面63测试通过；输入现有Client/页面/原Windows登录工厂/0049。仅独立合成browser fixture与验收，不修改原21请求fixture或审计计数、不改生产/API/权限/依赖。

采用computer-use skill优先浏览器工具操作自有loopback页面，固定新合成User/真实Scrypt/临时PG角色与Vault，显式本轮Vite Origin，原Uvicorn/代理；原A04临时库已清除，不复用其数据。测试密码仅synthetic-browser-password，不是用户或生产凭据，不保存至浏览器密码管理器。浏览器不执行脚本读取Cookie或storage，仅页面交互验证；无法据页面单独证明HttpOnly不可读取或无持久化，属性/源码/契约证据分别记录。

计划：错密码拒绝、正确登录/密码清空、续期、退出、退出后读取拒绝、再次登录、reload后身份查询只读/续期退出disabled、再次登录后退出。终态PG预期4Sessions/3issued/1renewed/2revoked，早期重新登录的旧Session可仍有效（原服务语义不静默改写），不将清页面当撤会话。精确最终计数验收，不放宽或为迎合测试修改后端。

风险/回滚：900秒最大等待/异常退出清自有服务与临时库角色Vault，停止确认后清源；不输出Token/hash/真实秘密/不外发。独立窗口不触碰用户其他浏览页面。未测TLS/Secure/最低硬件/生产信任/性能/全Scope；查看布局不等于完整UI验收。删除新验证文件即可回滚，无DB升级。Gate/完整包仍待。

首次浏览器错密码提交仅显示通用不可用，而非固定AUTH_INVALID_CREDENTIALS提示；未标PASS。检查现有Client直接this.fetcher调用会给原生Window.fetch非Window receiver，而Mock未检验receiver；选择先修调用为独立函数调用并增加严格receiver测试，再同浏览器链复验。该兼容修复不改变API/权限/算法，生产差异另记录结果，不凭假设宣称根因已证实。

第一fixture修fetch后错误密码提示/登录通过，续期PG已提交（2Session/1renewed）但页面拒绝，GET200也拒绝。临时安全布尔形状诊断定位两expiry校验false；PG按本地时区读出带offset日期而原Client只接UTC，登录新发时间UTC所以前面通过。接受严格RFC3339显式offset、校验原日历有效性/期限顺序后客户端规范为UTC，不丢日期检查、不改权限或后端合同；补正/负offset测试。诊断console已撤，不输出Token/hash；第一fixture不符合原完整计数，保留失败并清理，另全新fixture按原4/3/1/2/2计划完整复验，不放宽SQL断言。

2026-09-28 复验过程：跨轮保留的第二fixture达到原900秒等待上限自行失败退出；重新检查其临时PG库/角色均为0，原本机PG18.6监听55432。第一次重启误选仅有标准库的裸Python，缺Alembic；第二次选旧PoC venv缺pydantic-settings；第三次未分配交互终端，stdin EOF立即失败。三次均没有执行浏览器操作，fixture的finally分别清理自有库/角色/Vault，不算复验通过。最终使用项目已隔离PoC Python 3.13 venv及本地foundation依赖，交互终端启动新fixture；不把这些运行器问题归因于产品。

新fixture实际浏览器页面逐步验收：错误密码固定中文提示/无身份；正确登录1后可见合成用户名、普通用户、0授权项目且密码输入清空；续期成功且身份保留；退出1成功，随后读取提示会话失效且无身份；正确登录2成功；刷新后无身份且续期/退出不可用；读取仅恢复身份并提示提交前重新登录；正确登录3、退出2成功。浏览器未读取Cookie/storage或直接发API请求，所有写动作均经页面按钮。最终同一临时PG精确断言4个Session、3个SESSION_ISSUED、1个SESSION_RENEWED、2个SESSION_REVOKED、2个logout收据通过（exit0）；自有服务已停止，临时库/角色不存在，Vault目标缺项1168。该计数不证明登录2的旧会话被自动撤销，原语义仍如实保留。

视觉检查：桌面截图可见中文卡片、明确的表单与状态、禁用态和只读说明；页头两导航文案在当前宽度相邻，留作独立UI排版任务，未声称移动端/无障碍全面通过。前端66个测试、类型检查和构建通过；未运行本项后端全量unit/coverage/wheel，未验证HTTPS/Secure、正式账号/信任锚、Server2025/Debian、浏览器跨机、完整UAT或可交付包。DB本地时区偏移与冻结合同要求UTC之间仍有服务端输出一致性待核，客户端本轮仅做安全兼容及UTC归一化，下一独立任务处理服务端合同偏差，不能把本次浏览器PASS扩展为Gate3 PASS。
