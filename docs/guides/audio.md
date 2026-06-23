# Generate narrated audio

The audio pipeline extracts and cleans document text, splits it into chunks,
synthesizes each chunk, and concatenates the results.

## Local Qwen synthesis

```bash
screencastgen audio book.pdf --backend qwen --device cuda -o book.wav
```

Use a reference recording for voice cloning:

```bash
screencastgen audio book.pdf \
  --backend qwen \
  --model 1.7B \
  --ref-audio voice.wav \
  --ref-text "Transcript of the reference recording."
```

`--ref-text` can be omitted when the selected runtime can obtain the transcript
through the surrounding workflow. Supplying an accurate transcript directly is
the most predictable CLI path.

## Remote synthesis

```bash
screencastgen audio book.pdf \
  --backend remote \
  --tts-server-url http://gpu-vm:8100 \
  --tts-concurrency 4
```

Increase concurrency only when the remote server has enough workers and GPU
capacity. See the [remote GPU guide](remote-gpu.md) for server setup.

## Resume or restart

Chunk outputs and state are retained under the output directory. Re-running the
same command resumes incomplete work. Add `--clean` to synthesize everything
again, or `--no-concat` to retain chunks without creating the final audio file.

For every option, run `screencastgen audio --help` or consult the
[CLI reference](../reference/core/cli.md).
