# kg-tools 接入、使用与维护

审阅日期：2026-11-17。上游：[agent0/kg-tools](https://gitcode.com/agent0/kg-tools)，审阅提交 `270da9a0ed92296977cde307ec8caab5895b3c23`。这里只适配其查询契约，接口和服务覆盖会变化。

## 为什么采用独立知识层

| 方式 | 本次判断 |
|---|---|
| 将上游全部规则放进现有六个 skill | 内容重复，任务触发面过宽，后续更新难保持一致 |
| 直接运行上游 Codex 安装器 | 本次未采用；审阅版 `install_codex()` 向运行目录的 `AGENTS.md` 写便携指针及主 skill，已有文件走覆盖询问；`--force` 可替换它 |
| 复制完整上游 skill/执行引擎 | 本次未采用；其任务级流程、常驻规则和推理服务调优引擎超出知识检索需求 |
| 独立 `ascend-knowledge` + 现有专项按需引用 | 本次采用；只维护一处查询、来源和失败处理，原实验工作流独立可用 |

审阅版上游主 skill 包含广泛强制查 KG、首次多份指南、自动更新检查、执行与多 Agent 编排等要求；适合选择整套上游工作方式的使用者。本适配层没有继承这些任务级要求，也没有把其具体机器经验升级为所有芯片的规范。

审阅树未找到独立 LICENSE 文件；本包不复制分发其脚本、engine 或完整说明。客户端为本包独立实现，事实与协议来源如下：

- [README](https://gitcode.com/agent0/kg-tools/blob/270da9a0ed92296977cde307ec8caab5895b3c23/README.md)：服务位置、配置和支持的 Agent。
- [检索手册](https://gitcode.com/agent0/kg-tools/blob/270da9a0ed92296977cde307ec8caab5895b3c23/skills/ascend-kg/references/retrieval.md)：请求字段、节点正文边界、图查询。
- [安装器](https://gitcode.com/agent0/kg-tools/blob/270da9a0ed92296977cde307ec8caab5895b3c23/install.sh)：`install_codex()` 的目标和覆盖行为。
- [场景路由](https://gitcode.com/agent0/kg-tools/blob/270da9a0ed92296977cde307ec8caab5895b3c23/skills/ascend-kg/references/skill-routing.md)：分类索引和配套资源。

## 配置与自然语言接入

此 skill 和 `kg_query.py` 随技能包安装，Python 3.8+ 标准库即可运行；无需再克隆上游或安装 NPU 环境。

服务为 `https://ascend.wiki`，认证头 `X-API-Key`，读取环境变量 `ASCEND_KG_API_KEY`。专属 Key 可在 [服务注册页](https://ascend.wiki/register)申请。不要把 Key 放在聊天、版本库、命令行参数或结果 JSON 中；使用当前平台的安全环境注入。客户端不修改 shell 配置。

用户没有 Key 时，说明外部查询暂不可用即可，继续本地任务。上游有公开体验凭据，但本包不内置或自动使用；需要体验时用户可按上游当前说明选择。本次开发的服务冒烟如使用公开体验凭据，会在验证记录中明确，与用户自己的凭据分开。

给未来 Agent 的安装描述可以是：

> 在我的个人 skill 目录安装 Ascend 技能包中的 `ascend-knowledge`，保留它的 scripts、references 和其他专项之间的相对链接。只做知识检索接入，使用我已配置的 ASCEND_KG_API_KEY；不要运行 kg-tools 的全局规则安装器或把上游整套指令写入 AGENTS.md。安装后先 dry-run，再用一个公开 API 问题测试；无 Key 时报告未完成联网测试，保留本地工作流可用。

如果用户明确要完整原版，先按当前 README 核安装目标和更新差异，保留目标规则/运行状态的原件，再选择对应 Agent 的安装方式。复制该任务到隔离目录或个人 skill 目录比在重要工程根目录直接运行安装器更容易审查。已有授权足够时直接完成对应范围，不因本说明另设审批。

## 查询契约

`kg_query.py` 仅访问固定 HTTPS 主机，不接受任意服务 URL，拒绝自动重定向，保留系统 TLS 校验和代理行为。每次调用最多一个请求，无自动重试；`--timeout` 默认 15 秒，是 socket 超时，不是严格总墙钟上限；需要严格限时可使用当前执行器的总超时。默认响应上限 2 MiB，超限报告失败，不执行返回的代码。

| 命令 | HTTP 接口 | 发送内容 |
|---|---|---|
| `health` | GET `/health` | 无正文 |
| `search` | POST `/search` | query、top_k，及显式选择的 file_type/source_repo/with_neighbors |
| `source` | POST `/source` | node_id、max_length |
| `graph` | POST `/cypher` | template、params 对象；不是原始 Cypher 执行器 |

只发送当前请求的显式字段，无自动错误日志扫描或源码读取。所有正文以 UTF-8 编码；中文 ID 从结果程序化原样传递。输出 JSON 使用 ASCII 转义，避免旧 Windows 终端编码改变 ID。

每次输出记录 UTC 时间、接口、实际请求、HTTP 状态、响应 SHA256 和解析后的响应。`response_sha256` 针对原始响应字节；输出中的匹配凭据会被脱敏，因此不能把重新序列化后的 JSON 当成同一原始字节。客户端不落 Key、不读 shell 配置，也不收集本机环境信息。用户可将输出保存到任务证据目录；接口返回的节点字段原样保留，不猜 schema 中缺失的来源。

```bash
python scripts/kg_query.py health
python scripts/kg_query.py search --query '507015' --top-k 3
python scripts/kg_query.py search --query 'Triton Ascend 数据布局 转换' --source-repo triton --top-k 3
python scripts/kg_query.py graph --template node_detail_by_id --params-json '{"id":"从结果取得的ID"}'
```

`search` 中 `with_neighbors` 默认由服务端决定，客户端只有指定 `--neighbors/--no-neighbors` 才发送它。不要添加 `path_trace` 等未声明字段。审阅版说明 `file_type=error_code` 覆盖不足，故错误码先裸码搜索；这一点属于服务当时状态，并非永恒无结果保证。图模板及其参数必须来自当前 API 文档，例如按需取 `kg-query-guide-full`；服务端模板校验仍是最终准入。

`/skill/search` 在审阅版有空结果的历史说明，本适配优先使用 `/source` 的分类索引。可以先读取 `kg-skill-index-master`，若目标分类已知则直接读取对应分类，避免重复预载所有指南。分类/技能名来自当前返回内容，不能用旧名称失败推断整个领域没知识。

## 各专项如何使用

| 专项 | 值得查询的缺口 | 必须回到本地核对的内容 |
|---|---|---|
| environment | API/版本支持、编译阶段和跨仓入口 | 实际导入、工具路径/提交、metadata、当前头文件 |
| benchmark | profiler 字段、PMU 定义/支持表 | task 映射、当前 SoC/exporter 能力和真实样本 |
| simulate | CLI/日志字段、同步和指令相关资料 | 当前 `--help`、ELF/PC、动态 ID、原始时间与完成点 |
| debug | 错误码、接口签名、同症参考 | 第一失败阶段、当前调用、最小复现和修复回归 |
| optimize | 算子/布局/访存方法与参考实现 | 真实关键路径、资源所有权、强基线及功能/性能 |

例如查 TRY_WAIT：可以查询指令、模式、counter 和同步资料，但要区分 Ascend C 高层接口、HIVM op 和实际 ISA 指令。泛化的队列同步描述不足以证明指定 silicon revision 上 WAIT→TRY 的可见性；查不到正式条款时继续保留未证明项。

## 结果判读与失败

- **相关性**：先看标题、source_file、正文、产品和版本，不能把高 score 当权威或正确概率。KG 索引的是不同来源，引用应追溯实际原页/源码；能提供原始链接时一并给出。
- **降级或截断**：实际服务可能返回 search 的 `degraded`/`cached`、source 的 `truncated`/`size` 等字段；这些原样保留在 `response`。`status=ok` 只表示取得可解析响应；截断可能漏掉限制段落，按需增加 max_length 或取原页，不能当完整文档。cached 也不提供本机工具版本已匹配的保证。
- **Code 正文缺失**：节点可能只有位置，`source` 404 不等于代码不存在。转查已有授权的本地源码，或按来源获取公开上游文件；不默认克隆整套知识图谱。
- **空结果**：用 API 原名/错误裸码、中英文或症状改写；仍无相关命中时转当前源码、手册或实验。历史“零命中”不是永久否定。
- **缺 Key / 401 / 403**：不回显凭据、不自动换公共 Key；报告配置/权限状态，保留本地路径。
- **429 / 超时 / 5xx**：报告具体类别；由任务按需要决定稍后重试，避免每个专项同时重试造成放大。
- **非 JSON / schema 变化 / 太大 / 重定向**：保留状态，核当前接口。不能把 HTTP 200 单独当“查询有用”。
- **来源冲突**：同时保存版本和条款；当前工具的实测只能证明本次观察，不能静默改写正式 ISA。缺来源的知识图谱摘要只是线索。

## 维护边界

本层只替换知识提供方，不改变实验执行端、共享服务器的资源准入、个人凭据边界或中央调度系统。服务离线时原六个 skill 可独立工作。已有 MCP 或新的本地镜像可替换传输，保留问题最小化、节点来源和适用性核对即可。

更新上游时复查提交、接口字段、安装行为和节点结构，不做每会话自动拉取或规则重写。形成跨任务有效经验后，按 [扩展约定](../../ascend-operator-workflow/references/extension-guide.md) 合并适用范围和证据；无需复制整份远程 skill 到公共默认。
