"""
Deep Learning Module for FRIDAY
Adds transformer-based intent classification, emotion analysis, and image understanding.
"""

import os
import json
import time
import threading
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np

TORCH_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False
TEXT2EMOTION_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    import transformers
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

try:
    import text2emotion as te
    TEXT2EMOTION_AVAILABLE = True
except ImportError:
    pass

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "friday_output")

CACHE_DIR = os.path.join(OUTPUT_DIR, "dl_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

INTENT_LABELS = [
    "open_app", "close_app", "search_web", "open_website",
    "send_message", "read_screen", "capture_screen", "click_element",
    "type_text", "press_key", "system_command", "shutdown",
    "play_music", "check_time", "check_date", "check_weather",
    "read_news", "send_email", "create_file", "list_files",
    "set_reminder", "show_tasks", "system_monitor", "screen_monitor",
    "help_request", "general_chat", "memory_save", "memory_recall",
    "learn_topic", "research_memory",
]

EMOTION_LABELS = [
    "anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise"
]

SENTIMENT_LABELS = ["positive", "negative", "neutral"]


@dataclass
class DLResult:
    success: bool
    data: Any = None
    confidence: float = 0.0
    error: str = ""
    processing_time_ms: float = 0.0


class DLIntentClassifier:
    """Intent classification using zero-shot or distilled transformer models."""

    def __init__(self):
        self._lock = threading.Lock()
        self._classifier = None
        self._tokenizer = None
        self._model = None
        self._device = None
        self._ready = False
        self._use_zero_shot = True
        self._init_model()

    def _init_model(self):
        if not TRANSFORMERS_AVAILABLE or not TORCH_AVAILABLE:
            self._ready = False
            return
        try:
            import torch
            self._device = 0 if torch.cuda.is_available() else -1
            from transformers import pipeline
            self._classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=self._device,
            )
            self._use_zero_shot = True
            self._ready = True
        except Exception as e:
            print(f"[DL INTENT] Zero-shot init failed: {e}")
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                model_name = "distilbert-base-uncased"
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    model_name, num_labels=len(INTENT_LABELS)
                )
                self._use_zero_shot = False
                self._ready = True
            except Exception as e2:
                print(f"[DL INTENT] DistilBERT init failed: {e2}")
                self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def classify(self, text: str, top_k: int = 3) -> DLResult:
        start = time.time()
        if not text or not isinstance(text, str) or not text.strip():
            return DLResult(success=False, error="Empty input")
        if not self._ready:
            return DLResult(success=False, error="Model not loaded")
        try:
            with self._lock:
                if self._use_zero_shot:
                    result = self._classifier(
                        text[:512],
                        candidate_labels=INTENT_LABELS,
                        multi_label=False,
                    )
                    scores = list(zip(result["labels"], result["scores"]))
                else:
                    inputs = self._tokenizer(
                        text[:512], return_tensors="pt", truncation=True, padding=True
                    )
                    with torch.no_grad():
                        outputs = self._model(**inputs)
                    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                    scores = sorted(
                        [(INTENT_LABELS[i], float(probs[0][i]))
                         for i in range(len(INTENT_LABELS))],
                        key=lambda x: x[1], reverse=True,
                    )
            top = scores[:top_k]
            elapsed = (time.time() - start) * 1000
            return DLResult(
                success=True,
                data={"top_intents": top, "primary": top[0][0], "all_scores": dict(scores)},
                confidence=top[0][1],
                processing_time_ms=elapsed,
            )
        except Exception as e:
            return DLResult(success=False, error=str(e))

    def get_primary_intent(self, text: str) -> str:
        result = self.classify(text)
        if result.success and result.data:
            return result.data["primary"]
        return "general_chat"


class DLEmotionAnalyzer:
    """Deep learning based emotion and sentiment analysis."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sentiment_pipeline = None
        self._emotion_pipeline = None
        self._ready = False
        self._init_model()

    def _init_model(self):
        if not TRANSFORMERS_AVAILABLE or not TORCH_AVAILABLE:
            self._ready = False
            return
        try:
            import torch
            device = 0 if torch.cuda.is_available() else -1
            from transformers import pipeline
            self._sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=device,
            )
            try:
                self._emotion_pipeline = pipeline(
                    "text-classification",
                    model="bhadresh-savani/distilbert-base-uncased-emotion",
                    device=device,
                    top_k=None,
                )
            except Exception:
                self._emotion_pipeline = None
            self._ready = True
        except Exception as e:
            print(f"[DL EMOTION] Init failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def analyze(self, text: str) -> DLResult:
        start = time.time()
        if not text or not text.strip():
            return DLResult(success=False, error="Empty input")
        if not self._ready:
            return self._fallback_analyze(text)
        try:
            with self._lock:
                sentiment = self._sentiment_pipeline(text[:512])[0]
                emotions = None
                if self._emotion_pipeline:
                    raw_emotions = self._emotion_pipeline(text[:512])
                    if raw_emotions and isinstance(raw_emotions[0], list):
                        emotions = {
                            item["label"]: item["score"]
                            for item in raw_emotions[0]
                        }
            elapsed = (time.time() - start) * 1000
            return DLResult(
                success=True,
                data={
                    "sentiment": sentiment["label"].lower(),
                    "sentiment_score": sentiment["score"],
                    "emotions": emotions,
                    "dominant_emotion": max(emotions.items(), key=lambda x: x[1])[0]
                    if emotions else "neutral",
                },
                confidence=sentiment["score"],
                processing_time_ms=elapsed,
            )
        except Exception as e:
            return self._fallback_analyze(text)

    def _fallback_analyze(self, text: str) -> DLResult:
        if TEXT2EMOTION_AVAILABLE:
            try:
                import text2emotion as te
                emotions = te.get_emotion(text)
                dominant = max(emotions, key=emotions.get)
                return DLResult(
                    success=True,
                    data={
                        "sentiment": "neutral",
                        "sentiment_score": 0.5,
                        "emotions": emotions,
                        "dominant_emotion": dominant,
                    },
                    confidence=0.5,
                )
            except Exception:
                pass
        words = text.lower().split()
        joy = sum(1 for w in words if w in {"happy", "great", "awesome", "love", "wonderful"})
        anger = sum(1 for w in words if w in {"angry", "mad", "furious", "hate"})
        sadness = sum(1 for w in words if w in {"sad", "upset", "crying", "miserable"})
        if joy > anger and joy > sadness:
            dominant = "joy"
        elif anger > sadness:
            dominant = "anger"
        elif sadness > 0:
            dominant = "sadness"
        else:
            dominant = "neutral"
        return DLResult(
            success=True,
            data={
                "sentiment": "positive" if dominant == "joy" else "negative" if dominant in ("anger", "sadness") else "neutral",
                "sentiment_score": 0.5,
                "emotions": None,
                "dominant_emotion": dominant,
            },
            confidence=0.5,
        )


class DLImageAnalyzer:
    """Vision transformer based image understanding."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pipe = None
        self._ready = False
        self._init_model()

    def _init_model(self):
        if not TRANSFORMERS_AVAILABLE or not TORCH_AVAILABLE:
            self._ready = False
            return
        try:
            import torch
            device = 0 if torch.cuda.is_available() else -1
            from transformers import pipeline
            try:
                self._pipe = pipeline(
                    "image-text-to-text",
                    model="microsoft/git-base-coco",
                    device=device,
                )
            except Exception:
                self._pipe = pipeline(
                    "image-to-text",
                    model="microsoft/git-base-coco",
                    device=device,
                )
            self._ready = True
        except Exception as e:
            print(f"[DL IMAGE] Init failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def describe(self, image_path: str) -> DLResult:
        start = time.time()
        if not image_path or not os.path.exists(image_path):
            return DLResult(success=False, error="Image not found")
        if not self._ready:
            return DLResult(success=False, error="Vision model not loaded")
        try:
            from PIL import Image
            image = Image.open(image_path).convert("RGB")
            with self._lock:
                result = self._pipe(image)
            description = result[0]["generated_text"] if result else ""
            elapsed = (time.time() - start) * 1000
            return DLResult(
                success=True,
                data={"description": description, "image_path": image_path},
                confidence=0.85,
                processing_time_ms=elapsed,
            )
        except Exception as e:
            return DLResult(success=False, error=str(e))


class DLIntentMapper:
    """Maps deep learning intents to FRIDAY command handlers."""

    INTENT_COMMAND_MAP = {
        "open_app": lambda text: f"open {_extract_target(text, 'open')}",
        "close_app": lambda text: f"close application {_extract_target(text, 'close')}",
        "search_web": lambda text: f"search {_extract_after(text, ['search', 'google', 'find', 'look up'])}",
        "open_website": lambda text: f"open website {_extract_target(text, 'open')}",
        "send_message": lambda text: text,
        "read_screen": lambda text: "read my screen",
        "capture_screen": lambda text: "see my screen",
        "click_element": lambda text: f"click on {_extract_after(text, ['click', 'click on', 'tap'])}",
        "type_text": lambda text: text,
        "press_key": lambda text: text,
        "check_time": lambda text: "time",
        "check_date": lambda text: "date",
        "check_weather": lambda text: f"weather {_extract_after(text, ['weather', 'temperature'])}",
        "read_news": lambda text: f"news {_extract_after(text, ['news'])}",
        "set_reminder": lambda text: text,
        "show_tasks": lambda text: "show tasks",
        "screen_monitor": lambda text: text,
        "play_music": lambda text: text,
        "system_monitor": lambda text: "start monitoring",
        "shutdown": lambda text: "shutdown",
        "help_request": lambda text: text,
        "general_chat": lambda text: text,
    }

    @staticmethod
    def map_to_command(text: str, intent: str) -> str:
        mapper = DLIntentMapper.INTENT_COMMAND_MAP.get(intent)
        if mapper:
            return mapper(text)
        return text


def _extract_target(text: str, action: str) -> str:
    text = text.lower()
    patterns = [
        rf"(?:{action})\s+(?:the\s+)?(.+)",
        rf"(?:{action})\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _extract_after(text: str, prefixes: List[str]) -> str:
    text = text.lower()
    for prefix in prefixes:
        if prefix in text:
            parts = text.split(prefix, 1)
            if len(parts) > 1:
                return parts[1].strip()
    return text


class DLCommandRouter:
    """Routes commands using deep learning intent classification."""

    def __init__(self):
        self.intent_classifier = DLIntentClassifier()
        self.emotion_analyzer = DLEmotionAnalyzer()
        self.image_analyzer = DLImageAnalyzer()
        self._cache = {}
        self._cache_lock = threading.Lock()

    def route(self, text: str) -> Dict[str, Any]:
        start = time.time()
        cache_key = text.strip().lower()[:100]
        with self._cache_lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if time.time() - cached["time"] < 30:
                    return cached["data"]

        intent_result = self.intent_classifier.classify(text)
        emotion_result = self.emotion_analyzer.analyze(text)

        primary_intent = intent_result.data["primary"] if intent_result.success else "general_chat"
        command = DLIntentMapper.map_to_command(text, primary_intent)

        result = {
            "intent": primary_intent,
            "intent_confidence": intent_result.confidence if intent_result.success else 0.0,
            "top_intents": intent_result.data["top_intents"] if intent_result.success else [],
            "emotion": emotion_result.data if emotion_result.success else {"dominant_emotion": "neutral"},
            "mapped_command": command,
            "processing_time_ms": (time.time() - start) * 1000,
        }

        with self._cache_lock:
            self._cache[cache_key] = {"data": result, "time": time.time()}
            if len(self._cache) > 100:
                self._cache.clear()

        return result

    def analyze_screen_image(self, image_path: str) -> DLResult:
        return self.image_analyzer.describe(image_path)

    def get_emotion_response_modifier(self, emotion_data: Dict) -> str:
        dominant = emotion_data.get("dominant_emotion", "neutral")
        sentiment = emotion_data.get("sentiment", "neutral")
        modifiers = {
            "joy": " Acknowledged with positive feedback.",
            "anger": " Responding with calm and patience.",
            "sadness": " Responding with gentle reassurance.",
            "fear": " Responding with confidence and certainty.",
            "surprise": " Acknowledging the unexpected.",
            "disgust": " Noted.",
        }
        if sentiment == "negative" and dominant in modifiers:
            return modifiers[dominant]
        return ""


class DLTrainer:
    """Simple online learning for intent adaptation."""

    def __init__(self):
        self.history_file = os.path.join(CACHE_DIR, "dl_intent_history.jsonl")
        self._lock = threading.Lock()

    def record(self, text: str, intent: str, correct: bool = True):
        entry = {
            "text": text,
            "intent": intent,
            "correct": correct,
            "time": time.time(),
        }
        with self._lock:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    def get_stats(self) -> Dict:
        if not os.path.exists(self.history_file):
            return {"total": 0}
        correct = 0
        total = 0
        intent_counts = {}
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total += 1
                    if entry.get("correct"):
                        correct += 1
                    intent = entry.get("intent", "unknown")
                    intent_counts[intent] = intent_counts.get(intent, 0) + 1
                except Exception:
                    continue
        return {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0,
            "intent_distribution": intent_counts,
        }


def get_dl_status() -> Dict[str, bool]:
    return {
        "transformers": TRANSFORMERS_AVAILABLE,
        "torch": TORCH_AVAILABLE,
        "cuda": torch.cuda.is_available() if TORCH_AVAILABLE else False,
        "intent_classifier": DLIntentClassifier().is_ready(),
        "emotion_analyzer": DLEmotionAnalyzer().is_ready(),
        "image_analyzer": DLImageAnalyzer().is_ready(),
    }


command_router = DLCommandRouter()
dl_trainer = DLTrainer()


def dl_classify(text: str) -> Dict[str, Any]:
    return command_router.route(text)


def dl_emotion(text: str) -> Dict:
    result = command_router.emotion_analyzer.analyze(text)
    return result.data if result.success else {"dominant_emotion": "neutral"}


def dl_describe_image(image_path: str) -> str:
    result = command_router.analyze_screen_image(image_path)
    return result.data["description"] if result.success else ""


def dl_get_emotion_modifier(text: str) -> str:
    result = command_router.emotion_analyzer.analyze(text)
    if result.success:
        return command_router.get_emotion_response_modifier(result.data)
    return ""
