# Run with a remote GPU

Remote mode keeps document extraction and media composition on the client while
the GPU server performs TTS, alignment, transcription, and lip-sync inference.

## GPU host

```bash
python3 scripts/setup.py --profile local-gpu
source .venv/bin/activate
screencastgen-server \
  --backend qwen \
  --device cuda \
  --aligner whisperx \
  --lipsync-provider latentsync
```

The server listens on port `8100` by default. Put authentication and TLS in a
reverse proxy before exposing it beyond a trusted network.

## Client

```bash
python3 scripts/setup.py \
  --profile remote-client \
  --server-url http://gpu-vm:8100
source .venv/bin/activate
screencastgen doctor \
  --profile remote-client \
  --server-url http://gpu-vm:8100
```

Run a client pipeline with the remote backend:

```bash
screencastgen highlight book.pdf \
  --backend remote \
  --tts-server-url http://gpu-vm:8100
```

The remote lip-sync contract submits a job, polls its state, downloads the
result, and removes temporary server output. See the
[inference server](../reference/core/inference-server.md) and
[remote GPU client](../reference/core/remote-gpu-client.md) references for the
HTTP contract.
