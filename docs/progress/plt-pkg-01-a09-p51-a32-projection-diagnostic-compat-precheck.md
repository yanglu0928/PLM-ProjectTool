# PLT-PKG-01-A09-P51-A32：父包诊断工具与A17应用投影兼容编码前检查

- 日期：2026-10-30
- 前置：A31父包README命令专项作业在hosted run 40992356658/job 123860726604通过；同一workflow的A17组合job 123861061645因 payload/check-startup.ps1 未映射而失败。
- 单一目标：让严格的当前应用布局投影显式排除且仅排除父包级只读启动诊断脚本，同时继续完整验证源候选清单/哈希，并对其他任何未知payload族保持拒绝。
- 根因证据：父包候选manifest/hash清单将 payload/check-startup.ps1 作为打包工具列入；smoke_current_app_packaged_https.py 在源完整性校验后把全部hash路径交给 exact_mapping，后者依赖 rehearse_windows_unified_pg18_layout.py:target_name 的应用文件映射，按设计拒绝未声明文件族。该脚本属于父包启动诊断，不属于被映射到长期应用布局的服务运行时。
- 范围：仅修 tools/smoke_current_app_packaged_https.py 的父包→当前应用投影输入集与计数语义，并增加定向单测；不改变父包文件、不修改通用映射器、不修改业务API/Schema/License、不放宽未知文件拒绝，不读取真实Secret、不启动正式服务、不写安装路径。
- 设计：源candidate仍须先通过完整manifest、所有payload哈希、文件集及archive摘要检查；只在投影层从映射集合中排除确切路径 payload/check-startup.ps1。应用布局映射数及投影验收数使用排除后的数量；任何其他未映射路径仍由既有 exact_mapping 拒绝。保留原完整源payload计数用于输入完整性断言。
- 验收：单测验证精确排除及投影计数；未知父包路径仍拒绝；hosted Windows完整workflow重新构建父包，A31父包smoke与A17 PlanVersion packaged Edge/HTTPS/PG全流程均通过；父包源哈希完整、候选未变、合成身份、临时进程/目录清理；不把Windows 11、正式信任、Gate、Pilot或Release标为通过。
- 风险：精确排除路径如未来被错误复用，可能导致该文件不进入应用布局；以独立常量、名称精确匹配、源包仍全量校验和A31父包检查降低风险。任何第二项排除都需修改本任务验收和记录。
- 迁移/回滚：无数据/API/Migration变更；回滚本任务投影过滤和对应测试即可，父包诊断脚本及A31已完成验收不需回退。
- 编码前结论：失败属于A30/A31新增父包诊断文件与A17严格应用投影的已证实组合兼容缺口。任务边界可独立修复，执行前置检查已记录；现进入仅本项代码/测试及hosted验收。

