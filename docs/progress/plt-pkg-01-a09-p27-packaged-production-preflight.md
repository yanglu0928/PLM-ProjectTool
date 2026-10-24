# PLT-PKG-01-A09-P27：随包生产模式信任前置核查

日期：2026-10-01；状态：`NON_RELEASE_PRODUCTION_FAIL_CLOSED_PASS / FORMAL_TRUST_NOT_PROVISIONED`。输入P22固定ZIP、P23清洁暂存、P25隔离布局与P26合成HTTPS证据。本项只核查供给缺失时的真实包内进程行为，不创建正式信任材料。

编码前检查：Phase2/Gate3开放；固定ZIP、暂存与隔离布局21,113项及映射SHA-256 `e30dc7732d78883c0b09be0911e0b16ade98c95b0af38008164fdc665c515ed4`先全量Hash核对；只读查询当前账户数据库Vault目标**是否存在**，不读取凭据内容。若已存在则跳过进程测试，避免连接未知已有数据库。仅在缺失时以临时非秘密YAML和随机回环端口运行随包`serve_windows --platform-write`，限定20秒，不改SCM/正式根/现有数据库。

`tools/preflight_packaged_production_startup_windows.py`真实执行exit0：包内正式产品公钥资源`trust/product_public_key.json`不存在；当前账户默认`PLMProjectTool/Database` Vault目标不存在。在该条件下包内生产入口退出码1，stderr仅固定拒绝信息，stdout空，API端口退出后可重新绑定；临时数据/配置自动销毁。定向单元1/1 PASS。该结果只能证明**缺材料时失败关闭**，不能证明供给正式DB/License/可信时间/游标/Secret主密钥后可启动、登录或工作。与P26仓库生产API组合通过不矛盾；其应用对象并非包内生产模式进程。

正式发行公钥/签发私钥仪式、目标服务账户Vault供给、证书私钥、NOTICE/对应源码法律审查、安装/备份迁移及Server2025/Debian13目标验收仍开放；`release_eligible=false`，Gate3不变。下一项P28转独立第三方NOTICE/对应源码盘点与差异，不把License仪式阻断当作项目整体停止。回滚删除本只读前置工具和临时输出，不触碰客户数据。
