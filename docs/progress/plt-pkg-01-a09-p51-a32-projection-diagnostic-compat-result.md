# PLT-PKG-01-A09-P51-A32：父包诊断工具与A17应用投影兼容验收结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（组合云端验证通过；非Windows 11实机或正式发行）
- GitHub Actions run：https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40995913354
- 验证提交：2e20a1f5f907ae88e5f194d1c2196fe1657bc2e5；全workflow 10/10 jobs success。
- 运行环境：GitHub hosted Windows Server 2025；项目候选解包/服务数据库临时目录在D盘RUNNER_TEMP，本机未执行项目代码。
- 定向测试：新接入CI的应用投影单测5/5通过；其中精确排除payload/check-startup.ps1，保留payload/future/unknown.bin并由严格exact_mapping拒绝。后端3,849项回归通过。
- 父包复验（job 123871658387）：20,119个payload，ZIP SHA-256 349e893aee3884c7814cf6c2801382f4ba39bf019ca9ba934244edbca97fcb9d；README父包根目录PowerShell 5.1诊断输出BLOCKED、exit 2、release_eligible/legal_clearance=false、stderr空；四类篡改输入拒绝，A29七类守门矩阵通过；没有产品监听；PG18.6/pgvector0.8.6临时生命周期及清理成功。
- A17组合复验（job 123871991799）：Edge/HTTPS/临时PostgreSQL PlanVersion链29次API调用成功；状态IN_REVIEW，WBS/requirement/validation=(2,2,1)，Review/Round=IN_REVIEW，decisions=0，synthetic_identities=true，current-app候选20,113文件，结果PASS_LIMITED。
- 偏差关闭：首次A31组合run因严格投影器未声明父包级check-startup.ps1失败；A32仅在应用投影层精确排除此脚本，源父包仍完整manifest/hash校验，所有其他未知payload仍失败关闭。潜在加密篡改单测波动在两轮后端全量复验中未重现，本WBS未改动该独立测试。
- 无业务API、数据模型、DB Schema、Migration或License机制变更。正式信任锚、服务账户/Vault/ACL/TLS、离线安装升级、Windows 11实机和用户UAT仍待；Pilot/Gate 3/正式Release保持NOT_READY。
