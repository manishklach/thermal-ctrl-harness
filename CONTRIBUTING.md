# Contributing to thermal-ctrl-harness

Thanks for checking this out. This is a systems RFC and simulation harness for thermal-aware inference control.

## How to help

**1. Test on real hardware**
If you have H100/H200/MI300X access, please run through `docs/validation_playbook.md` and open an issue with results. This is the highest-leverage contribution.

**2. Code**
PRs welcome for:
- NVML bindings to replace `nvidia-smi` shell-out
- AMD `rocm-smi` support
- vLLM scheduler plugin vs admin API
- Better cold-KV heuristics

**3. Docs**
Found a typo or unclear setup step? PR it.

## Dev setup
```bash
git clone https://github.com/manishklach/thermal-ctrl-harness
cd thermal-ctrl-harness
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

No GPU? Run the simulation harness:
```bash
python -m thermal_ctrl compare --baseline configs/baseline.yaml --controlled configs/simulated.yaml --seed 7
```

If you have accelerator access and want a concrete checklist, start with [VALIDATION.md](VALIDATION.md).

## Code style
- Python 3.9+
- `black`, `isort`, and `flake8`
- Type hints required for new code
- Tests for new logic in `tests/`

## PR process
1. Open an issue first for non-trivial changes
2. Keep PRs focused: 1 feature/fix per PR
3. CI must pass
4. Update README and docs if behavior changes

## Code of Conduct
Be respectful. Assume good intent. We're all debugging GPUs together.

## License
By contributing, you agree your code is MIT licensed.
