"""KV prefix reuse on Qwen3.6: the shared contract, against the tiny fixture.

Qwen3.6 makes the contract stricter than a pure-attention engine would: three of
every four layers are DeltaNet, which carries a RECURRENT state rather than
position-indexed rows. Reuse keeps that state too, so a wrong reuse length
corrupts the recurrence and not just the attention. This engine also GROWS its
KV cache between turns, so tests/prefix_serve_harness.py's three-turn scenario
covers the per-head copy that growth performs.

Runs against the tiny random-init fixture the oracle job already builds
(tools/make_qwen36_tiny.py + tools/convert_qwen36.py): no checkpoint, no disk.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prefix_serve_harness import (PrefixReuseContract, ServeEngine,  # noqa: E402
                                  ensure_byte_tokenizer)

HERE = Path(__file__).resolve().parent.parent
ENGINE = HERE / ("qwen36.exe" if sys.platform == "win32" else "qwen36")
FIXTURE = Path(os.environ.get("QWEN36_TINY", HERE / "qwen36_tiny_c"))


@unittest.skipUnless(ENGINE.exists(), "qwen36 is not built")
# The metadata of this container is TRACKED (config.json, qwen36_meta.json and
# the README), so its presence says nothing about whether the weights were ever
# converted. Gate on a shard the conversion writes, or this skips nothing and
# fails on a checkout that never ran the converter.
@unittest.skipUnless((FIXTURE / "model-globals.safetensors").exists(),
                     "tiny qwen36 container is absent (tools/convert_qwen36.py)")
class Qwen36PrefixServeTest(PrefixReuseContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The fixture ships no tokenizer: the oracle path feeds ids directly.
        ensure_byte_tokenizer(FIXTURE)

    def spawn(self, log_prefix=True, reuse=True):
        return ServeEngine(ENGINE, ["8", "8"],
                           {"SNAP": str(FIXTURE), "SERVE": "1", "COLI_DENSE_I8": "0"},
                           log_prefix=log_prefix, reuse=reuse)

    def test_cancel_during_prefill_does_not_process_the_whole_prompt(self):
        engine = ServeEngine(
            ENGINE,
            ["8", "8"],
            {"SNAP": str(FIXTURE), "SERVE": "1", "COLI_DENSE_I8": "0",
             "QWEN36_SERVE_PREFILL_CHUNK": "1"},
            log_prefix=True,
        )
        self.addCleanup(engine.close)
        prompt = b"x" * 400
        engine.p.stdin.write(
            f"SUBMIT cancel-prefill 0 {len(prompt)} 4 0 1\n".encode()
            + prompt + b"\n"
        )
        engine.p.stdin.flush()

        while True:
            line = engine.p.stdout.readline()
            self.assertTrue(line, "engine exited before accepting cancellation test")
            accepted = line.decode("latin-1").strip()
            if accepted.startswith("ACCEPT cancel-prefill "):
                break
        engine.p.stdin.write(b"CANCEL cancel-prefill\n")
        engine.p.stdin.flush()

        while True:
            line = engine.p.stdout.readline()
            self.assertTrue(line, "engine exited before acknowledging cancellation")
            text = line.decode("latin-1").strip()
            if text.startswith("DATA cancel-prefill "):
                self.fail("engine generated data before honoring a prefill cancellation")
            if text.startswith("ERROR cancel-prefill "):
                self.assertEqual(text, "ERROR cancel-prefill CANCELLED")
                break

        # Cancellation must not poison the persistent process or its next turn.
        actual = engine.ask("after-cancel", prompt + b"y", max_tok=4)
        fresh = self.spawn(log_prefix=False)
        self.addCleanup(fresh.close)
        self.assertEqual(actual, fresh.ask("fresh", prompt + b"y", max_tok=4))
        log = engine.close()
        self.assertNotIn("[PREFIX] reusing 400 of 401 prompt tokens", log,
                         "CANCEL was acknowledged only after all 400 prompt tokens ran")

    def test_chunked_prefill_matches_whole_prompt(self):
        prompts = [b"Repeated prefix. " * 20,
                   b"def process(items): return sorted(set(items))\n" * 7]
        for rows in (1, 7, 128):
            with self.subTest(rows=rows):
                chunked = ServeEngine(ENGINE, ["8", "8"], {
                    "SNAP": str(FIXTURE), "SERVE": "1", "COLI_DENSE_I8": "0",
                    "QWEN36_SERVE_PREFILL_CHUNK": str(rows)})
                whole = ServeEngine(ENGINE, ["8", "8"], {
                    "SNAP": str(FIXTURE), "SERVE": "1", "COLI_DENSE_I8": "0",
                    "QWEN36_SERVE_PREFILL_CHUNK": "0"})
                try:
                    for index, prompt in enumerate(prompts):
                        self.assertEqual(chunked.ask(f"chunk-{index}", prompt, max_tok=8),
                                         whole.ask(f"whole-{index}", prompt, max_tok=8))
                finally:
                    chunked.close()
                    whole.close()

    def test_stop_is_successful_and_cancel_remains_an_error(self):
        for slots in (1, 2):
            for command in ("STOP", "CANCEL"):
                with self.subTest(slots=slots, command=command):
                    engine = ServeEngine(ENGINE, ["8", "8"], {
                        "SNAP": str(FIXTURE), "SERVE": "1", "COLI_DENSE_I8": "0",
                        "KV_SLOTS": str(slots), "Q36_MAXT": "1024"})
                    try:
                        prompt = b"test normal stop"
                        engine.p.stdin.write(f"SUBMIT control 0 {len(prompt)} 128 0 1\n".encode() + prompt + b"\n")
                        engine.p.stdin.flush()
                        sent = False
                        while True:
                            line = engine.p.stdout.readline()
                            self.assertTrue(line, "engine exited before terminal frame")
                            text = line.decode("latin-1").strip()
                            if text.startswith("DATA control "):
                                engine.p.stdout.read(int(text.split()[2]))
                                engine.p.stdout.readline()
                                if not sent:
                                    engine.p.stdin.write(f"{command} control\n".encode())
                                    engine.p.stdin.flush()
                                    sent = True
                            if text.startswith(("DONE control ", "ERROR control ")):
                                self.assertTrue(sent)
                                if command == "STOP":
                                    self.assertTrue(text.startswith("DONE control STAT "), text)
                                    self.assertEqual(text.split()[-1], "0", "STOP must not be length-limited")
                                else:
                                    self.assertEqual(text, "ERROR control CANCELLED")
                                break
                        engine.ask("after-control", b"still responsive", max_tok=1)
                    finally:
                        engine.close()


if __name__ == "__main__":
    unittest.main()
