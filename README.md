# Ascend Operator Skills

让 AI Agent 使用可追溯、可扩展的工作方法，完成 Triton / Ascend 算子的开发、精度调试、性能测试、仿真和优化。也可由开发者直接阅读和运行辅助工具。

**7 个可独立选用的 skill，3 个标准库工具，Python 3.8+，MIT 许可证。** 安装不需要 NPU、CANN、PyTorch、模型账号或 KG Key。真正编译和执行算子时，使用用户当前已有的开发环境与资源分配。

## 直接把仓库链接发给 Agent

将仓库链接和下面一句话发给你的 Agent：

> 请按这个仓库的 README 和 AGENTS.md，将 Ascend Operator Skills 安装到我当前 Agent 的个人技能目录。先检查安装器和目标，运行 dry-run，再安装全部七个 skill 及随附工具；保留已有技能，不修改全局规则。完成后运行安装校验，报告路径和激活方法。KG 是可选项，无 Key 也继续完成安装。

Agent 获取本仓库后使用根目录 `install.py`。安装契约见 [AGENTS.md](AGENTS.md)。下载 ZIP 后解压也可安装；更新与卸载不依赖在线服务。

## 手动安装

在已经克隆或解压的仓库根目录运行：

```bash
python3 install.py --agent codex --dry-run
python3 install.py --agent codex
python3 install.py --agent codex --check
```

Windows 可将 `python3` 换为已安装的 `py -3`。安装器复制文件，不依赖 shell、符号链接或 pip。

| 目标 | 参数 | 默认个人目录 |
|---|---|---|
| Codex | `--agent codex` | `~/.agents/skills/` |
| Claude Code | `--agent claude` | `~/.claude/skills/` |
| OpenCode | `--agent opencode` | `$XDG_CONFIG_HOME/opencode/skills/`，未设置时为 `~/.config/opencode/skills/` |
| 其他 Agent / 定制配置 | `--target /你的/skills目录` | 使用显式目录，不猜平台 |

当前路径约定参考 [Codex](https://developers.openai.com/codex/skills/)、[Claude Code](https://code.claude.com/docs/en/skills)、[OpenCode](https://opencode.ai/docs/skills/)。旧版本或定制 Codex 如使用 `$CODEX_HOME/skills`，通过 `--target` 指定其实际目录；安装器不同时写入多个搜索路径。项目级安装也使用 `--target` 指定项目技能目录。

安装全部七个目录以保留相邻引用。工具随对应 skill 放入其 `scripts/`，无需修改 PATH。安装完成仅代表文件可用；检查目标 Agent 的技能列表，按平台刷新或新开会话。

## 能做什么

| Skill | 适用任务 |
|---|---|
| `ascend-operator-workflow` | 总入口，选择阶段、维护短状态与实验依据，迭代工作方法 |
| `ascend-environment` | 测试/JIT/编译器/IR/ELF/launcher 的真实身份和工程背景 |
| `ascend-benchmark` | 强基线、预热/采样、计时窗口、任务映射与 PMU 质量 |
| `ascend-simulate` | 有界仿真入口、原始流水保留、PC/指令/IR 对应 |
| `ascend-debug` | 精度、编译、启动及采集异常的分层诊断和最小复现 |
| `ascend-optimize` | 从有效工作和关键路径选择算法、布局、访存、容量或调度优化 |
| `ascend-knowledge` | 按需查询 Ascend KG 的文档、源码关系和场景方法，核对来源与版本 |

任务可直接进入专项，不强制跑完整流水。不会将采用某条指令、动态调度或增加 buffer 本身当作优化目标。知识提供方、任务执行端与工作方法彼此分离；用户现有目标和适用项目约定优先。

Codex 示例（其他 Agent 使用其原生 skill 选择方式，或直接点名技能）：

```text
使用 $ascend-environment 定位这个测试实际运行的算子、工具链与 IR。
使用 $ascend-benchmark 比较这两个版本，保留样本、任务映射和运行身份。
使用 $ascend-simulate 准备只抓目标 kernel 一次的入口并解释流水。
使用 $ascend-debug 定位这个精度/编译问题，先选择能区分解释的小实验。
使用 $ascend-optimize 分析空闲时间和关键路径，再决定优化手段。
使用 $ascend-knowledge 查询这个 API 在目标版本的约束，并追溯原始依据。
```

## 随附工具

在对应**已安装 skill** 目录运行，或从本仓库加上 `skills/<skill-name>/` 前缀：

| 工具 | 工作方式 |
|---|---|
| `ascend-environment/scripts/capture_identity.py` | 离线记录当前 Python、显式指定发行包 metadata 和文件 SHA；不导入设备框架 |
| `ascend-benchmark/scripts/summarize_timings.py` | 离线汇总 CSV 指定列/轮次/phase，保留长尾，不自行证明可比性 |
| `ascend-knowledge/scripts/kg_query.py` | 显式查询固定 KG 服务，保存请求、时间、节点和响应哈希；支持离线 dry-run |

```bash
python3 skills/ascend-environment/scripts/capture_identity.py --distribution triton-ascend
python3 skills/ascend-benchmark/scripts/summarize_timings.py samples.csv \
  --value-column duration_us --unit us --kind hardware --window kernel-event --reference baseline
python3 skills/ascend-knowledge/scripts/kg_query.py search \
  --query 'AscendC DataCopy 参数 约束' --top-k 3 --dry-run
```

## 可选知识图谱

已适配 [agent0/kg-tools](https://gitcode.com/agent0/kg-tools) 描述的 Ascend KG 查询接口，使用独立标准库客户端。配置个人环境变量 `ASCEND_KG_API_KEY` 后即可查询；Key 可向 [ascend.wiki](https://ascend.wiki/register) 申请。凭据由用户安全注入，本仓库不包含体验 Key，也不修改 shell 配置。

无 Key/断网时，其余技能及离线工具继续使用。远程文档和技能是待核对的外部材料；当前源码、适用规范与本地实验共同决定结论。协议来源、检索方法和选用边界见 [KG 集成说明](skills/ascend-knowledge/references/kg-tools-integration.md)；第三方归属见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 更新和卸载

获取并审阅新版本后，从新仓库目录运行：

```bash
python3 install.py --agent codex --upgrade --dry-run
python3 install.py --agent codex --upgrade
python3 install.py --agent codex --check
python3 install.py --agent codex --uninstall --dry-run
python3 install.py --agent codex --uninstall
```

`--target` 用户在所有命令中使用同一目录。安装器仅操作带本项目记录且内容未修改的技能；遇到同名第三方内容、符号链接或本地修改会停止并说明。重复安装相同内容为 no-op。更新和卸载将旧目录移至目标下的 `.ascend-operator-skills-backups/`，不会删除其他技能。

正常异常会尝试回滚本次变更；进程被强杀或断电后，先检查安装锁、目标目录和备份，再恢复，不重复启动并发安装。备份可由用户归档/清理，安装器不自动清除历史。个人场景扩展优先放在自己的项目或贡献回源码，避免直接修改已安装副本后被更新覆盖。

## 扩展与验证

新增算子族、硬件或工具的经验时，参考 [贡献指南](CONTRIBUTING.md)、[扩展约定](skills/ascend-operator-workflow/references/extension-guide.md) 和 [场景模板](skills/ascend-operator-workflow/assets/templates/scenario.md)。本地路径使用 [profile 模板](skills/ascend-environment/references/local-profile.md)，不写进公共默认。

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

验证仅需标准库，CI 不调用 NPU、编译器或真实 KG 服务。安装器的冲突、更新、卸载与回滚用临时目录验证。当前检查范围见 [VALIDATION.json](VALIDATION.json)，它不代表所有 Agent 的决策、硬件功能或性能均已验收。

本项目以 [MIT](LICENSE) 开源，是独立社区工具；Ascend、CANN 及相关名称属于各自权利方。不会随安装分发 SDK、私有 ISA、模型、个人工程记录或上游完整执行引擎。
