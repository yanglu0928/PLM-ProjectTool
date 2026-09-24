# LIC-01-A04：受控激活与部署验证状态投影

- 日期：2026-09-24；结果：PASS（仅内部命令）；依据：Gate 2、ADR-006、DM-02、API-02、CR-LIC-001、DEC-20260924-092。
- Changed：管理员 Session/CSRF/Role 两次复核；目标 IMPORTED 安装执行本轮完整综合验证，拒绝即不激活。事务内核对同追踪号、安装和文档摘要、VALID 事件、机器指纹、全功能权益、有效期及 60 秒新鲜度；旧 ACTIVE 保留为 SUPERSEDED，新安装 ACTIVE，部署级单例 VALID，Audit 同事务。
- Files：`installation_activation.py`、`installation_activation_repository.py`、单元测试与 PostgreSQL 临时库脚本。Migration：无。API：无公开路由。Permission：当前 Session+CSRF+DeploymentAdmin，验证前和激活提交前均检查。
- Tests：Windows 11/Python 3.13 后端 163/163 PASS，激活服务单元覆盖率 92%；PostgreSQL 18.6 临时库首次激活、替换旧授权、证据追踪不符拒绝、验证拒绝与审计失败回滚 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：本项未接运行时 License Guard；数据库 VALID 行不代表业务路由已安全开放。验证记录与激活是先后两笔事务，后者失败留下未激活验证历史而不改变活动授权。真实生产公钥、选定 MAC、可信时间密钥与初始化未装配，脚本使用合成验证器；不能据此通过 Gate 3/UAT。
- Next：LIC-02-A04 运行时许可检查与失败关闭。
