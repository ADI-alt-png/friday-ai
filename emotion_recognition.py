"""
FRIDAY Emotion Recognition
Uses deep learning (transformers) for emotion/sentiment analysis with text2emotion fallback.
Integrated with deep_learning.py module.
"""

try:
    from deep_learning import DLEmotionAnalyzer, dl_emotion, command_router
    dl_analyzer = DLEmotionAnalyzer()
    DL_READY = dl_analyzer.is_ready()
except ImportError:
    DL_READY = False

import text2emotion as te


def detect_emotion(text):
    """Detects emotion from input text using deep learning or fallback."""
    if DL_READY:
        try:
            result = dl_emotion(text)
            if result and result.get("dominant_emotion"):
                return result["dominant_emotion"], result.get("emotions", {})
        except Exception:
            pass
    emotions = te.get_emotion(text)
    dominant = max(emotions, key=emotions.get)
    return dominant, emotions


def get_sentiment(text):
    """Get sentiment label (positive/negative/neutral) using DL."""
    if DL_READY:
        try:
            result = dl_emotion(text)
            if result and result.get("sentiment"):
                return result["sentiment"], result.get("sentiment_score", 0.5)
        except Exception:
            pass
    return "neutral", 0.5


def analyze_emotion_response_modifier(text):
    """Get a response modifier based on detected emotion."""
    try:
        return command_router.get_emotion_response_modifier(dl_emotion(text))
    except Exception:
        return ""


if __name__ == "__main__":
    sample = "I am so happy and excited to see you!"
    dominant, emotions = detect_emotion(sample)
    print(f"Dominant emotion: {dominant}\nScores: {emotions}")
    sentiment, score = get_sentiment(sample)
    print(f"Sentiment: {sentiment} (confidence: {score:.2f})")
