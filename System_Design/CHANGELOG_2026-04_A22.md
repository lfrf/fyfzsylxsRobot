# A22 项目改动记录（2026-04）

## 1. 说明
- 目的：汇总近期“已提交改动 + 当前工作区未提交改动”，方便比赛前统一追溯。
- 数据来源：当前仓库 `git log` 与当前工作区状态。
- 时间范围：2026-04-14 到 2026-04-21。

## 2. 关键改动时间线（已提交）
| Commit | Date | Summary |
|---|---|---|
| `969b789` | 2026-04-21 | `feat(release): add one-click competition submission packager` |
| `12ea2b4` | 2026-04-21 | `chore(remote): expose SER/FER envs and hsemotion cache path` |
| `becd49b` | 2026-04-21 | `chore: default TTS speaker to 中文女 in remote startup scripts` |
| `98980e5` | 2026-04-21 | `fix: add SoulX async render switch and default to stable sync mode` |
| `b7c2786` | 2026-04-21 | `feat: async soulx render and manifest polling for lower perceived latency` |
| `10a6212` | 2026-04-21 | `fix: keep full reply text for avatar video tts` |
| `be4ba43` | 2026-04-21 | `fix: correct SoulX command template to avoid broken mp4 output path` |
| `181e3ca` | 2026-04-21 | `fix avatar 500/422 and stabilize remote startup` |
| `d702251` | 2026-04-21 | `fix SoulX command template format crash` |
| `de9ca15` | 2026-04-21 | `fix avatar 422 fallback and add avatar error logging` |
| `c604e65` | 2026-04-21 | `sync remote startup and frontend proxy for soulx-full` |
| `ce0275d` | 2026-04-20 | `feat(remote): minimal soulxflashhead integration with video stream manifest` |
| `9442b9a` | 2026-04-19 | `avatar: densify viseme segmentation for better lip activity` |
| `764e44b` | 2026-04-18 | `feat(a2f-ue): add ws bridge, runtime adapter, and runbook` |
| `e98b808` | 2026-04-18 | `fix(avatar-service): stabilize cosyvoice runtime config and deps` |
| `970d637` | 2026-04-17 | `feat(avatar): add ws endpoint and push turn events` |
| `bbf5143` | 2026-04-17 | `fix(vision): accept numpy FER scores for confidence` |
| `4109d73` | 2026-04-17 | `fix(vision): pin timm for hsemotion and harden fer runtime` |
| `d8405cf` | 2026-04-17 | `feat: add SER(FunASR emotion2vec+) and FER(hsemotion enet_b2_7)` |
| `db32322` | 2026-04-15 | `Generate avatar video from leading reply segment` |
| `d54dd61` | 2026-04-14 | `Avoid speaking instruct prompt in CosyVoice 300M mode` |
| `534863b` | 2026-04-14 | `Document AutoDL single-port proxy startup flow` |

## 3. 已完成能力归纳（按链路）
1. 远端五服务启动链路稳定化（`qwen/speech/vision/avatar/orchestrator`）  
2. SoulX-FlashHead 视频生成链路打通，支持分段清单/流式清单轮询  
3. CosyVoice-300M-Instruct 与数字人视频合成联调完成  
4. 语音情绪 SER（emotion2vec）与视觉情绪 FER（hsemotion）已集成到服务层  
5. 远端启动脚本可显式配置 `SER_* / FER_* / TTS_SPEAKER_ID`  
6. 竞赛提交一键打包脚本已加入（导出镜像 tar + 工程包）  

## 4. 当前工作区未提交改动（本地）
截至本文件生成时，`git status -sb` 显示：
- `System_Design/AUTODL_REMOTE_FRONTEND_RUNBOOK.md`
- `local/frontend/src/styles.css`
- `local/frontend/src/ui/AvatarPanel.js`
- `local/frontend/src/ui/InputBar.js`

## 5. 本次新增 UI 改动（录音覆盖层）
目标：录音中用醒目标识覆盖文本输入框，而不是只改 placeholder。

改动点：
1. `local/frontend/src/ui/InputBar.js`  
   - 在输入框外层新增 `message-input-shell`。  
   - 新增 `recording-input-overlay`，文本为“正在录音中”。  
   - 在 `syncControls()` 中，当 `voiceTurnState === RECORDING` 时显示覆盖层，其它状态隐藏。  
2. `local/frontend/src/styles.css`  
   - 新增覆盖层样式（红色渐变、发光边框）。  
   - 新增录音指示点动效 `recordingPulse`。  

效果：
- 录音开始后，输入框区域会被“正在录音中”覆盖，状态更直观。  
- 录音结束或进入处理态后，覆盖层自动消失。  

## 5.1 本次新增 UI 改动（首屏数字人参考图对齐）
目标：首屏默认人像与当前 SoulX 参考图一致，避免展示旧人物图。

改动点：
1. `local/frontend/public/avatar-portrait.png`  
   - 用当前参考图（`girl.png`）替换默认首屏人像资源。  
2. `local/frontend/src/ui/AvatarPanel.js`  
   - 增加 `VITE_AVATAR_PORTRAIT_URL` 可配置入口。  
   - 未配置时默认读取 `./avatar-portrait.png?v=20260421`（附加缓存参数，避免浏览器缓存旧图）。  

效果：
- 页面首次加载时即展示与当前数字人生成模型一致的人像。  
- 后续换参考图可通过环境变量或替换 `public/avatar-portrait.png` 实现。  

## 6. 比赛提交材料映射（对应企业要求）
1. 可执行参赛作品 docker 镜像或软件安装包  
   - 已支持：`scripts/release/package_competition_submission.sh` 导出远端镜像 tar  
2. 可执行数字人面部行为驱动模型工程文件  
   - 对应目录：`remote/avatar-service`（已纳入打包脚本）  
3. 可执行语音识别模型工程文件  
   - 对应目录：`remote/speech-service`（已纳入打包脚本）  

## 7. 后续建议（可选）
1. 在提交前固定一个 tag（例如 `submission-v1`），保证评审可回溯。  
2. 出包后将 `sha256` 与 `submission_manifest.txt` 一并提交。  
3. 前端如需进一步“比赛展示化”，可继续弱化 UE 外部连接控件并保留状态看板。

## 8. 2026-04-21 Multi-avatar Switch (Safe, Backward Compatible)
- Added optional request fields across shared/edge/orchestrator:
  - `avatar_profile_id`
  - `avatar_ref_image_path`
- Frontend now includes an avatar profile switch button in avatar panel.
  - Default profile remains existing portrait.
  - Added second portrait asset: `local/frontend/public/avatar-portrait-alt.png`
  - Selected profile id is persisted in localStorage and sent with each `/chat` request.
- Orchestrator now resolves `ref_image_path` by priority:
  1. `avatar_ref_image_path` from request (if provided)
  2. `avatar_profile_id` mapped by env
  3. default profile mapping
  4. fallback to avatar-service own default (`SOULX_REF_IMAGE_PATH`)
- Remote startup script exports profile mapping envs so switching profile can change SoulX reference image without changing existing default flow.

### New envs (orchestrator)
- `AVATAR_DEFAULT_PROFILE_ID` (default: `avatar_a`)
- `AVATAR_PROFILE_ALT_ID` (default: `avatar_b`)
- `AVATAR_PROFILE_DEFAULT_REF_IMAGE_PATH` (default: current `SOULX_REF_IMAGE_PATH`)
- `AVATAR_PROFILE_ALT_REF_IMAGE_PATH` (default: `local/frontend/public/avatar-portrait-alt.png` if present; otherwise default ref)
- Optional JSON override: `AVATAR_PROFILE_REF_IMAGE_MAP`

### Frontend envs (optional)
- `VITE_AVATAR_PROFILE_DEFAULT_ID`
- `VITE_AVATAR_PROFILE_DEFAULT_NAME`
- `VITE_AVATAR_PROFILE_ALT_ID`
- `VITE_AVATAR_PROFILE_ALT_NAME`
- `VITE_AVATAR_PROFILE_ALT_PORTRAIT_URL`
