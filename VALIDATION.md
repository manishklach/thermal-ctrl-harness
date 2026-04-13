# Hardware Validation Checklist

This repo is an RFC/prototype. The core hypothesis: HBM thermal throttling at ~85C causes p99 latency spikes on H200/H100 at long context. This daemon tries to prevent it by cutting batch size.

**We need you to validate if this is real.** If you have H100/H200/MI300X access, please run this and report back.

## 0. Sanity check - does the demo run?
```bash
git clone https://github.com/manishklach/thermal-ctrl-harness
cd thermal-ctrl-harness
SIMULATE_THERMAL=1 docker compose up -d
```
Open http://localhost:3000, run `python examples/load_gen.py`. You should see temp spike -> batch cut -> recovery.

If this fails, open a bug. Don't proceed to hardware tests.

## 1. Critical unknowns - test these first

Run on your GPU node and paste results in a GitHub issue using the "Hardware Validation Report" template.

### 1.1 Does `memory.temp` exist?
```bash
nvidia-smi --query-gpu=index,name,memory.temp --format=csv
```
**Report**: Does it print a column? What values do you see at idle vs under load?

**Why this matters**: If `memory.temp` isn't exposed on Hopper, the whole daemon breaks. We'd need NVML or DCGM instead.

### 1.2 Does vLLM admin API exist?
Start vLLM with the admin flag:
```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-70B \
  --max-model-len 131072 \
  --enable-admin-api
```
Then hit it:
```bash
curl http://localhost:8000/v1/admin/batch
```
**Report**: 200 OK with JSON, or 404? If 200, what fields does it return?

**Why this matters**: If `/v1/admin/batch` doesn't exist in v0.4.3, we need to write a vLLM scheduler plugin instead of shelling out.

### 1.3 Can you observe thermal throttling?
Run this while pushing 128K context requests:
```bash
nvidia-smi dmon -s pucvmet -o DT
```
**Report**: Do you see `pwr` drop or `gtemp/mtemp` hit 85C+? Do you see `thrm` flags? Screenshot or CSV.

**Why this matters**: If HBM never hits 85C in practice, this whole project is moot.

## 2. End-to-end test - if 1.1 and 1.2 pass

**Setup:**
1. Start vLLM with `--enable-admin-api --max-num-seqs 256`
2. Start thermal-ctrl-harness without `SIMULATE_THERMAL=1`
```bash
python src/thermal_guard.py --config configs/config.yaml
```

**Load:**
Run `examples/load_gen.py` or your own traffic gen to sustain 128K decode for 5 min.

**Watch:**
Grafana http://localhost:3000. You want to see:
1. `hbm_memory_temp_celsius` climb toward 85
2. `thermal_throttle_active` flip to 1
3. `vllm_max_num_seqs` drop: 256 -> 128 -> 64
4. `hbm_memory_temp_celsius` stabilize or drop
5. p99 latency in your load tester

**Report:**
1. Did the daemon detect the temp and cut batch?
2. Did `mtemp` actually drop after cutting batch? How long did it take?
3. Did p99 improve vs baseline run without the daemon?
4. Any crashes, API errors, or weird behavior?

## 3. AMD MI300X
If you have MI300X:
```bash
rocm-smi --showtemp
```
**Report**: What fields show up? Is there an HBM temp equivalent? We want to add ROCm support.

## 4. What to do if something fails

**No `memory.temp`**: We pivot to NVML `nvmlDeviceGetFieldValues` or DCGM. Open issue with your `nvidia-smi -q -d TEMPERATURE` output.

**No `/v1/admin/batch`**: We write a vLLM plugin. Open issue with vLLM version + logs.

**Temp never hits 85C**: Tell us your workload. Maybe this only matters for 192GB H200 at 256K context. That's still valuable data.

**Daemon crashes**: Paste logs. This is alpha code.

## 5. What success looks like

Post your Grafana screenshot showing:
`mtemp 84C -> throttle -> batch 256->64 -> mtemp 81C -> p99 4.2s->2.1s`

That screenshot is worth 1000 stars. We'll add you to `THANKS.md` and cite you in the blog.

---

**No GPU?** You can still help: review the code, suggest better cold-KV heuristics, or find docs on HBM throttle behavior.

**Questions**: Open an issue or ping me on X @OrbitHigher.
