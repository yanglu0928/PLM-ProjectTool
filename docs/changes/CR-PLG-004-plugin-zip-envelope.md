# CR-PLG-004：Plugin ZIP Envelope 与安全只读检查边界

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / IMPLEMENTATION_IN_PROGRESS
- 适用WBS：PLG-01-A06
- 依据：冻结ADR-005、DM-04/API-03、CR-PLG-001/002/003、用户持续自主执行授权

## 问题

A02已有完整归档字节Ed25519 detached verifier，A03已有有界Manifest parser，A05已有包内publisher key resolver，但尚无正式归档Envelope合同，也没有证明待解析Manifest和EntryPoint确属被验签的同一ZIP。若分别接受调用方提供的Manifest与ZIP签名输入，会产生对象错配；若直接解压，则引入路径穿越、链接和资源耗尽风险。

## 决定与偏差

1. 正式开发包使用ZIP容器；唯一Manifest路径为ZIP根目录的 manifest.json，内容必须符合CR-PLG-002的 plm.plugin.manifest.v1。选择该名称与POC-08现有manifest.json惯例兼容，但其旧入口SHA字段不能升级为正式开发者签名。
2. 签名为包外detached Ed25519签名及明确 signer_key_ref；签名输入覆盖完整、原始ZIP字节，依CR-PLG-001绑定包SHA-256与key-ref。不得信任压缩包内自带公钥或签名身份。
3. 本WBS只做内存中的只读归档检查、Manifest解析、签名验证及entry_point存在性核对；不解压到文件系统、不保存、导入、安装、启动、持久化或授权插件。
4. 严格边界：压缩包不超过256 MiB；最多4,096个归档项；Manifest未压缩与解压后都不超过64 KiB；任一普通文件声明未压缩大小不超过512 MiB；全体声明未压缩大小总计不超过2 GiB；单文件压缩比不超过200:1。加密成员、重复/大小写折叠冲突路径、非规范POSIX路径、Windows设备保留名、链接/特殊文件、缺失/重复/非根Manifest及声明入口非普通文件均拒绝。
5. 目录项可省略；如存在，只允许规范相对目录名；文件与目录不可产生路径/大小写折叠冲突。ZIP中央目录和成员元数据必须有界；Manifest读取使用64KiB+1硬限制。

替代方案：
- 延用POC入口SHA字段：无法证明发布者身份，拒绝。
- 在压缩包内嵌公钥/身份：可由包作者自签自信，拒绝。
- 先解压后验证：验证前已写文件，增大攻击面，拒绝。
- 选定包外签名、受控包内公钥资源、内存有界检查。

## 影响、兼容性、迁移与回滚

- 仅新增application层只读检查Service及单测；本WBS不连接PluginPackage ORM、不改变DB Schema/API/外部文件格式，不执行解压或运行。
- 新格式是插件开发包输入合同；旧POC目录/manifest不会自动转换或被标记为正式可信包。
- 设定的压缩包上限尚无客户数据基线，依据首版单机/小团队插件包与安全封顶选择；超限时需新版本合同/CR，禁止静默放宽。
- 回滚只移除新增检查器及测试；无客户持久数据/安装包迁移。保持所有Plugin导入/安装入口关闭。
- Hosted测试使用内存合成ZIP和仅进程内签名key，不读取客户资料、不上传测试包artifact。只在GitHub hosted runner临时环境执行。

## 验证计划

- 合法包：根Manifest/真实EntryPoint/active合成签名通过；包字节或key-ref篡改失败；正式空keyring失败关闭。
- 恶意输入：坏ZIP、中央目录/大小/项数边界、加密成员、绝对/drive/UNC/回退路径、重复/大小写冲突、symlink/device、目录与文件冲突、Manifest缺失/重复/超限/坏schema、入口不存在/非普通文件。
- 后端全量、wheel、GitHub hosted PR集成链通过；A06仍为PASS_SCOPE_LIMITED，不外推安装/执行/Win11或Gate/Pilot/Release。


## 中央目录内存风险复核（编码提交前补充）

- 发现：Python zipfile 在创建 ZipFile 时会先解析并构造中央目录对象，之后调用 infolist() 才能检查数量。因此只在 infolist 后拒绝超过4,096项，无法阻止条目数量/额外字段驱动的前置内存消耗；256MiB归档字节上限不够约束条目对象开销。
- 修正设计：在打开ZipFile前，从归档尾部最大65,557字节定位并校验EOCD；拒绝多磁盘、ZIP64 sentinel、前置自解压数据、偏移/长度/注释不一致；先将总项数限制为4,096、Central Directory限制为8MiB，再进入zipfile。打开后重复核对实际项数和目录元数据。
- 选择该方案是为了保留Python标准库解析器，同时在对象创建前完成硬边界。备选“只依靠infolist后校验”未能限制前置解析成本，拒绝。ZIP64在当前256MiB/4,096项合同下无必要；未来若需支持必须由新CR放宽。
- 该保护属于已记录合同的具体化，不增加持久格式/API；相应单测覆盖EOCD项数/中央目录/ZIP64/多磁盘和偏移伪造拒绝。此补充在实现提交前写入。


## 首轮云端验收失败记录（2026-11-03，修复前）

- 首个A06实现提交80edd9f2cfe166c2b3cf9ff5e87ad7b780db5f41触发hosted run [41581198290](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41581198290)。前置PG18/前端/runner检查通过；后端3,902项中1个错误、1个失败，后续wheel/父包/A17/A34被跳过。
- 错误根因：Windows测试生成器构建成员名时将反斜杠规范成斜杠；Manifest测试值仍包含反斜杠，故Manifest parser按合同返回PLUGIN_INVALID_ENTRY_POINT，测试辅助函数仅捕获包检查错误，显示为fixture error。归档中未实际写入反斜杠成员名，该子例未验证目标分支。
- 失败根因：EOCD测试bytes literal包含过度转义的反斜杠文本，查找真实PK签名返回-1；该测试的伪造EOCD字段断言未执行。其他EOCD相关正向路径由主验收样例运行，但故障注入矩阵尚不完整。
- 目前证据未显示归档检查器绕过、路径逃逸或未授权执行；A06不标PASS。下一修正仅改测试夹具：对生成后的ZIP原始文件名字节将等长正斜杠替换为反斜杠（Manifest保留合法entry_point），并使用准确的PK\x05\x06 EOCD签名字节；然后重跑定向/全量hosted CI。
- 回滚策略不变：无DB/API/持久化，保持插件导入/安装/运行关闭。


## 第二轮hosted全量回归失败记录（2026-11-03，修复前）

- 第二轮run [41581853457](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41581853457) 中A06专项归档/EOCD用例未报失败；后端其余回归报1个既有测试失败（总计3,902项），导致wheel/父包/A17/A34跳过。
- 失败用例 test_capability_proof_locks_current_item_and_global_review 使用uuid.uuid4()生成12个值，并断言repr不包含固定子串“cccc”。一个随机UUID恰含该子串，proof repr只包含正常字段而没有隐藏敏感数据，该断言仍误报。此为随机夹具与过宽子串断言的false positive，不是本WBS产品实现缺陷。
- 预定修正仅限该单测：用确定性不含禁用标记的UUID集合替代随机UUID，让负向断言稳定且保留锁查询/返回结构验收。保留首轮两个A06 fixture根因记录。完成后重跑全量CI和集成链；在全量成功前A06保持未关闭。


## A06云端完整复验与关闭（2026-11-03）

- 代码及测试稳定化后的run [41582564698](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41582564698) 全13/13 jobs成功；后端3,902项全通过并构建wheel，前端、PG18/pgvector、父包构建/清洁解包/临时PG smoke、A35 handoff、A17 packaged PlanVersion flow、A34 offline replacement/manual restore均成功。
- A06的ZIP/EOCD与Manifest/签名/EntryPoint负例均随该后端全量回归通过。A17验证候选摘要为`ff223e20679361a37d33a6b215d0dc423d69b0f8c7de1e30830d66004bc74ba1`；A34演练摘要与恢复标记参见run 41582564698上传的证据artifact。
- 第二轮随机UUID误报仅调整既有测试fixture，未改变产品代码；首轮与第二轮失败及其原因继续保留为历史，不删除失败记录。
- WBS结论：`PASS_SCOPE_LIMITED`。不代表插件导入/落盘/安装/运行，不代表正式发布信任、Windows 11设备、Gate 3、Pilot或Release通过。没有客户数据、Secret或真实信任材料进入本验收。
- 运行位置：GitHub hosted Windows Server 2025 runner，工作区/隔离目录使用D盘；未在用户本机或C盘运行。
- 交付结果：`docs/progress/plg-01-a06-plugin-zip-inspector-result.md`。后续转至STATUS.md中的OUT-01-A01-P03，按其已完成的前置核查与CR-OUT-003实施。


## A06后续路线复核（2026-11-03）

上一版A06结尾指向OUT-01-A01-P03，依据当时STATUS行执行前置检查后才发现该P03已由提交e0b69bdcdc06765e5192d57fe84f924d30606958及run [41417503109](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41417503109)于2026-11-02完成。PLG-01-A01也已完成，因此按“持久注册/状态转换留待后续独立WBS”的原决定转入PLG-01-A07。更正记录和编码前边界见CR-PLG-005。
