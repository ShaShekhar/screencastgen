# Generate a LipSync Reader

The lip-sync pipeline combines narration, word alignment, and a reference face
video. LatentSync generates presenter clips delivered through the hosted reader
or a standalone offline reader ZIP. The offline reader ZIP is the recommended
portable output because it preserves the synchronized document, narration, and
presenter experience.

## Basic command

```bash
screencastgen lipsync book.pdf \
  --ref-audio voice.wav \
  --ref-video face.mp4 \
  --format reader
```

Use a short, clear reference recording and a roughly ten-second face video with
stable framing. Local LatentSync requires Linux or WSL2, an NVIDIA GPU, its
sidecar environment, and downloaded checkpoints.

## Output formats

| Format | Use case |
| --- | --- |
| `reader` | Hosted reader assets plus a standalone offline reader ZIP with document, narration, and movable presenter; this is the default and recommended output |
| `epub` | Text-and-narration accessibility export using Media Overlays; presenter omitted and reader support varies |

For reader layouts, configure `--face-position` and `--face-scale`. Choose
`--latentsync-preset small` for the fast 256px path or `quality` for the default
512px path.

To run inference elsewhere, combine the command with `--backend remote` and
the [remote GPU setup](remote-gpu.md).
