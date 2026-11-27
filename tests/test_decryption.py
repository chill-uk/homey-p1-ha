"""Tests for DLMS general-glo-ciphering decryption."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "custom_components" / "homey_p1"
FIXTURES_PATH = REPO_ROOT / "tests" / "fixtures"

package = types.ModuleType("custom_components.homey_p1")
package.__path__ = [str(MODULE_DIR)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules["custom_components.homey_p1"] = package

spec = importlib.util.spec_from_file_location(
    "custom_components.homey_p1.decryption", MODULE_DIR / "decryption.py"
)
decryption = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["custom_components.homey_p1.decryption"] = decryption
spec.loader.exec_module(decryption)

# Test-only keys (not belonging to any real meter).
EK = bytes.fromhex("000102030405060708090A0B0C0D0E0F")
AK = bytes.fromhex("D0D1D2D3D4D5D6D7D8D9DADBDCDDDEDF")
SYSTEM_TITLE = b"SAG5" + bytes.fromhex("00082800")
FRAME_COUNTER = bytes.fromhex("00013312")


def _telegram() -> str:
    raw = (FIXTURES_PATH / "austria_sagemcom_t210_d_r.txt").read_text()
    return raw.replace("\r\n", "\n").replace("\n", "\r\n")


def build_frame(plaintext: bytes, authenticated: bool = True) -> bytes:
    """Build a general-glo-ciphering frame the way an Austrian meter does."""
    security_control = 0x30 if authenticated else 0x20
    iv = SYSTEM_TITLE + FRAME_COUNTER
    encryptor = Cipher(algorithms.AES(EK), modes.GCM(iv)).encryptor()
    encryptor.authenticate_additional_data(bytes([security_control]) + AK)
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag[:12] if authenticated else b""
    payload = bytes([security_control]) + FRAME_COUNTER + ciphertext + tag
    length = len(payload)
    if length < 0x80:
        encoded_length = bytes([length])
    elif length < 0x100:
        encoded_length = bytes([0x81, length])
    else:
        encoded_length = bytes([0x82]) + length.to_bytes(2, "big")
    return bytes([0xDB, 0x08]) + SYSTEM_TITLE + encoded_length + payload


class DecryptFrameTests(unittest.TestCase):
    def test_decrypts_authenticated_frame(self) -> None:
        telegram = _telegram()
        frame = build_frame(telegram.encode())
        self.assertEqual(decryption.decrypt_frame(frame, EK, AK), telegram)

    def test_decrypts_without_authentication_key(self) -> None:
        telegram = _telegram()
        frame = build_frame(telegram.encode())
        self.assertEqual(decryption.decrypt_frame(frame, EK, None), telegram)

    def test_decrypts_encryption_only_frame(self) -> None:
        telegram = _telegram()
        frame = build_frame(telegram.encode(), authenticated=False)
        self.assertEqual(decryption.decrypt_frame(frame, EK, None), telegram)

    def test_wrong_authentication_key_is_rejected(self) -> None:
        frame = build_frame(_telegram().encode())
        with self.assertRaises(decryption.InvalidKeyError):
            decryption.decrypt_frame(frame, EK, bytes(16))

    def test_wrong_encryption_key_is_rejected_without_ak(self) -> None:
        frame = build_frame(_telegram().encode())
        with self.assertRaises(decryption.InvalidKeyError):
            decryption.decrypt_frame(frame, bytes(16), None)

    def test_rejects_plain_text(self) -> None:
        with self.assertRaises(decryption.DecryptionError):
            decryption.decrypt_frame(b"/XYZ5\\TEST\r\n!", EK, AK)


class FrameBufferTests(unittest.TestCase):
    def test_reassembles_split_frames(self) -> None:
        frame = build_frame(_telegram().encode())
        buffer = decryption.DLMSFrameBuffer()
        self.assertEqual(buffer.feed(frame[:7]), [])
        self.assertEqual(buffer.feed(frame[7:300]), [])
        self.assertEqual(buffer.feed(frame[300:]), [frame])

    def test_splits_merged_frames_and_skips_garbage(self) -> None:
        frame = build_frame(_telegram().encode())
        buffer = decryption.DLMSFrameBuffer()
        self.assertEqual(buffer.feed(b"\x00\x01" + frame + frame), [frame, frame])


class KeyHelperTests(unittest.TestCase):
    def test_normalize_key_accepts_portal_formatting(self) -> None:
        self.assertEqual(
            decryption.normalize_key("00:01 02-03 0405060708090a0b0c0d0e0f"), EK
        )

    def test_normalize_key_empty(self) -> None:
        self.assertIsNone(decryption.normalize_key(""))
        self.assertIsNone(decryption.normalize_key(None))

    def test_normalize_key_rejects_bad_length(self) -> None:
        with self.assertRaises(ValueError):
            decryption.normalize_key("0011")

    def test_looks_encrypted(self) -> None:
        self.assertTrue(decryption.looks_encrypted(build_frame(b"/x")))
        self.assertFalse(decryption.looks_encrypted(b"/XYZ5"))


if __name__ == "__main__":
    unittest.main()
