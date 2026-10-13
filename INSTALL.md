# 安装、更新与回滚

仅安装完整的 `deep-thinking/` 包目录。入口、adapter、references、Schema 和状态工具共 11 个文件，须保持完整。

## 前置条件

- 使用支持 Agent Skills 的宿主，并确认宿主实际使用的 Skills 根目录。
- 准备已有 Python 3；校验器仅使用标准库。
- 更新前确认目标安装目录，并将现有目录备份到明确命名的位置。

实际验证环境为 Linux/WSL 和 Codex CLI `0.162.0-alpha.2`。下列 Windows 步骤采用标准文件操作，但本版本尚未取得 Windows 原生宿主认证。

## 从 Release 安装

1. 从 [v1.1.0 Release](https://github.com/lengmh/deep-thinking-skills/releases/tag/v1.1.0) 下载全部附件到独立目录。
2. 在该目录核对 `SHA256SUMS`。Linux/WSL 使用：

   ```bash
   sha256sum --check SHA256SUMS
   ```

   Windows 可使用 `Get-FileHash -Algorithm SHA256` 逐项比较文件与清单。
3. 解压安装包并验证：

   ```bash
   python3 -m zipfile -e deep-thinking-v1.1.0.zip unpacked
   python3 validate_skill_package.py unpacked/deep-thinking --verify-manifest deep-thinking-package-manifest.json
   ```

   Windows 使用已有 Python 3 命令执行等价操作。
4. 新安装时确认目标目录不存在，再复制完整 `unpacked/deep-thinking/`。更新时先移动旧安装目录到备份位置，再放入新目录。
5. 用同一校验器和 manifest 验证实际安装目录，然后冷启动宿主并确认显式调用可发现。

校验或路径检查失败时停止安装，保留旧目录。校验和确认字节完整性，不是数字签名；从可信 Release 渠道取得附件。

## 从源码快照安装

```bash
git clone https://github.com/lengmh/deep-thinking-skills.git
cd deep-thinking-skills
git switch --detach v1.1.0
python3 scripts/validate_skill_package.py .agents/skills/deep-thinking --verify-manifest deep-thinking-package-manifest.json
```

新安装的 Linux/WSL 示例，确认目标尚不存在后执行：

```bash
if test -e "$HOME/.agents/skills/deep-thinking"; then
  printf '%s\n' '目标目录已存在，请先按更新步骤备份。'
else
  mkdir -p "$HOME/.agents/skills"
  cp -R .agents/skills/deep-thinking "$HOME/.agents/skills/deep-thinking"
  python3 scripts/validate_skill_package.py "$HOME/.agents/skills/deep-thinking" --verify-manifest deep-thinking-package-manifest.json
fi
```

示例在目标已存在时仅给出提示，不执行复制。更新已有目录时按上一节的备份步骤处理。

Codex 可使用用户级 Agent Skills 根 `~/.agents/skills/deep-thinking`；兼容根为 `$CODEX_HOME/skills/deep-thinking`。选择宿主实际发现的一个位置，避免同时保留不同字节的同名副本。其他宿主按其目录约定放置完整包，本项目未认证全部宿主。

仓库根不是 Skill 根。不要把 `docs/`、`scripts/`、`.git/` 或整个 GitHub Source code 归档安装为 Skill。

## 调用与模式

```text
$deep-thinking <request>
$deep-thinking lite <request>
$deep-thinking standard <request>
$deep-thinking full <request>
```

无模式参数时使用 Standard。模式只对当前调用有效；未知模式拒绝而不回退。Full 需要可写状态目录，初始化失败时报告阻塞，不静默降级。详细边界见[模式说明](docs/PROFILES.md)。

## 回滚

恢复此前备份的精确安装目录，按其原 manifest 核验，再冷启动宿主确认显式调用可发现。也可下载保留的旧版本安装包。避免用宽泛通配符删除整个 Skills 根。

v1.1.0 的 Full Schema 与状态 CLI 沿用 Cv2 的既有字节，本次公开分发不要求状态迁移。旧 Schema 运行记录须用当时捕获的包回放，不猜测迁移。
