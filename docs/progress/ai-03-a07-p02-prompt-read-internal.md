# AI-03-A07-P02：Prompt 元数据只读内核

日期：2026-10-02；版本：0.1.0.dev0；依据冻结 API-03 `AI_PROMPT_LIST/GET`、DM-04及 P01 前置核查。

Changed：新增 Prompt 专属 HMAC 游标、DeploymentAdmin/License 双重授权只读服务、SQLAlchemy 安全投影仓储；游标绑定会话与页大小，按 `(created_at, prompt_template_id)` 降序 keyset 分页。SQL 查询只选择版本的 hash/schema/policy 列，不选择 system/user 模板正文。DRAFT/RETIRED 均不输出活动版本；RETIRED 历史指针留在数据库供审计，不被描述为可调用版本。

Files：`prompt_list_cursor.py`、`prompt_metadata.py`、`prompt_metadata_repository.py`、单元测试及 `validation/ai-03-a07-p02-prompt-read/verify.py`。Migration/API：无新 Schema、依赖或公开 Router；冻结合同未改。兼容/回滚：内部新增能力，撤用服务即可停止读取；不改变现有 Prompt 数据或写路径。

Tests：专属游标篡改/跨会话/页大小/错密钥、两页稳定排序、权限/License/参数/缺密钥失败关闭单元4项 PASS；Win11 隔离PG18 DRAFT/ACTIVE/RETIRED 投影、正文不进入 DTO、游标 keyset 跨页 PASS；后端全量2094运行/3跳过 PASS。开发 wheel 构建 PASS，SHA-256 `135071a33833a5e6e18f86da39d8e64be704e3cc2e0140a1281ae3b84d51a9e7`，非交付包。首轮隔离库启动到默认5432、第二轮测试脚本未显式开启事务，修复测试启动参数/脚本后在55434重跑 PASS，生产实现未因此更改。

Known Issues：公开 LIST/GET HTTP、专属 Windows 密钥来源/组合装配、正式发行信任/目标账户、Server2025/Debian、Invocation 对 RETIRED 的资格拒绝、Gate3/UAT/可用包均未完成。Next：`AI-03-A07-P03` 可选只读 HTTP 合同与隔离PG18验证。
