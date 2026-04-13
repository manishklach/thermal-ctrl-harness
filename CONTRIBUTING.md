# Contributing

Thanks for taking a look at `thermal-ctrl-harness`.

## Before you open a PR
- Open an issue first for larger changes so the scope stays tight
- Keep changes focused on thermal control, observability, or deployment ergonomics
- Prefer small patches over broad refactors

## Local checks
Run the same checks CI runs before you push:

```bash
python -m pytest -q
python -m ruff check src tests
docker build -t thermal-ctrl-harness:test .
```

## Demo changes
- If you touch demo behavior, keep the simulated path honest and documented
- Do not remove the README note that `SIMULATE_THERMAL=1` is a demo mode

## Pull requests
- Describe the operational impact
- Call out config or API changes
- Include screenshots or GIFs for Grafana/dashboard updates when relevant

## Issue reports
Useful details:
- GPU model and driver version
- Whether temps came from `nvidia-smi` or simulation mode
- vLLM/TensorRT-LLM version
- Relevant controller logs or Prometheus samples
