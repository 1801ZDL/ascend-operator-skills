# Agent 安装与维护入口

本仓库提供 Ascend/Triton 工作方法和三个辅助工具。用户说“安装这个仓库”时，默认安装全部七个 skill 及其邻接资源；不把安装任务扩成算子实验或开发环境部署。

## 安装本仓库

1. 阅读 README 和 `install.py`，识别当前 Agent 的个人技能目录。已知定制目录时使用 `--target`；否则使用 `--agent codex|claude|opencode` 的对应预设。只有影响安装目标的信息仍不清楚时再询问。
2. 从克隆/解压的仓库运行 `python3 install.py <目标参数> --dry-run`；确认计划后沿用用户已有安装授权直接执行同一命令去掉 dry-run。不要因模板重复索取授权。
3. 用同一目标运行 `--check`。遇到已有同名内容、链接或本地修改时保留它，按报错解决；不自动删除或强制覆盖。
4. 报告版本、安装位置、七个 skill、检查结果和激活方法。当前平台未即时发现时提示刷新或新开会话；文件检查不等于已在 Agent 内完成调用。

没有 Python 时说明先决条件，使用用户选定的安装方式；不擅自改系统 Python。辅助脚本已随 skill 安装，不需要 pip。KG Key 可稍后配置，不阻塞安装其余内容。不要在安装时导入 Torch/Triton、查询 NPU、启动模型、运行编译器或修改 AGENTS.md/CLAUDE.md 等全局规则。

用户需要更新时，先获取并审阅新版本，再使用 `--upgrade --dry-run` / `--upgrade` / `--check`；卸载使用 `--uninstall`。不要自动拉取远端、启用后台更新或在多 Agent 目录重复安装。

## 修改本仓库

按当前用户目标修改，保持技能按需可用，不增加无条件查 KG 或整套实验的要求。私人 profile、凭据、原始业务数据、内部文档和本机路径留在本地。

源码/文档变化后运行 `python3 scripts/validate.py --write-manifest` 更新校验和，再运行 `python3 scripts/validate.py` 和必要的离线测试。技能规则变更按受影响场景评估，文件校验不代替实际行为验证。提交前执行 `git diff --check`，保持第三方来源和许可证说明。
