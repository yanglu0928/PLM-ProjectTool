# CR-PKG-006：Ghostscript 10.08.0 对应源码加入新的非发行候选

日期：2026-10-01；状态：`RECORDED / NEW_CANDIDATE_INTEGRITY_PASS / RELEASE_REVIEW_OPEN`；关联 `PLT-PKG-01-A09-P43-A01～A03`、P33 固定非发行 ZIP、P28 发行差异和用户公开源码/遵守 Ghostscript 开源协议的要求。Gate 2 原冻结提交 `64cdf09` 及 P33 历史候选均不追写。

## 来源与偏差

P33 包含 Ghostscript 10.08.0 Windows x64 运行载荷及 `doc/COPYING`，但未附对应源码。P43-A02 已取得 Artifex 官方同版 `ghostscript-10.08.0.tar.xz` 并验 SHA-256、归档结构、Windows 构建元数据和与 P33 相同的 AGPL 文本。仍未证明可重现构建或完整法律合规。发行源代码/NOTICE 证据缺口阻止把 P33 提升为 Release。

## 方案比较及选择

|方案|判断|
|---|---|
|继续保持 P33，仅在文档提供官方下载链接|原包离线交付时不能直接访问源码；若链接失效则来源不可控，不足以收敛本项目离线候选的源码证据。|
|在新的非发行候选中加入固定官方源码归档及源包 `LICENSE`|保持 P33 历史不变，源码与二进制同包可离线核验；增加约 66 MiB 及全量重验成本。选择。|
|自行重新编译替换原 Windows 二进制|引入新的构建/运行差异，需额外安全和功能回归；当前无必要，保留为将来有可重现构建要求时的独立任务。|

## 范围、迁移与回滚

新建名称含 `NOT-FOR-RELEASE` 的候选，不覆盖 P33/P22。只增加 `payload/third-party-sources/ghostscript/ghostscript-10.08.0.tar.xz` 及 `payload/third-party-licenses/ghostscript/source-LICENSE` 两项，现有 21,112 个载荷逐件保持原 SHA；更新 manifest、逐项 hash 表和第三方库存的来源字段，继续写 `review_status=REVIEW_REQUIRED`、`release_eligible=false`、`legal_clearance=false`。不改变程序运行二进制、业务/API/Schema/Migration、SCM、正式安装根、Secret 或客户数据。没有升级迁移。回滚只需停用新候选，原 P33 固定 ZIP 可独立恢复；不得把旧包误称可发行。

## 验证计划与剩余风险

构建前重验 P33/P22 谱系和官方源码；构建后独立核新包文件数/来源关系、新增归档及 LICENSE 的字节摘要、原载荷全量不变、metadata 保持非发行；之后须清洁解包并核落盘及运行布局。P33 原 SHA 应保持不变。新增源码不能单独满足产品级 LICENSE/NOTICE、Ghostscript 与其他第三方完整义务或合格法律复核；也不能替代正式 License 公钥/证书/账户、目标平台或 Gate 验收。任一验证失败不向发行提升。

依据：[Artifex 官方发布资产](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs10080)、[Artifex 许可说明](https://artifex.com/licensing)。此 CR 是技术追溯与实施计划，不是法律意见。

2026-10-01/P43-A03 实施证据：新建不覆盖 P33 的非发行 ZIP，748,147,289 字节/SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`；原 21,112 项载荷全量不变，仅增同版官方源码和源包 LICENSE 至 21,114 项。构建及独立全量谱系验证 PASS、定向 6/6。尚未清洁解包或完成产品 NOTICE/法律复核；`release_eligible=false`。

2026-10-01/P43-A04 增量证据：P43-A03 新 ZIP 在全新 ASCII Temp 直属目录清洁解包 21,114 载荷＋三份 metadata，逐项 Hash/文件全集/源码和 LICENSE 内部同字节/来源末次复核 PASS，定向 2/2。暂存非正式安装；运行布局和完整法律义务仍待，`release_eligible=false`。

2026-10-01/P43-A05 增量证据：新 ZIP/暂存全量先验后，独立 ASCII Temp 布局 21,117 目标文件复制/全量 Hash、精确映射、Ghostscript/Go 源与许可、模型指纹、随包 Python/PG/Caddy/Ghostscript 版本及合成 Caddyfile validate PASS，定向 1/1。首次系统 Python 缺依赖在复制前失败，换随包 Python 完整重跑。正式 HTTPS 登录、产品 NOTICE/法律审核、目标环境 Gate 仍待，`release_eligible=false`。
