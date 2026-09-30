"""Tests for core.errors."""
from core import errors


# ═══════════════════════════════════════════════════════════════
#  describe()
# ═══════════════════════════════════════════════════════════════
class TestDescribe:
    def test_known_code(self):
        assert errors.describe("E020") == "Whisper failed"

    def test_unknown_code_returns_unknown(self):
        assert errors.describe("Z999") == errors.CODES["E099"]

    def test_all_codes_have_description(self):
        for code in errors.CODES:
            assert errors.describe(code)  # non-empty string


# ═══════════════════════════════════════════════════════════════
#  classify() — exception types
# ═══════════════════════════════════════════════════════════════
class TestClassifyByType:
    def test_file_not_found(self):
        assert errors.classify(FileNotFoundError("missing")) == "E001"

    def test_file_not_found_for_whisper(self):
        e = FileNotFoundError("whisper-cli not found")
        assert errors.classify(e) == "E010"

    def test_file_not_found_for_ffmpeg(self):
        e = FileNotFoundError("ffmpeg: no such file")
        assert errors.classify(e) == "E011"

    def test_permission_error(self):
        assert errors.classify(PermissionError("denied")) == "E004"

    def test_memory_error(self):
        assert errors.classify(MemoryError()) == "E030"

    def test_timeout_error(self):
        assert errors.classify(TimeoutError("timed out")) == "E022"


# ═══════════════════════════════════════════════════════════════
#  classify() — message keywords
# ═══════════════════════════════════════════════════════════════
class TestClassifyByMessage:
    def test_cancelled_english(self):
        assert errors.classify("Cancelled by user") == "E023"

    def test_cancelled_russian(self):
        assert errors.classify("Отменено пользователем") == "E023"

    def test_whisper_cli_not_found(self):
        assert errors.classify("whisper-cli: not found") == "E010"

    def test_whisper_failed(self):
        assert errors.classify("whisper error: code 1") == "E020"

    def test_ffmpeg_failed(self):
        assert errors.classify("ffmpeg failed to decode") == "E021"

    def test_out_of_memory(self):
        assert errors.classify("out of memory") == "E030"

    def test_no_space_left(self):
        assert errors.classify("No space left on device") == "E031"

    def test_unsupported_format(self):
        assert errors.classify("Unsupported media format") == "E003"


# ═══════════════════════════════════════════════════════════════
#  classify() — fallbacks
# ═══════════════════════════════════════════════════════════════
class TestClassifyFallback:
    def test_empty_string_returns_unknown(self):
        assert errors.classify("") == "E099"

    def test_random_message_returns_unknown(self):
        assert errors.classify("something weird happened") == "E099"

    def test_string_accepted(self):
        assert errors.classify("Cancelled") == "E023"

    def test_exception_accepted(self):
        assert errors.classify(RuntimeError("ffmpeg fail")) == "E021"

    def test_never_returns_none(self):
        for bad in ["", "?", "x", "Some random error"]:
            assert errors.classify(bad) is not None
