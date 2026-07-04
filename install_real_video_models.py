import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


BASE = Path(__file__).resolve().parent
COMFY = BASE / "external" / "ComfyUI"
MODELS = COMFY / "models"
HF_CACHE = BASE / "data" / "huggingface_cache"

os.environ["HF_HOME"] = str(HF_CACHE)
os.environ["HF_HUB_CACHE"] = str(HF_CACHE / "hub")
os.environ["TRANSFORMERS_CACHE"] = str(HF_CACHE / "transformers")
os.environ["HF_XET_CACHE"] = str(HF_CACHE / "xet")


INSTALL_LOCK = BASE / "data" / "install_real_video_models.lock"


def acquire_install_lock():
    INSTALL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    payload = f"pid={os.getpid()}\nstarted={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    try:
        fd = os.open(str(INSTALL_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        return True
    except FileExistsError:
        age = ""
        try:
            age = f" seit {int(time.time() - INSTALL_LOCK.stat().st_mtime)}s"
        except Exception:
            pass
        raise SystemExit(f"Installer laeuft bereits{age}. Kein zweiter Download gestartet: {INSTALL_LOCK}")


def release_install_lock():
    try:
        if INSTALL_LOCK.exists():
            INSTALL_LOCK.unlink()
    except Exception:
        pass


BEST_MODELS = [
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "T2V/Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "fp8_scaled_kj",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors",
        MODELS / "diffusion_models" / "WanVideo",
    ),
    (
        "Kijai/WanVideo_comfy",
        "fantasytalking_fp16.safetensors",
        MODELS / "diffusion_models" / "WanVideo",
    ),
    (
        "Kijai/WanVideo_comfy",
        "umt5-xxl-enc-bf16.safetensors",
        MODELS / "text_encoders",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Wan2_1_VAE_bf16.safetensors",
        MODELS / "vae" / "wanvideo",
    ),
    (
        "Kijai/WanVideo_comfy",
        "open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors",
        MODELS / "clip_vision",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
        MODELS / "loras" / "WanVideo",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        MODELS / "loras" / "WanVideo",
    ),
]


ULTRA_MODELS = [
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "InfiniteTalk/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "InfiniteTalk",
        "Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "InfiniteTalk/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "InfiniteTalk",
        "Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "WanVideo_2_1_Multitalk_14B_fp8_e4m3fn.safetensors",
        MODELS / "diffusion_models" / "WanVideo",
        "WanVideo_2_1_Multitalk_14B_fp8_e4m3fn.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "TI2V/Ovi/Wan2_2_Ovi_Video_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "Ovi",
        "Wan2_2_Ovi_Video_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "TI2V/Ovi/Wan2_2_Ovi_Audio_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "Ovi",
        "Wan2_2_Ovi_Audio_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Wan2_2_VAE_bf16.safetensors",
        MODELS / "vae",
        "Wan2_2_VAE_bf16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Ovi/mmaudio_vae_16k_bf16.safetensors",
        MODELS / "audio_encoders",
        "mmaudio_vae_16k_bf16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "Ovi/mmaudio_vocoder_bigvgan_best_netG_bf16.safetensors",
        MODELS / "audio_encoders",
        "mmaudio_vocoder_bigvgan_best_netG_bf16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "SteadyDancer/Wan21_SteadyDancer_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "SteadyDancer",
        "Wan21_SteadyDancer_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "WanMove/Wan21-WanMove_fp8_scaled_e4m3fn_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "WanMove",
        "Wan21-WanMove_fp8_scaled_e4m3fn_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "2_2",
        "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors",
        MODELS / "loras" / "WanVideo" / "LoRAs" / "Wan22_relight",
        "WanAnimate_relight_lora_fp16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "Fun/Wan2_2-Fun-Control-A14B-HIGH_fp8_e4m3fn_scaled_KJ_fixed.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "2_2" / "Fun",
        "Wan2_2-Fun-Control-A14B-HIGH_fp8_e4m3fn_scaled_KJ_fixed.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "Fun/Wan2_2-Fun-Control-A14B-LOW_fp8_e4m3fn_scaled_KJ_fixed.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "2_2" / "Fun",
        "Wan2_2-Fun-Control-A14B-LOW_fp8_e4m3fn_scaled_KJ_fixed.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "Fun/Wan2_2-Fun-Control-Camera-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "2_2" / "Fun",
        "Wan2_2-Fun-Control-Camera-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy_fp8_scaled",
        "I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "2_2",
        "Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors",
        MODELS / "loras" / "WanVideo" / "Wan22-Lightning",
        "Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-A14B-4steps-lora_HIGH_fp16.safetensors",
        MODELS / "loras" / "WanVideo" / "Wan22-Lightning",
        "Wan2.2-Lightning_T2V-A14B-4steps-lora_HIGH_fp16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "FlashVSR/Wan2_1-T2V-1_3B_FlashVSR_fp32.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "FlashVSR",
        "Wan2_1-T2V-1_3B_FlashVSR_fp32.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "FlashVSR/Wan2_1_FlashVSR_LQ_proj_model_bf16.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "FlashVSR",
        "Wan2_1_FlashVSR_LQ_proj_model_bf16.safetensors",
    ),
    (
        "Kijai/WanVideo_comfy",
        "FlashVSR/Wan2_1_FlashVSR_TCDecoder_fp32.safetensors",
        MODELS / "diffusion_models" / "WanVideo" / "FlashVSR",
        "Wan2_1_FlashVSR_TCDecoder_fp32.safetensors",
    ),
]


WORKFLOWS = [
    (
        "wanvideo_2_1_14B_T2V_example_03.json",
        "jarvis_wan_t2v_best.json",
        {
            "WanVideo\\\\Lightx2v\\\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors":
                "WanVideo\\\\Lightx2v\\\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
        },
    ),
    (
        "wanvideo_2_1_14B_I2V_FantasyTalking_example_01.json",
        "jarvis_wan_talking_avatar_best.json",
        {
            "clip_vision_h.safetensors": "open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors",
        },
    ),
]


ULTRA_WORKFLOWS = [
    (
        "wanvideo_2_2_5B_Ovi_image_to_video_audio_example_01.json",
        "jarvis_wan_ovi_audio_ultra.json",
        {
            "WanVideo/Ovi/Wan_2_1_Ovi_video_model_bf16.safetensors":
                "WanVideo/Ovi/Wan2_2_Ovi_Video_fp8_e4m3fn_scaled_KJ.safetensors",
            "WanVideo/Ovi/Wan_2_1_Ovi_audio_model_bf16.safetensors":
                "WanVideo/Ovi/Wan2_2_Ovi_Audio_fp8_e4m3fn_scaled_KJ.safetensors",
            "mmaudio_vae_16k_fp32.safetensors": "mmaudio_vae_16k_bf16.safetensors",
            "mmaudio_vocoder_bigvgan_best_netG_fp32.safetensors": "mmaudio_vocoder_bigvgan_best_netG_bf16.safetensors",
        },
    ),
    (
        "wanvideo_2_1_14B_I2V_InfiniteTalk_example_03.json",
        "jarvis_wan_infinitetalk_multi_ultra.json",
        {},
    ),
    (
        "wanvideo_2_1_14B_V2V_InfiniteTalk_example_02.json",
        "jarvis_wan_infinitetalk_v2v_ultra.json",
        {},
    ),
    (
        "wanvideo_2_1_14B_SteadyDancer_pose_control_example_01.json",
        "jarvis_wan_steadydancer_pose_ultra.json",
        {
            "WanVideo\\\\SteadyDancer\\\\Wan2.1-SteadyDancer_fp8_scaled_KJ.safetensors":
                "WanVideo\\\\SteadyDancer\\\\Wan21_SteadyDancer_fp8_e4m3fn_scaled_KJ.safetensors",
        },
    ),
    (
        "wanvideo_2_1_14B_WanMove_I2V_example_01.json",
        "jarvis_wanmove_i2v_ultra.json",
        {},
    ),
    (
        "wanvideo_WanAnimate_example_01.json",
        "jarvis_wananimate_ultra.json",
        {
            "WanVideo\\\\WanAnimate_relight_lora_fp16.safetensors":
                "WanVideo\\\\LoRAs\\\\Wan22_relight\\\\WanAnimate_relight_lora_fp16.safetensors",
        },
    ),
    (
        "wanvideo_2_2_Fun_control_example_03.json",
        "jarvis_wan_fun_control_ultra.json",
        {
            "WanVideo\\\\Lightx2v\\\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors":
                "WanVideo\\\\Lightx2v\\\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
        },
    ),
    (
        "wanvideo_2_2_Fun_control_camera_example_01.json",
        "jarvis_wan_fun_control_camera_ultra.json",
        {},
    ),
    (
        "wanvideo_1_3B_FlashVSR_upscale_example.json",
        "jarvis_wan_flashvsr_upscale_ultra.json",
        {
            "Wan2_1_FlashVSR_TCDecoder_fp32.safetensors": "WanVideo\\\\FlashVSR\\\\Wan2_1_FlashVSR_TCDecoder_fp32.safetensors",
        },
    )
]


COMMON_REPLACEMENTS = {
    "clip_vision_h.safetensors": "open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors",
}


def ensure_huggingface_hub():
    try:
        import huggingface_hub  # noqa: F401
        return
    except Exception:
        pass
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "huggingface_hub[cli]"])


def download_file(repo_id: str, filename: str, local_dir: Path, dest_name: str | None = None):
    from huggingface_hub import hf_hub_download

    local_dir.mkdir(parents=True, exist_ok=True)
    target = local_dir / (dest_name or filename)
    if target.exists() and target.stat().st_size > 1024 * 1024:
        print(f"OK schon da: {target}")
        return target
    print(f"LADE: {repo_id}/{filename}")
    if dest_name:
        cached = Path(hf_hub_download(repo_id=repo_id, filename=filename, resume_download=True))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, target)
        return target
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
    )


def download_wav2vec():
    from huggingface_hub import snapshot_download

    target = MODELS / "transformers" / "facebook" / "wav2vec2-base-960h"
    if (target / "model.safetensors").exists():
        print(f"OK schon da: {target}")
        return
    print("LADE: facebook/wav2vec2-base-960h fuer Lippenbewegung")
    snapshot_download(
        repo_id="facebook/wav2vec2-base-960h",
        local_dir=str(target),
        local_dir_use_symlinks=False,
        allow_patterns=[
            "config.json",
            "feature_extractor_config.json",
            "model.safetensors",
            "preprocessor_config.json",
            "special_tokens_map.json",
            "tokenizer_config.json",
            "vocab.json",
        ],
    )


def copy_workflows(include_ultra: bool):
    src = COMFY / "custom_nodes" / "ComfyUI-WanVideoWrapper" / "example_workflows"
    dst = BASE / "comfyui_video_workflows"
    dst.mkdir(parents=True, exist_ok=True)
    items = list(WORKFLOWS) + (list(ULTRA_WORKFLOWS) if include_ultra else [])
    for src_name, dst_name, replacements in items:
        source = src / src_name
        if not source.exists():
            print(f"FEHLT Workflow-Vorlage: {source}")
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        merged = dict(COMMON_REPLACEMENTS)
        merged.update(replacements)
        for old, new in merged.items():
            text = text.replace(old, new)
        out = dst / dst_name
        out.write_text(text, encoding="utf-8")
        print(f"Workflow installiert: {out}")


def verify_nodes():
    needed = [
        COMFY / "custom_nodes" / "ComfyUI-WanVideoWrapper",
        COMFY / "custom_nodes" / "ComfyUI-VideoHelperSuite",
    ]
    missing = [p for p in needed if not p.exists()]
    if missing:
        raise SystemExit(
            "Video-Nodes fehlen. Starte zuerst install_video_ai.bat.\n"
            + "\n".join(str(p) for p in missing)
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ultra", action="store_true", help="Laedt zusaetzlich Ovi/InfiniteTalk-Modelle.")
    args = parser.parse_args()

    acquire_install_lock()
    try:
        if not COMFY.exists():
            raise SystemExit("ComfyUI fehlt. Starte zuerst install_comfyui.bat oder install_video_ai.bat.")

        verify_nodes()
        ensure_huggingface_hub()
        for item in BEST_MODELS:
            download_file(*item)
        download_wav2vec()
        if args.ultra:
            for item in ULTRA_MODELS:
                download_file(*item)
        copy_workflows(include_ultra=args.ultra)
        (BASE / "data").mkdir(exist_ok=True)
        (BASE / "data" / "real_video_models_ready.txt").write_text(
            "Jarvis KI Video Best Pack installiert.\n"
            f"Ultra: {args.ultra}\n"
            "Danach start_comfyui.bat starten.\n",
            encoding="utf-8",
        )
        print("\nFERTIG: Echte KI-Video-Modelle/Workflows sind vorbereitet.")
        print("Starte jetzt start_comfyui.bat und sage Jarvis: erstelle TikTok KI Video ...")
    finally:
        release_install_lock()


if __name__ == "__main__":
    main()
