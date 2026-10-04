# PLT-PKG-01-A09-P47-A03：当前应用真实非发行候选与清洁解包

日期：2026-10-02；Phase 2；结果：`NON_RELEASE_CURRENT_APP_CLEAN_EXTRACT_PASS / PACKAGED_IMPORT_PASS`。

编码前检查：CR-PKG-008 先行、P45 父候选 SHA 已固定、P47-A02 构建器测试通过且代码已提交；范围仅 Windows 11 非发行候选与独立验证工具，不改产品 API/ORM/Migration、现有安装根/服务/数据库、原 ZIP。模块为打包/验证，数据实体及权限无变化；验收为干净提交来源、父包逐项不变、全量新清单/安全路径/唯一新包、独立解包读回、随包应用导入。风险为开发版号相同但字节不同、许可尚未放行及未完成运行烟测，须保留唯一 ID/哈希与不可发行标记。

在干净 HEAD `6d731177aacb1cfd1ae57fa01ce99275fea49e24` 上重建后端 wheel `d6f4cf581e843eb3619a218a7cbbd07d85b7cd633b376847738903888a221e58` 与前端 dist（`index-BwItlzAE.js`、`index-LTvnm9Te.css`）。从 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98` 的固定父 ZIP 派生新 ZIP：`artifacts/package-prep/windows11/current-app-candidate-f88bace1fcde/NOT-FOR-RELEASE-windows11-current-app.zip`（Git 忽略区，未上传仓库），652,186,749 字节，SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`。保留父包非应用载荷20,573项，输出21,178项；构建器对父、输出逐件哈希与清单检查均退出0。构建输入 wheel/dist 紧接干净 HEAD 在本机重新生成，其自身 SHA 固定；目前未证明跨机器可重复构建。

新增独立暂存工具：先核对新 ZIP 指定 SHA、安全路径、全集与不可发行字段，再在全新直接 ASCII Temp 子目录 `C:\Users\17231\AppData\Local\Temp\plm-current-app-stage-db7508e42667` 解包21,178载荷＋3元数据；解包时逐件哈希，完成后通用验证器再独立读回全量哈希/文件全集，最终复查源 ZIP SHA；真实命令退出0。包内 `payload/runtime/python.exe -I -B` 导入 `plm_assistant`、Evidence 原操作号回查模块并从已解包路径确认迁移 `20261001_0052_evidence_parse_provenance.py` 存在，分发版本为 `0.1.0.dev0`，退出0。新失败关闭定向单元1/1，通过错误 SHA/复用目标拒绝；原验证器仅增加新候选 kind。

本结果仅证明新候选文件完整性与包内 Python 导入，**不证明**随包 PG18 空库/有数据迁移、HTTPS/License 生产链、正式安装/升级、浏览器交互、第三方发行法律结论、正式信任材料、Windows Server 2025/Debian 13、AI 质量、UAT 或 Gate 3。`release_eligible=false`、`legal_clearance=false`、`installation_performed=false`、`services_changed=false`、`database_started=false`。下一项 P47-A04 在一次性隔离资源执行真实随包迁移及 HTTPS 烟测；回滚为弃用此新 ZIP，历史 P45 候选不变。
