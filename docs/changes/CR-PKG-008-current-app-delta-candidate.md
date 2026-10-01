# CR-PKG-008：固定非发行候选与当前应用源码漂移

日期：2026-10-02；来源：`PLT-PKG-01-A09-P47-A01` 当前可使用程序包前置核查；状态：`RECORDED / IMPLEMENTATION_OPEN`。原固定候选、原 Gate 2 提交和既有发行阻断记录均不追写。

P47-A02 已完成派生构建器的合成安全合同 7/7；P47-A03 已完成真实父 ZIP 派生、21,178件清洁解包和包内 Python 导入，见 [P47-A03](../progress/plt-pkg-01-a09-p47-a03-current-app-candidate-extract.md)；P47-A04 完成临时双库随包0052迁移，见 [P47-A04](../progress/plt-pkg-01-a09-p47-a04-packaged-migration.md)。隔离 HTTPS/License 与正式发行仍未验，状态保持 OPEN。

## 冲突与证据

Windows 11 原生 OCR 通知非发行 ZIP 位于 Git 忽略区，重新计算 SHA-256 为 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，与 P45 记录一致。它的 `manifest.json` 为 `version=0.1.0.dev0`、`release_eligible=false`、`legal_clearance=false`。只读检查 ZIP 清单：前端资产为 `index-1aZZs5xp.js`，当前 `pnpm build` 为 `index-BwItlzAE.js`；包内无 Evidence `lookup_eligibility_operation.py` API/应用服务，Evidence 子树仅 8 个文件；包内 Migration 最高 `0051`，当前源码已到 `20261001_0052_evidence_parse_provenance.py`。当前分支提交 `25106908`。即旧 ZIP 完整但不含已验证的后续应用功能和 Schema，不能当作当前程序包或 UAT 产物。

## 方案与选择

- A：直接以旧 ZIP 做安装/验收。会遗漏新功能及 Migration，制造版本号相同却字节不同的假一致；禁止。
- B：保留旧 ZIP，使用其已固定的第三方/运行时/OCR/PG/Caddy 载荷为基底，另取当前源构建的后端 wheel 与前端 dist，仅替换应用归属路径并重算逐件 SHA-256 清单、新候选 manifest/来源提交与构建物哈希。选择此方案，仅产出新的 `NOT-FOR-RELEASE` 候选，不替代正式发行审查。
- C：从所有第三方原始归档完全重建。可作为最终可重复发行流程，但依赖已审来源、法律结论与较长重新验证；本轮不以其阻塞 B 的技术候选。

## 差异、风险、迁移与回滚

仅候选组装流程和非发行产物变化；不修改运行 API、ORM、Migration 内容、License 签名算法、正式安装或生产数据。新候选必须有不同唯一 ID/哈希并保存父 ZIP SHA、Git commit、wheel SHA、dist 文件哈希；原 `0.1.0.dev0` 内部版本不足以证明字节一致，须以候选唯一标识区分。替换时先验证 wheel 内容和预期包路径，拒绝路径穿越/重名/Secret/客户数据；不可静默保留已从当前应用删除的旧代码。未替换的第三方载荷逐项哈希必须与父包一致。Migration `0052` 必须随新 wheel 出现并在临时 PG18 空库及有数据升级中验证。构建输出继续 `release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`，不得写入真实密钥或证书。

回滚为弃用新候选并保留父 ZIP/清单，不在生产根执行覆盖或数据库回退。若当前 wheel 与嵌入式 Python 运行环境依赖不兼容，候选失败并回到构建前置，不借旧代码掩盖。Windows Server 2025、Debian 13、正式信任源、法律声明、AI 质量及全部 Release Gate 仍独立开放。

## 验证计划

1. 只用当前 Git 已提交源码构建 wheel/frontend dist，核验工作区与来源提交；不把未提交代码打包。
2. 在新唯一临时目标生成完整 ZIP/manifest/checksums，父包逐件只读校验；应用替换范围与未变载荷逐件比对，Secret/文件类型与路径安全审查。
3. 清洁解包并从随包 Python 执行 import、Migration 0052 空/有数据升级；在隔离 PG18 跑显式组合 Evidence 创建/资格/回查和已有 HTTPS/License 失败关闭烟测。
4. 仅上述技术证据齐全后标记 `NON_RELEASE_CANDIDATE_PASS`；发行许可、正式材料、三平台安装/升级、性能、AI/RAG、UAT 缺证据时保持不可发行。
