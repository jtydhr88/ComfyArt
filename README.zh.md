# ComfyArt

[English](README.md) | 中文

[![ComfyArt 宣传片](docs/media/preview-zh.gif)](docs/media/promo-zh.mp4)

[观看完整宣传片（38 秒）](docs/media/promo-zh.mp4)

免费开源的 AI 设计画布，完全跑在你自己的 ComfyUI 上：无限画布（tldraw + React）、能用工具直接在画布上干活的设计 Agent，所有图像、视频、音频和 3D 模型都在本地运行。不用账号，不花积分，不上云。

每个功能的图文说明见文档站 **[comfyart.org](https://comfyart.org/zh)**。

![Agent 在画布上做出一张 Instagram 海报](docs-site/images/agent-result.webp)

## 三步试用

1. 把 `https://github.com/jtydhr88/ComfyArt` clone 到 `ComfyUI/custom_nodes/`，在 ComfyUI 的环境里运行 `pip install -r requirements.txt`。不用构建，`dist/` 已经提交在仓库里。
2. 重启 ComfyUI（或 Comfy Desktop）。没有本地 GPU 的话，先设好 `COMFY_API_KEY`，所有工作流都在 [Comfy Cloud](README.md#comfy-cloud) 上跑，不用下载模型。
3. 点 ComfyUI 顶栏的 **ComfyArt** 按钮，或打开 `http://127.0.0.1:8188/comfyart/`。用 Cloud 时在设置 → 生成位置里选 Comfy Cloud。首页左侧栏和项目左上角的 logo 菜单里都有 **返回 ComfyUI**。

## 功能

- **首页和项目**：一句话或一个技能就能开始设计，浏览和管理项目，随时切换语言（中文 / English）、主题和对话栏位置。
- **画布**：多页面；画板支持尺寸预设、填充、描边和圆角、自动布局；图层面板可拖动、重命名、范围选择；评论可以直接执行修改，或连同圈出的区域发给 Agent；快照历史；导出 PNG、JPG、PDF 和可编辑的 PPTX。
- **文字和矢量**：富文本（同一个文本框里混用字体、字号、颜色、粗体、斜体、下划线）；字体选择器分品牌、常用和本机字体；纯色、线性、径向和图片填充，色标支持透明度，支持混合模式；钢笔工具和节点编辑；布尔运算（合并、减去、相交、排除）。
- **生成**：按真实像素尺寸出现的图像生成器，五个本地图像模型，参考图和结构模式，配色和底图；视频支持文生视频、首尾帧、最多 9 张参考图和分镜，5 到 15 秒，768p 或 1080p。
- **图片工具**：快捷编辑、放大、去背景、橡皮、带平台预设的裁剪、翻转旋转、非破坏性调整、局部重绘、移动对象、多角度、扩图、图层拆分、编辑文字、风格迁移、矢量化。
- **编辑元素**：把一张成品海报还原成可编辑的画板（OCR 文字图层、抠出的产品和 logo、干净的背景），改完再重新渲染。
- **样机**：把设计印到产品照片上，实时贴合褶皱和光影，然后烘焙成图片或用 AI 融合。
- **音频和 3D**：配乐、配音（支持声音克隆）和音效，以可播放的卡片放在画布上；图片转带贴图的 3D 模型。
- **资产**：我的资产、整页的品牌套件编辑器、角色、产品和参考图板。
- **Agent**：会调用工具的设计 Agent（见下文），通过 MCP 可以使用以上所有功能。

## 安装

把本目录放进 `ComfyUI/custom_nodes/`，在 ComfyUI 的环境里装好 Python 依赖（`pip install -r requirements.txt`：PDF 上传用的 `pypdfium2` 和编辑元素用的 `rapidocr`），重启 ComfyUI 后打开 `http://127.0.0.1:8188/comfyart/`。构建好的页面在 `dist/`；改了 `src/` 之后用 `npm install && npm run build` 重新构建。

项目、项目的快照历史和 Agent 对话都保存在 SQLite 数据库 `user/__comfyart/data.db` 里。旧版本的项目（`comfyart/projects/` 下的 JSON 文件）会在第一次打开 ComfyArt 时自动导入，原文件保留不动。界面语言默认跟随 ComfyUI，可以在设置菜单里随时切换。

## 局域网实例

局域网里其他的 ComfyUI 也能跑 ComfyArt 的任务。对方启动时加 `--listen`，在 设置 → 局域网实例… 里登记（名称、地址、端口，别的都不存）。之后 设置 → 生成位置 决定任务的默认去处：「自动」把任务发给排队最少、并且装齐了工作流所需节点和模型文件的机器，本机也算一台，关机或缺东西的机器会被跳过；选了某一台就排到那台的队列。每张生成卡片还能在模型旁边的「运行在」里单独改。放大、去背景这类工具按默认去处走，运行中的卡片会显示任务去了哪台机器。输入文件会上传到对方的 `input/comfyart/`，进度照常显示在画布上，结果下载到本机 `output/comfyart/`，文件名带 `<机器>-<任务>` 后缀。模型按文件名匹配，各台机器放在不同子目录也没关系。Qwen Image 2512 的加载器要求那台机器也装了 ComfyArt。

## Agent

Agent 面板在后端运行一个真正会调用工具的 Agent，移植自 [ComfyTV](https://github.com/jtydhr88/ComfyTV) 的 bot。默认关闭：在「Agent 设置」里打开 MCP 和 Agent 即可。图像、视频模式不依赖它。每个对话可以单独选择 Agent：

| Agent | 需要什么 |
|---|---|
| Claude Code | PATH 里有 `claude` 且已登录 |
| Codex | PATH 里有 `codex` 且已登录 |
| Qwen Code | PATH 里有 `qwen`，并在 `~/.qwen/settings.json` 配好模型 |
| DeepSeek Harness | PATH 里有 `dsh`，并在 DeepSeek Harness 应用里登录 |
| Hermes | 本机或可 SSH 登录的另一台机器上装好 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 并配好模型（见 [Agent 文档](https://comfyart.org/zh/guides/agent)） |
| Local LLM | 任意支持工具调用的 OpenAI 兼容端点（Agent 设置 → Local LLM 地址）；需要 key 时在启动 ComfyUI 前设置 `COMFYART_LOCAL_LLM_API_KEY` |

智能分镜、OCR、品牌和记忆提取、参考图说明、Ideogram 的结构化描述，都是对默认 Agent 的单次调用（`POST /comfyart/bot/complete`，不带工具）。ComfyArt 从不保存任何凭据。Agent 通过 `POST /comfyart/mcp` 上的 ComfyArt MCP 服务器干活（查看画布、生成和编辑图片、视频、音频和 3D 模型、编辑元素和样机、放置文字、形状、画板、网页和幻灯片、记忆、技能、向用户提问）。画布工具由该项目打开着的 ComfyArt 标签页执行，所以 Agent 工作时请保持页面打开。对话保存在 SQLite 数据库 `user/__comfyart/data.db` 里，关掉面板也会继续运行。

### 在其他 agent 里使用 ComfyArt

在「Agent 设置」里打开 MCP，把 `http://127.0.0.1:8188/comfyart/mcp?project=<项目 id>` 加到任意 MCP 客户端，例如：

```bash
claude mcp add --transport http comfyart "http://127.0.0.1:8188/comfyart/mcp?project=<项目 id>"
codex mcp add comfyart --url "http://127.0.0.1:8188/comfyart/mcp?project=<项目 id>"
```

Claude Code、Codex、Gemini CLI、Qwen Code、Cursor、VS Code、Claude Desktop 和自写脚本的接入方法、工具超时设置以及完整工具列表见 [MCP 指南](https://comfyart.org/zh/guides/mcp)。

## 工作流和模型

画布上的每个操作都通过 ComfyUI 的 `/prompt` 运行 `workflows/` 里的某个 API 工作流。除特别注明外都只用核心节点。

| 操作 | 工作流 | 模型 / 自定义节点 |
|---|---|---|
| 图像生成、快捷编辑、编辑文字、扩图、评论改稿 | `qwen-image-2.1-t2i`、`edit-qwen-image-2.1`、`outpaint-qwen-image-2.1` | `qwen_image_2.1_int8_convrot.safetensors`、`qwen3vl_8b_int8_convrot.safetensors`、`qwen_image_2.1_vae_bf16.safetensors` |
| 图像生成（其他模型） | `z-image-turbo-t2i`、`krea2-turbo-t2i`、`flux2-klein-9b-t2i`、`flux3-klein-t2i`、`moss-image-t2i`、`qwen-image-2512-t2i`、`ideogram4-t2i` | `z_image_turbo_bf16` + `qwen_3_4b` + `ae`；`krea2_turbo_int8_convrot` + `qwen3vl_4b_fp8_scaled` + `qwen_image_vae`；`flux-2-klein-9b-nvfp4` + `qwen_3_8b_fp8mixed` + `flux2-vae`；`flux3-image-klein-int8-convrot` + `qwen3vl_4b_int8_convrot` + `flux2-vae`；`moss_image_sft_int8_convrot` + `qwen3.5_9b_w4a8_gptq` + `flux2-vae_small`；`qwen_image_2512_fp8_e4m3fn` + `qwen_2.5_vl_7b_fp8_scaled` + `qwen_image_vae`（用 ComfyArt Precise UNET Loader 节点加载，见下文）；`ideogram4_fp8_scaled` + `ideogram4_unconditional_fp8_scaled` + `qwen3vl_8b_fp8_scaled` + `flux2-vae`，Ideogram 需要的结构化描述由默认 Agent 撰写（`ideogram4-caption.json`） |
| 参考模式（线稿、景深、姿势等） | 代码内构建 | [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) 预处理器（MLSD、HED、法线和分割首次使用时会下载标注器权重）；配合 Qwen Image 2512 还需要 `Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors`（controlnet） |
| 语音输入 | `transcribe-gemma4` | `gemma4_e4b_it_fp8_scaled.safetensors`（text_encoders） |
| 放大 | `upscale-ultrasharp-4x` | `4x-UltraSharp.pth`（upscale_models） |
| 去背景 | `cutout-birefnet` | `birefnet.safetensors`（background_removal） |
| 橡皮工具 | `erase-lama` | [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes)、`big-lama.pt` |
| 多角度 | `multiangle-qwen-image-2.1` | 上面的 Qwen Image 2.1 三个文件，外加 [`qwen-image-2.1-qma-camera-angles.safetensors`](https://huggingface.co/gribbliest/qwen-image-2.1-qma-camera-angles)（loras） |
| 图层拆分 | `layers-qwen-image-layered` | `qwen_image_layered_bf16.safetensors`、`qwen_image_layered_vae.safetensors`、`qwen_2.5_vl_7b_fp8_scaled.safetensors` |
| 动态图片、视频生成、视频延长 | `i2v-minimax-h3`、`t2v-minimax-h3` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors`、`minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`、`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`、`minimax_h3_video_vae_fp16.safetensors`、`minimax_h3_audio_vae_fp32.safetensors` |
| 参考生视频（图片、视频、音频） | `r2v-minimax-h3` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors`，外加上面的文本编码器和 VAE |
| 动作控制 | `r2v-minimax-h3` + 代码内构建的姿态图 | `minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors`（model_patches）、`sdpose_wholebody_fp16.safetensors`（checkpoints）、`rt_detr_v4-x-hgnet_fp16.safetensors`（diffusion_models） |
| 对口型 | `i2v-minimax-h3` + `MiniMaxH3AddGuide` | 上面图生视频的那套文件 |
| 视频剪辑（多片段、配乐、导出） | 代码内构建 | ComfyArt Timeline Render 节点（随 ComfyArt 提供） |
| 编辑元素 | 代码内构建、`erase-lama` | `rapidocr`（Python 包，`POST /comfyart/ocr`）、SAM3（`sam3.1_multiplex_fp16.safetensors`）、LaMa |
| 样机 | `mockup-surface` | [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) 的 Depth Anything V2（`depth_anything_v2_vitl.pth`，首次使用时下载）、`birefnet.safetensors` |
| 配乐（MiniMax Music 3） | `music-minimax3` | `minimax_music3_dit_fp16.safetensors`（diffusion_models）、`minimax_music3_text_encoder_pruned_int8_convrot.safetensors`（text_encoders）、`minimax_music3_dav.safetensors`（vae） |
| 配乐（ACE-Step 1.5） | `music-ace-step15` | `acestep_v1.5_xl_turbo_bf16.safetensors`（diffusion_models）、`qwen_0.6b_ace15.safetensors` 和 `qwen_4b_ace15.safetensors`（text_encoders）、`ace_1.5_vae.safetensors`（vae） |
| 配乐（YuE2） | `music-yue2` | `yue2_3b_int8_convrot.safetensors`（checkpoints） |
| 音效 | `sfx-stable-audio` | `stable-audio-open-1.0.safetensors`（checkpoints）、`t5-base.safetensors`（text_encoders） |
| 配音 | `speech-kokoro` | [comfyui-kokoro](https://github.com/stavsap/comfyui-kokoro) |
| 声音克隆 | `voice-clone-indextts` | [ComfyUI-Easy-IndexTTS2](https://github.com/yolain/ComfyUI-Easy-IndexTTS2) |
| 图片转 3D | `image-to-3d-trellis2` | `trellis_2_int8_convrot.safetensors`、`trellis_2_shape_vae_bf16.safetensors`、`trellis_2_texture_vae_bf16.safetensors`、`dino_v3_L_naf_fp32.safetensors`（clip_vision）、`birefnet.safetensors` |
| 图片转 3D（Pixal3D） | `image-to-3d-pixal3d` | `pixal3d_int8_convrot.safetensors`、`moge_2_vitl_normal_fp16.safetensors`（geometry_estimation），以及上面的 TRELLIS.2 两个 VAE、`dino_v3_L_naf_fp32.safetensors` 和 `birefnet.safetensors` |
| 多视角转 3D（Pixal3D） | `image-to-3d-pixal3d-multiview` | `pixal3d_multiview_int8_convrot.safetensors`，以及上面的 TRELLIS.2 两个 VAE、`dino_v3_L_naf_fp32.safetensors` 和 `birefnet.safetensors` |

## 节点和路由

- `web/comfyart.js` 在 ComfyUI 顶栏加一个 ComfyArt 按钮（Comfy Desktop 里也有）。
- `ComfyArt Precise UNET Loader` 用 manual cast 算子加载扩散模型。ComfyUI 的 `--fast fp8_matrix_mult` 会把 Qwen Image 2512 这类未缩放的 fp8 权重跑成噪点；这个加载器让它加载的模型绕开那条路径。
- `/comfyart/bot/*`（对话、发送、停止、分支、回答）、`/comfyart/settings` 和 `/comfyart/mcp` 服务于 Agent。
- `/comfyart/instances` 列出、添加、修改、删除局域网实例；`/comfyart/instances/status` 返回哪些在线以及各自的队列和扩散模型。`POST /comfyart/remote/prompt` 选机器（`target` 是实例 id 或 `auto`）并把任务排上去；`GET /comfyart/remote/history/{instance}/{job}` 和 `POST /comfyart/remote/cancel/{instance}/{job}` 跟进这个任务。
- `POST /comfyart/pdf` 把上传的 PDF 前 30 页渲染成 PNG，存到 `input/comfyart/pdf/`，并连同每页文字一起返回。
- `POST /comfyart/ocr` 在本机用 RapidOCR 识别图片里的文字行，返回每行文字和位置框。

## 开发

`npm run dev` 启动 Vite，`/api` 代理到 `http://127.0.0.1:8188`（可用 `COMFY_URL` 覆盖）。

## 许可证

ComfyArt 采用 MIT 许可证。`bot/` 和 `api/` 里的 Agent 后端改编自 [ComfyTV](https://github.com/jtydhr88/ComfyTV) 的 bot（MIT），其中包括 Pengjingyu1992（DeepSeek Harness、Local LLM、Codex）、MuAIGC（Codex、Qwen Code）和 Goldlionren（Codex）共同编写的 provider。画布使用的 [tldraw SDK](https://tldraw.dev) 不是 MIT：它以自身的许可证打包在 `dist/` 中，许可证副本见 `licenses/tldraw-LICENSE.md`。从 `localhost` 或普通 `http` 访问时，它以开发模式运行，无需许可证密钥，右下角会显示一个小的 "Get a license for production" 标记。
