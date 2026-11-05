# ComfyArt

English | [中文](README.zh.md)

[![ComfyArt promo](docs/media/preview-en.gif)](docs/media/promo-en.mp4)

[Watch the full promo (38s)](docs/media/promo-en.mp4)

A free, open-source AI design canvas that runs fully on your own ComfyUI: an infinite canvas (tldraw + React), a design agent that works on it with tools, and every image, video, audio and 3D model running locally. No account, no credits, no cloud.

Documentation with screenshots for every feature: **[comfyart.org](https://comfyart.org)**.

![The Agent building an Instagram post on the canvas](docs-site/images/agent-result.webp)

## Try it in 3 steps

1. `git clone https://github.com/jtydhr88/ComfyArt` into `ComfyUI/custom_nodes/` and run `pip install -r requirements.txt` in ComfyUI's environment. No build is needed: `dist/` is committed.
2. Restart ComfyUI (or Comfy Desktop). No local GPU? Set `COMFY_API_KEY` first and every workflow runs on [Comfy Cloud](#comfy-cloud) with no model downloads.
3. Click **ComfyArt** in ComfyUI's top bar, or open `http://127.0.0.1:8188/comfyart/`. On Cloud, pick Settings → Generate on → Comfy Cloud. **Back to ComfyUI** sits in the home rail and in the logo menu of a project.

## Features

- **Home and projects**: start a design from one sentence or a skill, browse and manage projects, switch language (中文 / English), theme and chat side at any time.
- **Canvas**: pages, artboards with size presets, fill, stroke and corner radius, auto layout, a layers panel with drag, rename and range select, comments that can be run as edits or sent to the Agent with the marked area, snapshot history, export to PNG, JPG, PDF and editable PPTX.
- **Text and vectors**: rich text (mixed fonts, sizes, colors, bold, italic, underline in one text box), a font picker with brand, common and local fonts, solid, linear, radial and image fills with transparent color stops and blend modes, a pen tool with node editing, and boolean union, subtract, intersect and exclude.
- **Generate**: image generators sized in real pixels with five local image models, references and structure modes, color palettes and base images; video from text, first and last frames, up to 9 reference images, or a storyboard, 5 to 15 seconds at 768p or 1080p.
- **Image tools**: quick edit, upscale, remove background, eraser, crop with platform presets, flip and rotate, non-destructive adjust, inpaint, move object, multi-angle, expand, split layers, edit text, style transfer, vectorize.
- **Edit Elements**: turn a flat poster back into an editable artboard (OCR text layers, cut-out product and logo, clean background), edit it, then re-render.
- **Mockups**: print a design onto a product photo; it follows folds and shading in real time, then bake it or blend it with AI.
- **Audio and 3D**: music, voiceovers (with voice cloning) and sound effects as playable cards; image to textured 3D model.
- **Assets**: My Assets, a full-page brand kit editor, characters, products and a reference board.
- **Agent**: a tool-using design agent (below) that can use every feature above through MCP.

## Install

Put this folder in `ComfyUI/custom_nodes/`, install the Python requirements into ComfyUI's environment (`pip install -r requirements.txt`: `pypdfium2` for PDF uploads and `rapidocr` for Edit Elements), restart ComfyUI and open `http://127.0.0.1:8188/comfyart/`. The built page is in `dist/`; after changing `src/`, rebuild with `npm install && npm run build`.

Projects, their snapshot history and agent chats are saved in a SQLite database, `user/__comfyart/data.db`. Projects from older versions (JSON files under `comfyart/projects/`) are imported automatically the first time you open ComfyArt; the files are left in place. The interface starts in ComfyUI's language and can be switched from the settings menu.

## Comfy Cloud

ComfyArt can run its workflows on [Comfy Cloud](https://cloud.comfy.org) instead of the local GPU. Create an API key at [platform.comfy.org](https://platform.comfy.org/profile/api-keys) (Cloud API keys need a paid Comfy plan), set it as `COMFY_API_KEY` before starting ComfyUI, then choose Settings → Generate on → Comfy Cloud. The same workflows are sent to `https://cloud.comfy.org/api/v2/jobs`; no build or deployment is needed because Cloud has the models and nodes preinstalled. Input images and audio are uploaded as Cloud assets when a job is submitted, and results are downloaded into `output/comfyart/` with a `cloud-<job>` suffix, so the canvas, history and Agent see them like local results.

On Cloud, FLUX.2 Klein 9B runs the bf16 `flux-2-klein-9b.safetensors` and Qwen Image 2512 loads with the core `UNETLoader`. Angles imports the QMA LoRA from Hugging Face into your Cloud model library the first time it runs. Voiceover and voice cloning use Qwen3-TTS on Cloud (`speech-qwen3tts`, `voice-clone-qwen3tts`) instead of Kokoro and IndexTTS2, which Cloud does not have.

## LAN instances

Other ComfyUI machines on your network can run ComfyArt jobs too. Start them with `--listen`, and add them under Settings → LAN instances… (name, address, port; nothing else is stored). Settings → Generate on then sets where jobs go by default: Auto sends each job to the least busy machine, this computer included, that has every node and model file the workflow needs, skipping machines that are off or missing something; picking a machine queues jobs there. Each generator card can override it under Run on, next to the model. Tools such as upscale or remove background use the default, and the card shows where a running job went. Input files are uploaded to the machine's `input/comfyart/`, progress shows on the canvas as usual, and results are downloaded into `output/comfyart/` with a `<machine>-<job>` suffix. Model files are matched by file name, so they can sit in different subfolders on each machine. Qwen Image 2512 needs ComfyArt installed on that machine for its loader.

## Agent

The Agent panel runs a real tool-using agent on the backend, ported from [ComfyTV](https://github.com/jtydhr88/ComfyTV)'s bot. It is off by default: turn on MCP and the Agent in Agent Settings. Image and video modes work without it. Pick the agent per chat:

| Agent | What it needs |
|---|---|
| Claude Code | `claude` on PATH, logged in |
| Codex | `codex` on PATH, logged in |
| Qwen Code | `qwen` on PATH with a model configured in `~/.qwen/settings.json` |
| DeepSeek Harness | `dsh` on PATH, signed in through the DeepSeek Harness app |
| Hermes | [Hermes Agent](https://github.com/NousResearch/hermes-agent) with a model configured, on this machine or another one over SSH (see the [Agent guide](https://comfyart.org/guides/agent)) |
| Local LLM | any OpenAI-compatible endpoint with tool calling (Agent Settings → Local LLM URL); set `COMFYART_LOCAL_LLM_API_KEY` before starting ComfyUI if it needs a key |

Storyboard split, OCR, brand and memory extraction, reference notes and the Ideogram caption are single calls to the default Agent (`POST /comfyart/bot/complete`, no tools). ComfyArt never stores credentials. The agent works through the ComfyArt MCP server at `POST /comfyart/mcp` (look at the canvas, generate and edit images, videos, audio and 3D models, Edit Elements and mockups, place text, shapes, frames, web pages and slides, memory, skills, ask the user). Canvas tools are executed by the open ComfyArt tab of the project, so keep it open while the agent works. Chats are saved in a SQLite database at `user/__comfyart/data.db` and keep running when the panel is closed.

### Use ComfyArt from other agents

Turn on MCP in Agent Settings and add `http://127.0.0.1:8188/comfyart/mcp?project=<project-id>` to any MCP client, for example:

```bash
claude mcp add --transport http comfyart "http://127.0.0.1:8188/comfyart/mcp?project=<project-id>"
codex mcp add comfyart --url "http://127.0.0.1:8188/comfyart/mcp?project=<project-id>"
```

Setup for Claude Code, Codex, Gemini CLI, Qwen Code, Cursor, VS Code, Claude Desktop and your own scripts, tool timeouts and the full tool list are in the [MCP guide](https://comfyart.org/guides/mcp).

## Workflows and models

Every canvas action runs one of the API workflows in `workflows/` through ComfyUI's `/prompt`. They use core nodes unless noted.

| Action | Workflow | Models / custom nodes |
|---|---|---|
| Image generation, quick edit, edit text, expand, comment edits | `qwen-image-2.1-t2i`, `edit-qwen-image-2.1`, `outpaint-qwen-image-2.1` | `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_int8_convrot.safetensors`, `qwen_image_2.1_vae_bf16.safetensors` |
| Image generation (other models) | `z-image-turbo-t2i`, `flux2-klein-9b-t2i`, `flux3-klein-t2i`, `moss-image-t2i`, `qwen-image-2512-t2i`, `ideogram4-t2i` | `z_image_turbo_bf16` + `qwen_3_4b` + `ae`; `flux-2-klein-9b-nvfp4` + `qwen_3_8b_fp8mixed` + `flux2-vae`; `flux3-image-klein-int8-convrot` + `qwen3vl_4b_int8_convrot` + `flux2-vae`; `moss_image_sft_int8_convrot` + `qwen3.5_9b_w4a8_gptq` + `flux2-vae_small`; `qwen_image_2512_fp8_e4m3fn` + `qwen_2.5_vl_7b_fp8_scaled` + `qwen_image_vae` (loaded with the ComfyArt Precise UNET Loader node, see below); `ideogram4_fp8_scaled` + `ideogram4_unconditional_fp8_scaled` + `qwen3vl_8b_fp8_scaled` + `flux2-vae`; the default Agent writes the structured caption Ideogram expects (`ideogram4-caption.json`) |
| Reference modes (line art, depth, pose, …) | built in code | [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) preprocessors (MLSD, HED, normal and segmentation download their annotator weights on first use); with Qwen Image 2512 also `Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors` (controlnet) |
| Voice input | `transcribe-gemma4` | `gemma4_e4b_it_fp8_scaled.safetensors` (text_encoders) |
| Upscale | `upscale-ultrasharp-4x` | `4x-UltraSharp.pth` (upscale_models) |
| Remove background | `cutout-birefnet` | `birefnet.safetensors` (background_removal) |
| Eraser | `erase-lama` | [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes), `big-lama.pt` |
| Angles | `multiangle-qwen-image-2.1` | the Qwen Image 2.1 files above, plus [`qwen-image-2.1-qma-camera-angles.safetensors`](https://huggingface.co/gribbliest/qwen-image-2.1-qma-camera-angles) (loras) |
| Split layers | `layers-qwen-image-layered` | `qwen_image_layered_bf16.safetensors`, `qwen_image_layered_vae.safetensors`, `qwen_2.5_vl_7b_fp8_scaled.safetensors` |
| Animate, video generation, video extend | `i2v-minimax-h3`, `t2v-minimax-h3` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors`, `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`, `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, `minimax_h3_video_vae_fp16.safetensors`, `minimax_h3_audio_vae_fp32.safetensors` |
| Reference to video (images, videos, audio) | `r2v-minimax-h3` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors`, plus the text encoder and VAEs above |
| Motion control | `r2v-minimax-h3` + pose graph built in code | `minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors` (model_patches), `sdpose_wholebody_fp16.safetensors` (checkpoints), `rt_detr_v4-x-hgnet_fp16.safetensors` (diffusion_models) |
| Lip sync | `i2v-minimax-h3` + `MiniMaxH3AddGuide` | the image-to-video files above |
| Video editor (several clips, music, export) | built in code | ComfyArt Timeline Render node (ships with ComfyArt) |
| Edit Elements | built in code, `erase-lama` | `rapidocr` (Python package, `POST /comfyart/ocr`), SAM3 (`sam3.1_multiplex_fp16.safetensors`), LaMa |
| Mockup | `mockup-surface` | [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) Depth Anything V2 (`depth_anything_v2_vitl.pth`, downloaded on first use), `birefnet.safetensors` |
| Music (MiniMax Music 3) | `music-minimax3` | `minimax_music3_dit_fp16.safetensors` (diffusion_models), `minimax_music3_text_encoder_pruned_int8_convrot.safetensors` (text_encoders), `minimax_music3_dav.safetensors` (vae) |
| Music (ACE-Step 1.5) | `music-ace-step15` | `acestep_v1.5_xl_turbo_bf16.safetensors` (diffusion_models), `qwen_0.6b_ace15.safetensors` and `qwen_4b_ace15.safetensors` (text_encoders), `ace_1.5_vae.safetensors` (vae) |
| Music (YuE2) | `music-yue2` | `yue2_3b_int8_convrot.safetensors` (checkpoints) |
| Sound effects | `sfx-stable-audio` | `stable-audio-open-1.0.safetensors` (checkpoints), `t5-base.safetensors` (text_encoders) |
| Voiceover | `speech-kokoro` | [comfyui-kokoro](https://github.com/stavsap/comfyui-kokoro) |
| Voice cloning | `voice-clone-indextts` | [ComfyUI-Easy-IndexTTS2](https://github.com/yolain/ComfyUI-Easy-IndexTTS2) |
| Image to 3D | `image-to-3d-trellis2` | `trellis_2_int8_convrot.safetensors`, `trellis_2_shape_vae_bf16.safetensors`, `trellis_2_texture_vae_bf16.safetensors`, `dino_v3_L_naf_fp32.safetensors` (clip_vision), `birefnet.safetensors` |
| Image to 3D (Pixal3D) | `image-to-3d-pixal3d` | `pixal3d_int8_convrot.safetensors`, `moge_2_vitl_normal_fp16.safetensors` (geometry_estimation), plus the TRELLIS.2 VAEs, `dino_v3_L_naf_fp32.safetensors` and `birefnet.safetensors` above |
| Multi-view to 3D (Pixal3D) | `image-to-3d-pixal3d-multiview` | `pixal3d_multiview_int8_convrot.safetensors`, plus the TRELLIS.2 VAEs, `dino_v3_L_naf_fp32.safetensors` and `birefnet.safetensors` above |

## Nodes and routes

- `web/comfyart.js` adds the ComfyArt button to ComfyUI's top bar (also in Comfy Desktop).
- `ComfyArt Precise UNET Loader` loads a diffusion model with manual cast ops. ComfyUI's `--fast fp8_matrix_mult` turns unscaled fp8 checkpoints such as Qwen Image 2512 into noise; this loader skips that path for the model it loads.
- `/comfyart/bot/*` (chats, send, stop, branch, answers), `/comfyart/settings` and `/comfyart/mcp` serve the Agent.
- `POST /comfyart/cloud/prompt`, `GET /comfyart/cloud/history/{job}` and `POST /comfyart/cloud/cancel/{job}` forward jobs to Comfy Cloud with `COMFY_API_KEY`.
- `/comfyart/instances` lists, adds, edits and removes LAN instances; `/comfyart/instances/status` reports which are online with their queue and diffusion models. `POST /comfyart/remote/prompt` picks a machine (`target` is an instance id or `auto`) and queues the job there; `GET /comfyart/remote/history/{instance}/{job}` and `POST /comfyart/remote/cancel/{instance}/{job}` follow it.
- `POST /comfyart/pdf` renders up to 30 pages of an uploaded PDF to PNG files in `input/comfyart/pdf/` and returns them with each page's text.
- `POST /comfyart/ocr` reads the text lines of an image (RapidOCR, on device) and returns each line with its box.

## Development

`npm run dev` starts Vite with `/api` proxied to `http://127.0.0.1:8188` (override with `COMFY_URL`).

## License

ComfyArt is MIT licensed. The Agent backend in `bot/` and `api/` is adapted from [ComfyTV](https://github.com/jtydhr88/ComfyTV)'s bot (MIT), including providers co-authored by Pengjingyu1992 (DeepSeek Harness, Local LLM, Codex), MuAIGC (Codex, Qwen Code) and Goldlionren (Codex). The canvas is the [tldraw SDK](https://tldraw.dev), which is not: it is bundled in `dist/` under its own license, copied in `licenses/tldraw-LICENSE.md`. Served from `localhost` or plain `http` it runs in development mode without a license key and shows a small "Get a license for production" badge.
