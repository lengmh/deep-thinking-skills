# 模式说明

三种模式共享同一认识论内核。区别在于判断跟踪和恢复方式，模式选择不构成能力高低承诺。

| 合同 | Lite | Standard | Full |
|---|---|---|---|
| 选择方式 | 显式 `lite` | 显式 `standard` 或无模式参数 | 显式 `full` |
| 持久 Research Run | 禁止 | 禁止 | 必需 |
| Checkpoint | 不要求 | 事件触发 | 实质认识论转换 |
| 类型化终态与状态 CLI | 禁止 | 禁止 | 必需 |
| Retro | 禁止要求 | 禁止要求 | 仅例外事件触发 |

Lite 提供简短判断和必要的反转条件，不因缺少流程记录拒绝可解决任务。Standard 只在判断、关键假设、证据关系、范围或交接等实质变化时保留必要状态，不逐批要求记录或审批。

Full 先成功初始化独立 Research Run，再开展实质研究。它记录问题、研究目标、假设、证据、独立性关系、当前判断、Checkpoint 和终态；初始化失败时报告合同阻塞，不静默切换为 Standard。运行有单写入者，同一 Run 的并发写立即失败。终结前至少有一个实质 Checkpoint，终态判断绑定最新 Checkpoint。

Full 的 Schema 当前为 v4。CLI 对旧 v1/v2/v3 状态拒绝猜测迁移；历史回放应使用捕获该运行时的包。状态 provenance 是本地记录，不是宿主选择 Skill 的认证证明。

Skill 不维护全局活动模式，不因普通请求或任务复杂度自动激活。输出给出结论、关键依据、限制或反转条件；仅在仍需行动时给出下一步，不暴露私有思维链。

可执行合同分别位于 [Lite](../.agents/skills/deep-thinking/references/profile-lite.md)、[Standard](../.agents/skills/deep-thinking/references/profile-standard.md) 和 [Full](../.agents/skills/deep-thinking/references/profile-full.md)。
