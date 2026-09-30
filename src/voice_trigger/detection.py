import re
import time
import unicodedata


def normalize(text):
    return unicodedata.normalize("NFKC", text).casefold().strip()


class KeywordDetector:
    def __init__(self, config):
        self.last_hits = {}
        self.configure(config)

    def configure(self, config):
        patterns = {}
        for keyword in config.keywords:
            normalized = normalize(keyword)
            if normalized in patterns:
                continue
            if re.search(r"[\u3400-\u9fff]", normalized):
                expression = r"\s*".join(re.escape(character) for character in normalized if not character.isspace())
            else:
                expression = r"\s+".join(re.escape(part) for part in normalized.split())
                expression = r"(?<!\w)" + expression + r"(?!\w)"
            patterns[normalized] = (keyword.strip(), re.compile(expression))
        self.patterns = patterns
        self.cooldown = config.cooldown_seconds
        self.last_hits = {key: value for key, value in self.last_hits.items() if key in patterns}

    def detect(self, text, now=None):
        now = time.monotonic() if now is None else now
        normalized = normalize(text)
        hits = []
        for key, (keyword, pattern) in self.patterns.items():
            last_hit = self.last_hits.get(key)
            if pattern.search(normalized) and (last_hit is None or now - last_hit >= self.cooldown):
                hits.append(keyword)
                self.last_hits[key] = now
        return hits
