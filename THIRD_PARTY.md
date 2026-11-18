# 第三方来源与边界

本仓库原创技能、辅助脚本与安装器采用根目录 [MIT 许可证](LICENSE)。不分发 CANN、Triton、AscendNPU-IR、LLVM、设备驱动或其二进制，也不声称代表这些项目。

## Ascend KG / kg-tools

- 来源：[agent0/kg-tools](https://gitcode.com/agent0/kg-tools)。
- API 契约审阅提交：`270da9a0ed92296977cde307ec8caab5895b3c23`，2026-11-17。
- 用途：独立实现客户端调用公开描述的 search/source/cypher/health 接口；原始链接见 [KG 集成说明](skills/ascend-knowledge/references/kg-tools-integration.md)。
- 本仓库未复制其代码、完整规则、执行引擎或体验凭据。审阅树未找到独立 LICENSE 文件，不据此推定其内容可按本仓库许可证再分发。
- 远程服务与节点内容由各自提供者维护，可能要求 API Key、有配额或发生变化。查询结果的原始资料、许可和适用性需分别核对；本仓库许可证不覆盖服务数据。

## Agent 技能约定

SKILL.md 与邻接资源的组织参考开放技能格式及 Agent 文档：[Agent Skills](https://agentskills.io/)、[Codex](https://developers.openai.com/codex/skills/)、[Claude Code](https://code.claude.com/docs/en/skills)、[OpenCode](https://opencode.ai/docs/skills/)。安装器支持对应个人目录预设，未包含这些产品的客户端或 SDK。

品牌名称仅用于说明兼容对象。用户对其实际开发工具、凭据和设备保持独立管理。
