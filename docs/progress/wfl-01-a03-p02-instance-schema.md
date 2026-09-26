# WFL-01-A03-P02：Workflow 四表与结构约束

- Phase 2；输入冻结 SC-01/SC-02、DM-02、CR-WFL-001 V1 配置、CR-WFL-002 状态语义。编码前明确仅 WFL-01 ORM/迁移/结构，不改 API/权限或业务事实。
- Changed/Files：workflow infrastructure ORM、纯定义 fingerprint、Migration `20260926_0030`、迁移 metadata 注册、单元/迁移合同测试、隔离验证脚本、版本/状态/决策文档。四表项目及父子复合归属、唯一 key/order、定义固定 fingerprint、初态、定义防改写、历史防删、状态/指针结构；提交延迟校验拒绝半套实例。
- Migration：0030 继承 0029，自包含固定 V1 内容，不导入运行时 Domain。已有 Project 不自动回填，生产升级前备份。空 Workflow 可降级/再升；有实例拒绝降级，不可删除业务历史。无新依赖/公开 API 变化。
- Tests：Windows 11/Python 3.13 后端 619 项无失败，2 项既有符号链接环境跳过。隔离 PostgreSQL 18.6 空库全量 up、空 Workflow down/re-up、有既有 Project 升级、ORM parity、半套/required 篡改/版本/hash/跨项目/定义/锁/双当前/跳级/过早终态/复活/删除拒绝、合法 BLOCKED→ACTIVE 与顺序结构 PASS；非空 down 拒绝 PASS。
- 修复记录：初次真实验证发现共享 INSERT trigger 的布尔表达式可能解析其他表不存在的字段；改为按表名嵌套条件，重跑通过。回归的两项失败为 head 与注册表集合仍写旧值，扩展精确预期及单独 ORM import 后全部通过；未削弱断言。
- Build：开发 wheel 包含 0030、ORM、fingerprint PASS；SHA-256 `7e6cae30210e313e104a82174d4c67bf633d9f637abbf4a3188d8cba915c0138`。没有发行包/安装/UAT 验收。
- Result：WFL-01 四表**结构范围** PASS；不代表业务 Gate、Workflow 全链或 Gate 3 PASS。API/Permission/真实业务 Gate 未运行，尚未实现这些路径。
- Known Issues：当前 Project 尚未自动拥有实例；初始化/Project 创建接线、同事务历史/Audit/幂等、真实 Gate/Owner/Review/Evidence、最后阶段完成 HTTP 未具备。数据库结构可表示 PASS/WAIVED/COMPLETED，不证明对应业务事实；禁止独立生产更新，业务写 API 未挂载。Stage 状态变更的 root 锁与历史由后续受控 Application 保证。
- 清理：脚本仅删除自身随机临时库；测试 PostgreSQL 服务已停止，未修改生产或客户数据。Windows Server 2025 未运行，Debian 13 按用户要求暂不验证。
- Next：WFL-01-A03-P03 受控初始化及既有 Project/新建 Project 接线前置；先确保历史/Audit/幂等合同，不凭迁移自动推断项目进度。
