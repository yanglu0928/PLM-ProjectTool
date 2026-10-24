# PLT-PKG-01-A09-P48-A02：当前候选第三方材料继承核查

日期：2026-10-02；Phase 2；结果：`LICENSE_EVIDENCE_INHERITANCE_PASS / LEGAL_REVIEW_OPEN`。

编码前检查：输入 P45 固定父包、P47 当前非发行 ZIP、P43/P45 历史审阅材料及 P48-A01 发行阻断。任务只审计打包载荷/声明归属，不改业务模块、实体、API、权限、Migration、正式安装或客户数据。验收为两个 ZIP 完整 SHA、父/子清单/库存同一性、后端依赖声明、原生 OCR 映射与正文身份及法律标志；风险是将“材料相同”误记为“义务满足”，因此输出明确保留审阅缺口。

新增只读工具 `tools/audit_current_app_license_inheritance.py` 与合成测试，真实固定包退出0，定向2/2通过。结果：父 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，当前 SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`；20,573项非应用文件名称/清单哈希与父包相同，`third-party-inventory.json` 原字节相同；自有后端 `METADATA` 版本及18条第三方依赖声明无差异；105个第三方 Python 分发包仍为 `REVIEW_REQUIRED`；原生 OCR 61映射引用42份正文，映射/文本哈希匹配继承清单。错误包 SHA 或变更保留载荷在测试中失败关闭。

输出[当前应用审阅差异稿](../release/THIRD-PARTY-NOTICE-REVIEW-DRAFT-CURRENT-APP.md)，不追写[P45 历史草案](../release/THIRD-PARTY-NOTICE-REVIEW-DRAFT-P45.md)。当前产品级 LICENSE/NOTICE 仍缺，前端 dist 虽更新但其第三方组件与侧载最终对应关系还需单独审阅；即使所有旧证据可读取，也不等于完成法律签核。`legal_clearance=false`、`release_eligible=false`。兼容性：仅审计工具/文档；升级：无迁移；回滚：弃用本次审计稿而保留两个固定候选。下一独立项准备正式信任与安装验收的可执行输入，法律审结仍需有权人员。
