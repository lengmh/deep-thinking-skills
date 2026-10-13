# 模式说明

三种模式采用同一套证据判断原则，区别在于如何跟踪判断和恢复研究记录。选择 Full 本身不保证更高的答案质量。

| 要求 | Lite | Standard | Full |
|---|---|---|---|
| 选择方式 | 显式 `lite` | 显式 `standard` 或不指定模式 | 显式 `full` |
| 持久研究记录（Research Run） | 不允许 | 不允许 | 必须 |
| 检查点（Checkpoint） | 不要求 | 按事件触发 | 记录实质变化 |
| 预定义的结束状态与状态 CLI | 不允许 | 不允许 | 必须 |
| 复盘（Retro） | 不要求 | 不要求 | 仅在例外事件发生时触发 |

Lite 给出简短判断和可能改变结论的条件，不因缺少流程记录而拒绝可解决的任务。Standard 只在判断、关键假设、证据关系、范围或交接等发生实质变化时跟踪必要信息，不要求每批记录或审批。

Full 必须先成功初始化独立的 Research Run，再开展实质研究。记录包括问题、研究目标、假设、证据及其独立性、当前判断、检查点和结束状态。初始化失败时说明无法继续，不自动切换为 Standard。同一 Run 只允许一个进程写入，并发写入立即失败。结束前至少记录一个实质检查点，结束时的判断必须与最新检查点一致。

Full 当前使用 Schema v4。CLI 不会为 v1/v2/v3 状态猜测迁移方式；回放旧记录时，应使用当时保存的包。状态中的调用来源只是本地记录，不能据此确认宿主是否实际加载了 Skill。

Skill 不维护全局活动模式，也不会因普通请求或任务复杂度自动激活。回答包含结论、关键依据、限制或可能改变结论的条件；只有仍需行动时才给出下一步，不暴露私有思维链。

完整模式规则见 [Lite](../.agents/skills/deep-thinking/references/profile-lite.md)、[Standard](../.agents/skills/deep-thinking/references/profile-standard.md) 和 [Full](../.agents/skills/deep-thinking/references/profile-full.md)。
