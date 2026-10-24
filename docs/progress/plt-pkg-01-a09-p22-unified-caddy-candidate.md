# PLT-PKG-01-A09-P22：Windows统一+PG18+Caddy非发行候选

日期：2026-10-01；状态：`NON_RELEASE_UNIFIED_CADDY_INTEGRITY_PASS / INSTALLATION_OPEN`。依据`CR-PKG-005`、P15与P19～P21；旧P15 ZIP Hash/历史保持不变。

编码前检查：Phase2/Gate3开放；输入P15固定ZIP SHA-256 `c54a7862872d402a6c9763287a508dc63dd602049f93aa6097e5a8e8e0766ef2`、官方Caddy v2.11.4四资产/Apache-2.0许可/源码/SBOM、P21已验证的Host/API/SPA配置。仅建新非发行包、无业务实体/API/权限/Schema/Migration改动；不动正式安装根、SCM、数据库或客户证书。验收：原21,103件+7项Caddy输入逐件Hash、顶层清单完整与独立读回、公开源码/许可位置、无新TLS私钥、发行门禁关闭。风险：NOTICE/对应源码法律审查不限于Caddy，模板未目标渲染，旧包本身发行阻断均继续。

新增`deploy/windows/Caddyfile.template`，外部域名、证书/密钥路径、API端口和前端根以显式占位表示；正式证书及私钥不得入包。新增`tools/build_windows_unified_caddy_candidate.py`从固定P15逐件复制21,103项，再加七项：`caddy.exe`、官方README/Apache-2.0 LICENSE、官方Windows SBOM、发布checksums、含vendor的buildable source归档和模板。新包顶层重新生成payload Hash、嵌套原第三方库存+Caddy来源/审查状态、非发行manifest（`legal_clearance=false`、无安装/服务/正式TLS）。新包位于Git忽略的`artifacts/package-prep/windows11/unified-caddy-candidate-6d171039204b/NOT-FOR-RELEASE-windows11-unified-pg18-caddy.zip`，639,617,127字节，SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`，载荷21,110件。构建写入中及ZIP成品逐件Hash通过。

首次构建在写载荷前发现构建器把旧审计工具的casefold路径键与ZIP原始大小写直接比较，误拒21,103项；固定原清单大小写映射与casefold身份后，从全新随机目录重跑。首次生成的22字节空ZIP及目录经内容/路径确认后移除（可由固定来源重建）。新增独立`tools/verify_windows_unified_caddy_candidate.py`固定整包字节/Hash、来源与七项身份、许可库存审查状态、无新增证书私钥，重读21,110项PASS；定向单元4/4。P15固定ZIP及Caddy官方输入均再核未变。

此项只是装配与完整性，不是安装器或可用程序包。未验证清洁解包后的Caddy模板渲染/目标账户/ACL/SCM/正式证书/License、原包完整许可/源码/真实质量、Windows Server2025、Debian13或Gate。`release_eligible=false`。下一项P23以全新ASCII临时目录清洁解包并逐件回读，再渲染仅合成证书的模板做Caddy validate/回环烟测。回滚弃用新非发行ZIP及构建器，保留旧P15与冻结API/Schema。
