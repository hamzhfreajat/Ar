"""Pronunciation assessment by Azure AI Speech (the short-audio REST API, no SDK needed)."""
import base64
import json
import urllib.error
import urllib.request

# A word with one sound missed this badly cannot pass, however good the rest of it is
MISSED_SOUND = 30.0
MISSED_SOUND_CAP = 50.0


def assess(wav: bytes, text: str, key: str, region: str, timeout: float = 10.0) -> dict:
    """How well the recording says `text`. Returns the app's answer: ok, score, heard, words."""
    params = {"ReferenceText": text, "GradingSystem": "HundredMark", "Granularity": "Phoneme",
              "Dimension": "Comprehensive", "EnableMiscue": False}
    url = (f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
           "?language=en-US&format=detailed")
    request = urllib.request.Request(url, data=wav, method="POST", headers={
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        "Accept": "application/json",
        "Pronunciation-Assessment": base64.b64encode(json.dumps(params).encode("utf-8")).decode("ascii"),
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {"ok": False, "reason": "service"}
    return read_result(result)


def read_result(result: dict) -> dict:
    """Turns Azure's detailed answer into the app's."""
    best = (result.get("NBest") or [{}])[0]
    # The scores sit on the result itself, or under "PronunciationAssessment", depending on the API version
    scores = best.get("PronunciationAssessment") or best
    if result.get("RecognitionStatus") != "Success" or "AccuracyScore" not in scores:
        return {"ok": False, "reason": "not understood"}

    words, sounds = [], []
    for word in best.get("Words", []):
        assessed = word.get("PronunciationAssessment") or word
        words.append({"word": word.get("Word"), "accuracy": assessed.get("AccuracyScore"),
                      "error": assessed.get("ErrorType")})
        sounds += [(p.get("PronunciationAssessment") or p).get("AccuracyScore", 100.0) for p in word.get("Phonemes", [])]

    # PronScore is too kind: "yellow" for "hello" scored 86.8, because the service hears the
    # text it was told to expect. The sounds give it away ("h" 0, "eh" 6).
    score = float(scores["AccuracyScore"])
    if sounds and min(sounds) < MISSED_SOUND:
        score = min(score, MISSED_SOUND_CAP)
    return {"ok": True, "score": score, "accuracy": scores["AccuracyScore"],
            "heard": best.get("Display") or result.get("DisplayText") or "", "words": words}
