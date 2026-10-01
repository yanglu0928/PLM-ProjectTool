# PLT-PKG-01-A09-P47-A05：当前非发行候选隔离 HTTPS/License 链

日期：2026-10-02；Phase 2；结果：`SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS / RELEASE_OPEN`。

编码前检查：CR-PKG-008、P47-A03 新候选 SHA/清洁解包与 P47-A04 包内迁移已通过，复用历史合成HTTPS/License演练边界。仅新增新候选布局映射/烟测适配工具与定向测试；不修改产品 API/ORM/Migration、正式安装根、SCM或现有数据库。实体为临时 PG 的合成登录用户，权限验收是匿名/错误 Host/Origin 关闭、授权登录和未装 License 时受保护 Project 拒绝；风险为 Vault 固定目标冲突、临时进程或文件残留、误将合成信任认作正式信任，故先检查固定目标空缺并于完成后逐项回读/停止。

首次在默认 C 盘 Temp 进行第一份布局复制时发生 `Errno 28: No space left on device`；在服务/数据库启动前失败。`_copy_and_publish` 清理未发布的私有部分目录，源候选不变。C 盘此前已成功验证的 `C:\Users\17231\AppData\Local\Temp\plm-current-app-stage-db7508e42667` 仍保留；其精确范围删除命令被环境策略拒绝，未绕过。D 盘存在足够空闲空间，因此仅对测试进程将 TEMP/TMP 指到 `D:\PLMTemp`，重新清洁解包到 `plm-current-app-stage-544a31619fae`，21,178载荷＋3元数据全量哈希/全集复核退出0。

从 D 盘新暂存将21,181文件映射到两份全新 `plm-install-rehearsal-*` 隔离布局，复制时及发布后全量读回 SHA，并检查新 Evidence 回查模块/迁移0052的目标路径。复用已验证的合成信任和启动测试：包内 Python/Caddy/临时PG18实际启动，错误 Host 421、错误 Origin 403，登录200且 Secure/HttpOnly/SameSite Cookie、会话200，无 License 的受保护 Project 403。合成公钥仅注入临时副本，非原候选；12项临时 Vault Key 与数据库凭据、API/Caddy/PG进程及测试目标文件均核查清理；候选 SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7` 前后不变。实际测试退出0、定向失败关闭单元1/1。

本项证明 Windows 11 的**合成**包内运行链，不证明正式 TLS 证书、公钥来源、客户 License、真实浏览器 UI、Server2025/Debian、法律/NOTICE、AI质量、正式安装升级、UAT或 Gate 3。`release_eligible=false`、`legal_clearance=false`、`formal_trust_provisioned=false`。D 盘清洁暂存也仍保留供后续候选验证，不是正式程序包目录；回滚为弃用该副本/工具，历史 P45 ZIP 与当前候选 ZIP 均未修改。
