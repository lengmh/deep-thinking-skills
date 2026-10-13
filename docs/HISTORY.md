# 产品演进历史

2026-10-13，在首个公开快照之后补充 10 个可浏览、可比较的历史产品快照。它们按来源版本顺序组成 `history/product-evolution` 分支，并通过普通合并接入公开 `main`。首个公开提交及 `v1.1.0` 标签保留在原位置。

## 历史如何整理

每个历史提交保存对应来源版本的完整 `.agents/skills/deep-thinking/`，共 11 个文件。各文件的内容与来源版本逐字节一致；同时加入当前公开版本的 MIT 许可证，便于明确这些公开快照的分发许可。许可证是在本次整理时加入的。

公开历史使用本次整理的新提交、新 SHA 和实际生成日期，作者与提交者使用 GitHub noreply 身份。原提交 SHA 和原作者日期作为来源信息分别记录在提交说明中。开发仓库的 Git 提交对象、原作者邮箱、环境配置、实验材料及会话记录均未导入。

这是一组经过筛选的产品快照，相邻公开提交展示两个所选来源版本之间的包差异。它不包含每一步开发操作或对应实验框架的修改；重新生成的公开 SHA 也不会被当作原提交 SHA。

## 来源对照

下表按原版本的作者日期排列。公开提交时间为本次生成时间；完整 SHA、精确日期、包树与逐文件 SHA-256 见 [history.json](history.json)。

| 序号 | 来源日期 | 产品变化 | 公开提交 | 来源提交 |
|---|---|---|---|---|
| 01 | 2026-08-30 | 建立 canonical Skill、显式调用和 Lite / Standard / Full 三模式。 | [`5cde26d5f62d`](https://github.com/lengmh/deep-thinking-skills/commit/5cde26d5f62de3af457a750941abf8c452a753f0) | `4640cc1ff2ef` |
| 02 | 2026-08-31 | 补充状态校验与单写者锁，明确并发写入失败的处理。 | [`0b1977cc08bc`](https://github.com/lengmh/deep-thinking-skills/commit/0b1977cc08bce802adf71e0bb8072d054d72d690) | `e08259fc2d4a` |
| 03 | 2026-09-05 | 强化模式合同、状态 Schema 和 Checkpoint 校验。 | [`a276c030e695`](https://github.com/lengmh/deep-thinking-skills/commit/a276c030e695b81c759eb34d6e792f2d295d7685) | `02859d288faa` |
| 04 | 2026-09-05 | Full 须先完成状态初始化；失败时报告阻塞，由用户选择后续模式。 | [`3547de98641c`](https://github.com/lengmh/deep-thinking-skills/commit/3547de98641c8625b990ecaa374333431b6e1f36) | `02cca7ec3bdc` |
| 05 | 2026-09-07 | Schema v4 保存完整工作集，补充转换重放、证据归属和终态一致性校验。 | [`0d68be843f87`](https://github.com/lengmh/deep-thinking-skills/commit/0d68be843f872b5fa85ac99516ac042dd729276b) | `ec233e28565c` |
| 06 | 2026-09-07 | 补充 Checkpoint 参数帮助，说明列表替换、稳定 ID 和证据归属。 | [`8f1dfe0e58d9`](https://github.com/lengmh/deep-thinking-skills/commit/8f1dfe0e58d96c29e6b82467a44279eb15013c79) | `7df3cb7b03e5` |
| 07 | 2026-09-15 | 将状态目录创建限定在 init 中，收敛只读命令与写入行为的边界。 | [`e5a924cbddd7`](https://github.com/lengmh/deep-thinking-skills/commit/e5a924cbddd739caa155d7dac7d5b939d79e9fa5) | `ce087b00c181` |
| 08 | 2026-10-10 | 补充关键未知的继续追究与证据充分后的收束原则。 | [`8e8c218eb4c1`](https://github.com/lengmh/deep-thinking-skills/commit/8e8c218eb4c1ae29a93c581f4f5b508314751653) | `b3bf7413be86` |
| 09 | 2026-10-10 | 精简共享认识论内核，形成后续比较使用的 C 基线。 | [`a55db77fa349`](https://github.com/lengmh/deep-thinking-skills/commit/a55db77fa34968f98e32b7f2502b4ae57d675287) | `3efc62e05f8a` |
| 10 | 2026-10-12 | 完善必要重复核验与任务完成后的收束规则，形成 Cv2。 | [`187c50c248c0`](https://github.com/lengmh/deep-thinking-skills/commit/187c50c248c00edff8684845ffb7d5716691b394) | `6dce1a7b0e60` |

## 安装与验证边界

安装继续使用固定的 [v1.1.0 Release](https://github.com/lengmh/deep-thinking-skills/releases/tag/v1.1.0) 或 `v1.1.0` 标签。历史分支用于浏览演进，早期快照可能采用旧 Schema、旧状态工具和旧模式合同，不能用于推断当前版本兼容性。

本次整理逐项核对来源包字节、公开文件范围和提交身份，并检查敏感信息特征。它没有重跑历史版本的模型实验，也没有为历史快照重新授予资格。v1.1.0 的包、manifest、Release 附件和既有评分保持原值，当前评估结论见 [EVALUATION.md](EVALUATION.md)。
