from __future__ import annotations

import base64
import io

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


def _resolve_target_layer(model: torch.nn.Module, model_name: str) -> torch.nn.Module:
    name = model_name.lower()
    if "efficientnet" in name and hasattr(model, "features"):
        return model.features[-1]
    if "mobilenet" in name and hasattr(model, "features"):
        return model.features[-1]

    conv_layers = [m for m in model.modules() if isinstance(m, torch.nn.Conv2d)]
    if not conv_layers:
        raise ValueError("No convolution layer found for Grad-CAM.")
    return conv_layers[-1]


def _overlay_heatmap(image_np: np.ndarray, cam: np.ndarray) -> np.ndarray:
    cam_uint8 = np.uint8(np.clip(cam * 255, 0, 255))
    heatmap = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    overlay = np.clip(0.45 * heatmap + 0.55 * image_np, 0, 255).astype(np.uint8)
    return overlay


def image_to_base64(image: np.ndarray) -> str:
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generate_gradcam_base64(
    model: torch.nn.Module,
    model_name: str,
    input_tensor: torch.Tensor,
    image: Image.Image,
    class_idx: int,
) -> str:
    target_layer = _resolve_target_layer(model, model_name)
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def forward_hook(_module, _inp, out):
        activations.append(out.detach())

    def backward_hook(_module, _grad_in, grad_out):
        gradients.append(grad_out[0].detach())

    handle_forward = target_layer.register_forward_hook(forward_hook)
    handle_backward = target_layer.register_full_backward_hook(backward_hook)

    try:
        device = next(model.parameters()).device
        image_tensor = input_tensor.to(device)
        logits = model(image_tensor)
        score = logits[:, class_idx].sum()
        model.zero_grad(set_to_none=True)
        score.backward()

        if not activations or not gradients:
            raise RuntimeError("Grad-CAM hooks did not capture activations/gradients.")

        activation = activations[-1]
        gradient = gradients[-1]
        weights = gradient.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * activation).sum(dim=1, keepdim=True))
        cam = F.interpolate(
            cam, size=(image.height, image.width), mode="bilinear", align_corners=False
        )
        cam_np = cam.squeeze().cpu().numpy()
        cam_np = (cam_np - cam_np.min()) / (cam_np.max() - cam_np.min() + 1e-8)

        image_np = np.array(image.convert("RGB"))
        overlay = _overlay_heatmap(image_np, cam_np)
        return image_to_base64(overlay)
    finally:
        handle_forward.remove()
        handle_backward.remove()


def generate_heuristic_heatmap_base64(image: Image.Image) -> str:
    image_rgb = image.convert("RGB")
    image_np = np.array(image_rgb)
    resized = np.array(image_rgb.resize((224, 224))).astype(np.float32)
    r, g, b = resized[:, :, 0], resized[:, :, 1], resized[:, :, 2]

    yellow_stress = np.clip((r + g - 1.45 * b) / 255.0, 0, 1)
    brown_stress = np.clip((r - 0.75 * g - 0.75 * b) / 255.0, 0, 1)
    dark_stress = np.clip((95 - (r + g + b) / 3.0) / 95.0, 0, 1)
    stress_map = np.clip(0.4 * yellow_stress + 0.85 * brown_stress + 0.65 * dark_stress, 0, 1)

    stress_map = cv2.resize(stress_map, (image_np.shape[1], image_np.shape[0]))
    overlay = _overlay_heatmap(image_np, stress_map)
    return image_to_base64(overlay)

