# 产品历史

以下 10 个版本记录了 `deep-thinking` 从初版到 C/Cv2 的主要变化，可通过公开提交查看文件和比较差异。

## 版本对照

表格按来源版本的作者日期排列。完整 SHA、精确日期、包目录树和逐文件 SHA-256 见 [`history.json`](history.json)。

| 序号 | 来源日期 | 产品变化 | 公开提交 | 来源提交 |
|---|---|---|---|---|
| 01 | 2026-08-30 | 建立最初的 Skill、显式调用和 Lite / Standard / Full 三模式。 | [`5cde26d5f62d`](https://github.com/lengmh/deep-thinking-skills/commit/5cde26d5f62de3af457a750941abf8c452a753f0) | `4640cc1ff2ef` |
| 02 | 2026-08-31 | 增加状态校验和单写者锁，说明并发写入失败时的处理。 | [`0b1977cc08bc`](https://github.com/lengmh/deep-thinking-skills/commit/0b1977cc08bce802adf71e0bb8072d054d72d690) | `e08259fc2d4a` |
| 03 | 2026-09-05 | 完善模式规则、状态 Schema 和 Checkpoint 校验。 | [`a276c030e695`](https://github.com/lengmh/deep-thinking-skills/commit/a276c030e695b81c759eb34d6e792f2d295d7685) | `02859d288faa` |
| 04 | 2026-09-05 | Full 须先完成状态初始化；失败时说明无法继续，由用户选择后续模式。 | [`3547de98641c`](https://github.com/lengmh/deep-thinking-skills/commit/3547de98641c8625b990ecaa374333431b6e1f36) | `02cca7ec3bdc` |
| 05 | 2026-09-07 | Schema v4 保存完整工作集，增加转换重放、证据归属和结束判断的一致性校验。 | [`0d68be843f87`](https://github.com/lengmh/deep-thinking-skills/commit/0d68be843f872b5fa85ac99516ac042dd729276b) | `ec233e28565c` |
| 06 | 2026-09-07 | 补充 Checkpoint 参数帮助，说明列表替换、稳定 ID 和证据归属。 | [`8f1dfe0e58d9`](https://github.com/lengmh/deep-thinking-skills/commit/8f1dfe0e58d96c29e6b82467a44279eb15013c79) | `7df3cb7b03e5` |
| 07 | 2026-09-15 | 仅 init 创建状态目录，读取状态的命令不创建目录。 | [`e5a924cbddd7`](https://github.com/lengmh/deep-thinking-skills/commit/e5a924cbddd739caa155d7dac7d5b939d79e9fa5) | `ce087b00c181` |
| 08 | 2026-10-10 | 补充何时继续研究，以及何时因证据充分而结束的原则。 | [`8e8c218eb4c1`](https://github.com/lengmh/deep-thinking-skills/commit/8e8c218eb4c1ae29a93c581f4f5b508314751653) | `b3bf7413be86` |
| 09 | 2026-10-10 | 精简共享的证据判断原则，形成后续比较使用的 C 基线。 | [`a55db77fa349`](https://github.com/lengmh/deep-thinking-skills/commit/a55db77fa34968f98e32b7f2502b4ae57d675287) | `3efc62e05f8a` |
| 10 | 2026-10-12 | 完善必要重复核验和任务完成后的结束规则，形成 Cv2。 | [`187c50c248c0`](https://github.com/lengmh/deep-thinking-skills/commit/187c50c248c00edff8684845ffb7d5716691b394) | `6dce1a7b0e60` |

## 提交与日期说明

这些公开提交于 2026 年 10 月 13 日根据所选来源版本重新生成，组成 `history/product-evolution` 分支，再通过普通合并加入 `main`。首个公开提交和 `v1.1.0` 标签保留在原位置。

每个历史提交包含完整的 `.agents/skills/deep-thinking/`，共 11 个文件，内容与来源版本完全一致。MIT 许可证采用当前公开版本，并在整理历史时加入。

公开提交使用新的 SHA 和实际生成日期，作者与提交者使用 GitHub noreply 身份。提交说明另行保留来源 SHA 和原作者日期。开发仓库的提交对象、原作者邮箱、环境配置、实验材料和会话记录未导入。

相邻公开提交展示两个所选版本之间的包差异，不包含每一步开发操作或实验框架修改。公开 SHA 与来源 SHA 分别记录。

## 使用旧版本

当前安装使用 [v1.1.0 Release](https://github.com/lengmh/deep-thinking-skills/releases/tag/v1.1.0) 或 `v1.1.0` 标签。历史分支用于查看演进，旧版本可能使用旧 Schema、状态工具和模式规则，不能据此判断当前版本的兼容性。

整理时检查了来源文件、公开文件范围、提交身份和敏感信息，没有重新运行历史模型实验；旧版本测试结果仍只适用于当时的包。v1.1.0 包文件、manifest、Release 附件和原始评分均保持不变，评估结果见 [EVALUATION.md](EVALUATION.md)。
