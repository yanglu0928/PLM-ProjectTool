# PLT-02-A07-P03-A02：本产品发行公钥来源

- 日期：2026-09-25；状态：装载边界 IMPLEMENTED / RELEASE TRUST ANCHOR NOT PROVISIONED / 本项尚未 PASS。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P03-A02。输入：Gate 2/ADR-006、CR-LIC-001、现有 Ed25519 验签与 ProductPublicKey Port。前置满足代码实现；正式签发密钥仍缺。
- 涉及 License 基础设施、wheel 包数据声明与发行检查入口；无实体、Schema、Migration、公开 API 或权限变更。验收：只接受包内唯一产品代码和固定 key_ref 的 32 字节 Ed25519 公钥；清单缺失/畸形/重复字段/其它产品或引用失败关闭；正式 wheel 必须有经签发流程提供的公钥。
- 实现：`PackagedProductKey` 从已安装 `plm_assistant.modules.license/trust/product_public_key.json` 读取严格的 `plm.product-public-key.v1` 清单，同时实现公钥解析和本产品固定引用。运行时不接受普通配置、数据库、请求或 License 文档指定的其它公钥。`python -m plm_assistant.entrypoints.verify_release_key` 为发行门禁；当前因缺少真实公钥应返回失败。源代码没有测试公钥或私钥。
- 验证：Windows 11/Python 3.13 后端 341/341 PASS，合成公钥/签名、错误产品/引用/畸形/缺失拒绝；当前包默认实例化输出 `MISSING_RELEASE_KEY_FAIL_CLOSED`；开发 wheel 构建 PASS，但其成功不等于发行门禁通过。无数据库或外部数据操作。
- 待完成：Developer Workbench 的正式 Ed25519 私钥生成、备份/保管与对应公钥清单发行；从最终 wheel 安装环境执行门禁和真实签发→验签，且不得将私钥装入客户包或 Git。未完成前生产 License Guard 和受许可管理 API 继续关闭。Windows Server 2025 未验证；Debian 13 按用户指令暂不验证。
