# Ornith manual test (retired)

The October 8 trial temporarily replaced KAT with Ornith 1.5 35B-A3B for hands-on OpenCode testing. It used the verified official Q4_K_M GGUF with llama.cpp, not Colibri.

## Retirement — October 13, 2026

At the user's request, the Ornith service was stopped and disabled. Its model weights, service unit, dedicated credential copy and unused runtime image were removed. The weight file occupied 21,713,463,040 bytes. Historical benchmark results remain available.

The coding endpoint now uses the existing **KAT-Coder V2.5 Dev on Colibri**. No replacement model was downloaded.

The workstation's OpenCode default and `deep` agent use the KAT thinking profile:

- Thinking enabled, with `reasoning_effort: high`.
- Context capacity: 65,536 tokens.
- Output limit: 8,192 tokens, including reasoning.
- Existing authentication, permissions and other agent settings retained.

The Colibri renderer treats `high` as enabling thinking; it does not implement a separate reasoning-effort scale. Existing sessions may retain their previous model selection; start a new session or select the KAT deep profile.

Ollama was not installed on the server at retirement. The application assistant's separate Colibri service and ongoing training were preserved.

## Historical evidence

The [October 8 activation record](../benchmark/runs/2026-10-07-ornith/manual-activation.json) describes the former Ornith trial. It is not a description of the current deployment.

The [benchmark results](../benchmark/results.md) retain the original KAT and Ornith measurements. Ornith's deleted weights would need to be obtained and verified again before reproducing that trial.
