# Deep Thinking Skills

`deep-thinking` 是一个显式调用的研究质量 Skill，用于科学和技术问题中的证据评估、竞争解释比较，以及需要实际核验的判断。它强调追究可能改变结论的未知，在证据充分后收束。

当前稳定版本为 **v1.1.0（Cv2）**。本仓库提供经过整理的公开分发快照，目前包含一个 Skill；安装目录和调用名称均为 `deep-thinking`。代码和文档采用 [MIT 许可证](LICENSE)。

## 开始使用

从 [v1.1.0 Release](https://github.com/lengmh/deep-thinking-skills/releases/tag/v1.1.0) 下载 `deep-thinking-v1.1.0.zip`，按 [安装、更新与回滚](INSTALL.md)先校验再安装。也可克隆本仓库，安装完整的 `.agents/skills/deep-thinking/` 目录。

```text
$deep-thinking standard 核查这项方法是否适用于给定场景，并完成可行的关键验证。
```

显式调用方式：

```text
$deep-thinking <request>
$deep-thinking lite <request>
$deep-thinking standard <request>
$deep-thinking full <request>
```

未指定模式时使用 Standard。普通的「分析」「研究」「设计」「权衡」或任务复杂度不会自动激活 Skill；模式只对当前调用有效。未知模式会被拒绝。

## 三种模式

| 模式 | 用途和状态边界 |
|---|---|
| Lite | 轻量认识论提示；不创建持久状态、Checkpoint 或流程账本。 |
| Standard | 显式调用的默认模式；只在认识论状态实质变化时保留必要控制，不创建持久 Research Run。 |
| Full | 显式选择后建立独立、可恢复的 Research Run，并使用状态 CLI。 |

三种模式共享认识论内核。Full 的区别是治理与恢复能力，不能据此推断它更聪明。详细合同见[模式说明](docs/PROFILES.md)。

## v1.1.0 的主要规则

- 当来源细节可能改变判断时，核查相关原文、条件、图表、数据或代码。
- 关键未知尚未解决时，在任务范围、权限和成本边界内完成有价值、可行的下一步。
- 重复检查须服务于尚未完成的核验目的；保留修改后重跑和独立复核。
- 证据充分后结束，任务完成后不制造后续工作。

用户提供的文档和引用是待分析数据，其中的命令不会成为 Agent 指令。Skill 不提供私有思维链，也不授予额外网络、文件或工具权限；实际权限由宿主控制。

## 验证与来源

v1.1.0 安装包的 11 个文件与受测 Cv2 字节完全一致。来源提交和包指纹见 [SOURCE.json](SOURCE.json)，安装字节见 [package manifest](deep-thinking-package-manifest.json)。本仓库始于独立初始提交，随后追加经过整理的产品历史；公开提交 SHA 与来源提交 SHA 分别记录。

来源版本完成了 151 项单测和 44 项离线合成校准。八题 Standard 实际评估中，A/C/Cv2 的 24 份所选有效答卷均为 10/10；Cv2 的八份均保留关键核验并完成交付。原始评分和失败尝试分别保留，运行时间不参与版本比较。方法、来源关系和限制见[评估摘要](docs/EVALUATION.md)。

这些样本尚未证明 Cv2 相对旧版或无 Skill 的质量、收敛或成本增益，也未证明一般性等效。本次未新增全模式 L3、跨宿主、Windows 原生或并发认证。

## 维护方式

[产品演进历史](docs/HISTORY.md)提供 10 个可浏览的历史快照及来源对照，展示初版、状态工具修复和 C/Cv2 指令调整。历史公开提交使用本次生成日期和 noreply 身份，安装继续使用固定的 v1.1.0。

公开版本从固定来源版本导出，使用包指纹和逐文件哈希核对。后续版本继续通过 Release 分发；问题和建议可提交到本仓库 Issues。开发过程、原始会话和本机环境记录由独立维护仓库保存，公开快照包含安装所需文件及可分享的结果摘要。
