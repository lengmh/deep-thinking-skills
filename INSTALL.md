# 安装、更新与回滚

安装完整的 `deep-thinking/` 目录。入口、宿主配置、参考文档、Schema 和状态工具共 11 个文件，必须保持完整。

## 安装前准备

- 使用支持 Agent Skills 的工具，并确认工具实际读取的 Skills 目录。
- 准备已有 Python 3；校验器只使用标准库。
- 更新前确认安装目录，将现有版本备份到明确命名的位置。

已验证的环境为 Linux/WSL 和 Codex CLI `0.162.0-alpha.2`。下列 Windows 步骤使用标准文件操作，Windows 原生宿主的兼容性尚未确认。

## 从 Release 安装

1. 从 [v1.1.0 Release](https://github.com/lengmh/deep-thinking-skills/releases/tag/v1.1.0) 下载全部附件到独立目录。
2. 在下载目录核对 `SHA256SUMS`。Linux/WSL 使用：

   ```bash
   sha256sum --check SHA256SUMS
   ```

   Windows 可使用 `Get-FileHash -Algorithm SHA256` 逐项比较文件与清单。
3. 解压安装包，验证解压后的目录：

   ```bash
   python3 -m zipfile -e deep-thinking-v1.1.0.zip unpacked
   python3 validate_skill_package.py unpacked/deep-thinking --verify-manifest deep-thinking-package-manifest.json
   ```

   Windows 使用已有 Python 3 命令执行等价操作。
4. 新安装时，先确认目标目录不存在，再复制完整的 `unpacked/deep-thinking/`。目标目录已存在时，按下文的更新步骤处理。
5. 用同一校验器和 manifest 检查实际安装目录，然后完全退出并重新启动宿主，确认能显式调用 Skill。

校验或路径检查失败时停止安装，保留旧目录。校验和只能检查文件完整性，不能替代数字签名；应从可信的 Release 渠道下载附件。

## 从源码安装

```bash
git clone https://github.com/lengmh/deep-thinking-skills.git
cd deep-thinking-skills
git switch --detach v1.1.0
python3 scripts/validate_skill_package.py .agents/skills/deep-thinking --verify-manifest deep-thinking-package-manifest.json
```

新安装的 Linux/WSL 示例，确认目标目录尚不存在后执行：

```bash
if test -e "$HOME/.agents/skills/deep-thinking"; then
  printf '%s\n' '目标目录已存在，请先按更新步骤备份。'
else
  mkdir -p "$HOME/.agents/skills"
  cp -R .agents/skills/deep-thinking "$HOME/.agents/skills/deep-thinking"
  python3 scripts/validate_skill_package.py "$HOME/.agents/skills/deep-thinking" --verify-manifest deep-thinking-package-manifest.json
fi
```

目标目录已存在时，示例只显示提示，不复制文件。更新已有版本时，先按上一节备份旧目录。

Codex 可使用用户级安装位置 `~/.agents/skills/deep-thinking`，也可使用兼容位置 `$CODEX_HOME/skills/deep-thinking`。选择宿主实际读取的一个位置，避免同时保留内容不同的同名副本。其他宿主按各自的目录约定安装，兼容性需另行确认。

仅安装 Skill 目录。不要把 `docs/`、`scripts/`、`.git/` 或整个 GitHub Source code 归档作为 Skill 安装。

## 调用与模式

```text
$deep-thinking <request>
$deep-thinking lite <request>
$deep-thinking standard <request>
$deep-thinking full <request>
```

未指定模式时使用 Standard，模式只对当前调用有效。未知模式会被拒绝，不会回退到默认模式。Full 需要可写的状态目录；初始化失败时报告无法继续，不自动切换模式。具体要求见[模式说明](docs/PROFILES.md)。

## 更新

1. 下载目标版本的安装包，按该版本的校验和、校验器和 manifest 检查文件。
2. 确认实际安装目录，将现有目录移到明确命名的备份位置。
3. 将新版的完整 `deep-thinking/` 目录放入原安装位置。
4. 用新版校验器和 manifest 检查实际安装目录，再完全退出并重新启动宿主，确认能显式调用 Skill。

校验失败时停止更新，保留旧版本备份。需要恢复时按下文操作。

## 恢复旧版本

恢复此前备份的安装目录，用旧版本的 manifest 校验，再完全退出并重新启动宿主，确认能显式调用 Skill。也可下载保留的旧版本安装包。不要用宽泛通配符删除整个 Skills 目录。

v1.1.0 的 Full Schema 和状态 CLI 与 Cv2 相同，无需迁移状态。旧 Schema 的运行记录须用当时保存的包回放，不能猜测迁移方式。
