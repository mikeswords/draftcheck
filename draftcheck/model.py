import hashlib
import math
import os
import shutil
import ssl
import tempfile
from pathlib import Path
from threading import Lock
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / ".model"
MODEL_NAME = "Ettin 68M"
MODEL_CARD = "https://huggingface.co/Deckard618/textdet"
REVISION = "8b677e1bd3bc6421ae710352cda13ca65502147b"
ARTIFACTS = {
    "model.onnx": "d720129864ed3ecb7be5de85acf33d2fd62e5d4f8351de0e4cd1310de03adfe7",
    "tokenizer.json": "c24b1448c7b6762d0e4bf1c0b7b1e74a360039228f9ecf5a96a5fc789c07f49b",
    "LICENSE-ettin-68m.txt": "7e096e455b9dac457008fa960d25e64066416f417a71c7ad61fbdd65158ba9b9",
}
MAX_INPUT_TOKENS = 510  # The model's 512 positions include CLS and SEP.
_model = None
_lock = Lock()


class ModelUnavailable(Exception):
    pass


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def install_model(progress):
    import truststore

    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    MODEL_DIR.mkdir(exist_ok=True)
    for name, checksum in ARTIFACTS.items():
        path = MODEL_DIR / name
        if path.is_file() and digest(path) == checksum:
            continue

        url = f"{MODEL_CARD}/resolve/{REVISION}/ettin-68m/{name}"
        progress(f"Downloading {name}...")
        with tempfile.NamedTemporaryFile(dir=MODEL_DIR, delete=False) as temporary:
            temp_path = Path(temporary.name)
        try:
            with urlopen(url, timeout=60, context=context) as response, temp_path.open("wb") as output:
                shutil.copyfileobj(response, output)
            if digest(temp_path) != checksum:
                raise ModelUnavailable(f"Checksum failed for {name}. Run setup again.")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def model_files_present():
    return all((MODEL_DIR / name).is_file() for name in ARTIFACTS)


def ranges(length, count):
    return [(index * length // count, (index + 1) * length // count) for index in range(count)]


def signal(score):
    if score < 35:
        return "lower"
    if score >= 65:
        return "higher"
    return "uncertain"


class Detector:
    def __init__(self):
        import numpy
        import onnxruntime
        from tokenizers import Tokenizer

        if not model_files_present():
            raise ModelUnavailable("Detector files are missing. Run uv run --locked python -m draftcheck setup.")

        self.numpy = numpy
        self.tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
        self.cls = self.tokenizer.token_to_id("[CLS]")
        self.sep = self.tokenizer.token_to_id("[SEP]")
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        self.session = onnxruntime.InferenceSession(
            str(MODEL_DIR / "model.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
        )

    def _score(self, ids):
        inputs = self.numpy.asarray([[self.cls, *ids, self.sep]], dtype=self.numpy.int64)
        logits = self.session.run(
            None, {"input_ids": inputs, "attention_mask": self.numpy.ones_like(inputs)}
        )[0][0]
        human, ai = (float(item) for item in logits)
        # Stable softmax for the AI logit.
        maximum = max(human, ai)
        ai_weight = math.exp(ai - maximum)
        return 100 * ai_weight / (math.exp(human - maximum) + ai_weight)

    def evaluate(self, text):
        encoding = self.tokenizer.encode(text, add_special_tokens=False)
        ids = encoding.ids
        if not ids:
            return None, "unavailable", []

        windows = math.ceil(len(ids) / MAX_INPUT_TOKENS)
        if windows == 1:
            score = self._score(ids)
            method = "whole_draft"
            passages = self._passages(text, encoding, 2) if len(ids) >= 280 else []
        else:
            passages = self._passages(text, encoding, windows)
            score = sum(part["raw_score"] * part["tokens"] for part in passages) / len(ids)
            method = "weighted_passages"

        for passage in passages:
            del passage["raw_score"]
        return round(score, 1), method, passages

    def _passages(self, text, encoding, count):
        parts = []
        for start, end in ranges(len(encoding.ids), count):
            raw_score = self._score(encoding.ids[start:end])
            score = round(raw_score, 1)
            offsets = encoding.offsets[start:end]
            excerpt = " ".join(text[offsets[0][0]:offsets[-1][1]].split())
            parts.append(
                {
                    "excerpt": excerpt[:105].rstrip() + ("…" if len(excerpt) > 105 else ""),
                    "tokens": end - start,
                    "score": score,
                    "signal": signal(score),
                    "raw_score": raw_score,
                }
            )
        return parts


def get_detector():
    global _model
    with _lock:
        if _model is None:
            _model = Detector()
        return _model
