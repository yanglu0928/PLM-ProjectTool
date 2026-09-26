# DOC-04-A05：Windows 显式平台组合 Parse 列表

- Changed：在现有 `--platform` 与 `--platform-write` 的 DocumentReadService/真实 Session/License 组合中加入冻结 `DOCUMENT_PARSE_LIST` Router，并要求独立 Parse 游标密钥在启动时可读；普通登录模式仍不挂载。缺密钥时释放数据库资源并失败关闭。
- Files：Windows 组合入口、平台启动合同测试、隔离 PostgreSQL/真实 HTTP 集成验证；Migration/新依赖/API 变更：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 582 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 上传提交后固定版本 Parse 记录双页 HTTP、真实 Session/项目隔离/License 拒绝、只读/写模式接线、默认 404 及缺密钥失败关闭 PASS；开发 wheel PASS，SHA-256 `07d08db9d89ccc7bd710316ee035ace46dac1c7343c741ed0becd814c65c2519`。
- Result：合成信任源下 Windows 显式组合 PASS。未供给目标账户正式 Parse 密钥/发行 License 信任锚；ParseRecord 是合成元数据，真实 Parser/OCR Worker、结果文件 Hash/Locator 与精确 Evidence 定位未运行。Gate 3/发行 Gate 未通过。
- Next：Phase 2 独立 TraceLink/Evidence 任务前置核查；受真实解析结果阻塞的八型精确定位留 Phase 3。Windows Server 2025 本项未运行，Debian 13 按用户指令暂不验证。
