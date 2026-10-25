# AI-02-A04：Windows 模型只读平台组合

日期：2026-10-02；状态：Windows 11 合同/当前账户临时 Vault 验证 PASS；正式目标账户及平台+PG端到端未验。依据 DEC-667、A03 可选路由与既有 Windows 显式平台组合。

Changed：新增固定 `ai-model-list-cursor-v1` 专属当前账户 Vault 只读 KeyRef，严格要求32字节；缺失/错长/读取异常使显式平台启动失败关闭，不自动生成或复用其他密钥。两个显式平台模式组合 A03 部署管理员只读模型 GET/LIST；登录专用模式维持404。模型仍无调用或质量通过权限。

Tests：单元验证固定 KeyRef 与错误关闭、Win11 临时 Vault 凭据删除后旧游标失效及加密备份恢复后旧游标有效；平台合同验证两个显式模式缺钥均启动失败、登录不开放、显式读取路由可见。后端全量2044运行/3跳过；开发 wheel SHA-256 `0047eb7252cf58d2621a7ff464684bdaa0b14ac9e6e3ffc19dbc4fa2d0b8aee3`。A03 已独立验证隔离 PG18 服务/API，但本项未验证合成平台+PG整链。

Migration：无。API：仅显式平台组合增加现有只读合同，无冻结 API Breaking Change。兼容与回滚：目标账户必须单独供给/备份模型游标密钥；未供给不能开启显式平台模式。撤组合可回退，历史模型保留。Known Issues：正式目标账户密钥、组合 PG 端到端/Server2025/Debian、模型创建/状态 API、实际 Provider 外发/质量 Gate/UAT/可用包仍待。Next：`AI-02-A05` 可选模型首次登记 HTTP 合同；组合端到端和正式密钥留在发行前验收清单。
