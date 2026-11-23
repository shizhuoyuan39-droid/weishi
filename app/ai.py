"""Zero-shot Korean food recognition with CLIP.

This is a real model, not a mock: image -> CLIP embedding -> cosine similarity
against 30 Korean-food prompt sets -> softmax.  It runs on CPU and is intentionally
small enough for a student laptop.  Accuracy on real cafeteria trays is expected
to be moderate; the UI exposes top-3 and manual correction.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "data" / "cache"
HF_HOME = BASE_DIR / "data" / "hf"
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_HOME))
MODEL_NAME = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
PORTIONS = {"S": 0.75, "M": 1.0, "L": 1.25}


class FoodAI:
    def __init__(self, foods: list[dict[str, Any]]):
        self.foods = foods
        self.ready = False
        self.error: str | None = None
        self.model_name = MODEL_NAME
        self._torch = None
        self._model = None
        self._processor = None
        self._text_features = None
        self._load_seconds: float | None = None
        self._last_latency_ms: int | None = None

    def load(self) -> None:
        if self.ready:
            return
        started = time.time()
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            self._torch = torch
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._model = CLIPModel.from_pretrained(MODEL_NAME)
            self._model.eval()
            self._processor = CLIPProcessor.from_pretrained(MODEL_NAME)
            self._text_features = self._build_text_features()
            self.ready = True
            self._load_seconds = round(time.time() - started, 2)
            print(f"[ai] loaded {MODEL_NAME} in {self._load_seconds}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"
            self.ready = False
            print(f"[ai] load failed: {self.error}", flush=True)
            raise

    def _prompts_for(self, food: dict[str, Any]) -> list[str]:
        ko = food["ko"]
        return list(dict.fromkeys(food.get("prompts", []) + [
            f"a photo of {ko}, a Korean dish",
            f"a close up photo of {ko}",
            f"a Korean cafeteria tray with {ko}",
        ]))

    def _build_text_features(self):
        import torch

        prompts: list[str] = []
        owner: list[int] = []
        for idx, food in enumerate(self.foods):
            for prompt in self._prompts_for(food):
                prompts.append(prompt)
                owner.append(idx)
        key = hashlib.md5((MODEL_NAME + json.dumps(prompts, ensure_ascii=False)).encode("utf-8")).hexdigest()[:12]
        cache_file = CACHE_DIR / f"clip_text_{key}.pt"
        if cache_file.exists():
            try:
                payload = torch.load(cache_file, map_location="cpu")
                if payload.get("model") == MODEL_NAME:
                    print(f"[ai] text cache hit: {cache_file.name}", flush=True)
                    return payload["features"]
            except Exception:
                pass

        inputs = self._processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
        with torch.inference_mode():
            text = self._model.get_text_features(**inputs)
        if hasattr(text, "pooler_output"):
            text = text.pooler_output
        text = text / text.norm(dim=-1, keepdim=True)
        per_food = []
        for idx in range(len(self.foods)):
            vecs = text[[i for i, o in enumerate(owner) if o == idx]]
            vec = vecs.mean(dim=0)
            vec = vec / vec.norm()
            per_food.append(vec)
        features = torch.stack(per_food)
        torch.save({"model": MODEL_NAME, "features": features}, cache_file)
        print(f"[ai] text cache saved: {cache_file.name}", flush=True)
        return features

    def _classify(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        import torch

        inputs = self._processor(images=image, return_tensors="pt")
        with torch.inference_mode():
            feat = self._model.get_image_features(**inputs)
        if hasattr(feat, "pooler_output"):
            feat = feat.pooler_output
        feat = feat / feat.norm(dim=-1, keepdim=True)
        logits = 100.0 * (feat @ self._text_features.T)
        probs = logits.softmax(dim=-1)[0]
        top = torch.topk(probs, k=min(5, len(self.foods)))
        results = [
            {"food": self.foods[int(i)], "confidence": float(p)}
            for p, i in zip(top.values.tolist(), top.indices.tolist())
        ]
        return results, float(top.values[0])

    def _crops(self, image: Image.Image) -> list[tuple[str, Image.Image]]:
        w, h = image.size

        def box(x1, y1, x2, y2):
            return image.crop((int(w * x1), int(h * y1), int(w * x2), int(h * y2)))

        return [
            ("full", image),
            ("left", box(0.02, 0.10, 0.58, 0.92)),
            ("right", box(0.42, 0.10, 0.98, 0.92)),
            ("top", box(0.10, 0.02, 0.92, 0.62)),
            ("bottom", box(0.10, 0.38, 0.92, 0.98)),
        ]

    def predict(self, image_bytes: bytes) -> dict[str, Any]:
        if not self.ready:
            raise RuntimeError(self.error or "AI model is not ready")
        started = time.time()
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1024, 1024))

        full_results, full_conf = self._classify(image)
        chosen: dict[str, dict[str, Any]] = {
            full_results[0]["food"]["id"]: {
                "food": full_results[0]["food"],
                "confidence": full_results[0]["confidence"],
                "region": "full",
            }
        }
        for region, crop in self._crops(image)[1:]:
            results, top_conf = self._classify(crop)
            best = results[0]
            fid = best["food"]["id"]
            if fid in chosen:
                if best["confidence"] > chosen[fid]["confidence"]:
                    chosen[fid]["confidence"] = best["confidence"]
                continue
            if best["confidence"] >= 0.58 and len(chosen) < 3:
                chosen[fid] = {"food": best["food"], "confidence": best["confidence"], "region": region}

        items = []
        for item in chosen.values():
            food = item["food"]
            items.append({
                "food_id": food["id"],
                "name_ko": food["ko"],
                "name_zh": food["zh"],
                "serving": food["serving"],
                "portion": 1.0,
                "confidence": round(item["confidence"], 3),
                "region": item["region"],
                "nutrition": {
                    "kcal": food["kcal"],
                    "protein": food["protein"],
                    "carbs": food["carbs"],
                    "fat": food["fat"],
                    "sodium": food["sodium"],
                },
            })
        items.sort(key=lambda x: x["confidence"], reverse=True)
        latency_ms = int((time.time() - started) * 1000)
        self._last_latency_ms = latency_ms
        return {
            "engine": "clip-zero-shot",
            "model": MODEL_NAME,
            "latency_ms": latency_ms,
            "uncertain": full_conf < 0.25,
            "items": items,
            "alternatives": [
                {
                    "food_id": r["food"]["id"],
                    "name_ko": r["food"]["ko"],
                    "name_zh": r["food"]["zh"],
                    "confidence": round(r["confidence"], 3),
                    "nutrition": {
                        "kcal": r["food"]["kcal"],
                        "protein": r["food"]["protein"],
                        "carbs": r["food"]["carbs"],
                        "fat": r["food"]["fat"],
                        "sodium": r["food"]["sodium"],
                    },
                }
                for r in full_results
            ],
            "top_confidence": round(full_conf, 3),
        }

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "error": self.error,
            "model": MODEL_NAME,
            "engine": "clip-zero-shot",
            "load_seconds": self._load_seconds,
            "last_latency_ms": self._last_latency_ms,
            "classes": len(self.foods),
        }
