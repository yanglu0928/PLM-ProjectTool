# AUD-03-A06-A04-P03-A02-P01：Document owned审计存储Port

日期2026-09-26；Phase2；依据CR-AUD-002/ADR010、DEC206；前置0040已验。限定物理存储原语PASS，实际Worker数据库发布/下载未完成。

## Changed / Files

Document Application新增精确AuditFileCoordinate（仅PROJECT/DEPLOYMENT及非零ID）、AuditFileContent（完整32-byte Hash/0～128MiB size）和存储Protocol。不包含Locator/路径/Worker/Session，DTO和内容证明不授予权限。Adapter私有生成`generated/audit/deployment`或`generated/audit/projects/{id}`及对应temp区域；扩LocalFileStorage白名单正则复用原根目录/重解析点/大小写/普通文件inode与硬链接检查，不改变普通GLOBAL/PROJECT locators。

staging sink只允许bytes写入、有界并验证精确写入长度，写错误不可恢复为本次成功；正常退出flush/fsync/close，随后独立完整Hash/Size读回。异常保留私有部分文件不自动删除或重开；已有stage或final拒绝同ID新reserve，O_EXCL补充竞争保护。最终提升仍不可覆盖旧文件，只有新ID才能作为新generation。实际持久generation分配与绑定留Audit尝试Schema，不用file_id假称Job fencing。

内部inspect返回存储形状，STAGE_ONLY不是内容证明；new/final_only/linked_pair明确选择且Hash/Size重核，不盲自动修复。linked_pair仅同inode双硬链接，unrelated pair拒绝；最终损坏拒绝恢复。提升不是数据库结果发布，也不保证断电目录项durability；正式恢复/备份仍需实际环境验收。没有下载或物理清理删除Port。

普通上传扫描仍只temp/global和temp/projects，新审计temp区域不会被误识别为upload orphan。默认HTTP不挂载新入口，没有静态目录。无Migration/API/角色/依赖变更，head0040不变。

## Tests / Result

- 14项新增Windows11真实临时文件/异常测试：双Scope空和UTF8字节；Hash/Size误差不提升；排他reserve和final不覆盖、新ID独立；异常私有部分文件；小上限拒绝不多写；短写/非法类型/模拟ENOSPC及fsync失败；捕获写异常也不能成功关闭；真正hard-link后模拟unlink中断、同inode恢复；final-only完整读回/损坏拒绝、unrelated双文件不恢复；污染路径/非法坐标/普通扫描隔离；实际renderer空集合接真实staging sink→Hash读回→提升（来源DTO合成，无DB授权）。
- 后端897项无失败，2项既有Windows符号链接权限条件跳过。旧存储全部unit回归。模拟磁盘满不是实际满盘；小上限不是128MiB性能证明，现有重解析点跳过不能宣称该场景实测通过。
- 实际PostgreSQL固定capture→安全JSONL/manifest内存字节P01回归PASS（License合成，可信caller fixture）；旧普通FilePublish真实临时文件/数据库发布回归PASS。未把两项独立测试拼成完整审计Worker发布验收。
- 开发wheel 0.1.0.dev0成功：545796 bytes，SHA256 `44f287e9a453556aebc5a3e0f9c10bf639797d6eccf1874c29115392117457cd`；不是正式安装包。

## Known Issues / Next

公共caller-UOW元数据登记/查读/转换、Audit持久尝试与唯一结果、实际Root/acceptance/Queue/capture/当前权限/Lease/取消和短事务发布、下载再授权/HTTP仍待。Storage primitive只接受可信Owner调用，不自建UOW或做业务鉴权。文件提升后无结果不可下载；生产删除/真实目标账户ACL/128MiB和20并发/Server2025/Debian13/正式信任与质量/Gate3未验。下一项P03-A02-P02 Document owned元数据Port，再Audit尝试/结果Schema及Worker全链路。
