# Validation Checklist

Use this checklist when testing `thermal-ctrl-harness` on real hardware.

## Environment
- GPU model and SKU
- Driver version
- CUDA version
- vLLM or TensorRT-LLM version
- Whether `nvidia-smi --query-gpu=memory.temp` reports values

## Baseline
1. Start your serving stack without the controller.
2. Run a workload large enough to create sustained memory pressure.
3. Capture:
   - p50 and p99 latency
   - memory temperature
   - batch size
   - any Grafana screenshots or Prometheus samples

## Controller run
1. Start the runtime with `--enable-admin-api`.
2. Start `thermal-ctrl-harness`.
3. Re-run the same workload.
4. Capture:
   - pre-throttle temperature
   - throttle trigger temperature
   - reduced batch size
   - recovered temperature
   - new p50 and p99 latency

## Questions to answer
- Did the controller reduce batch size when temperature crossed the threshold?
- Did memory temperature stop climbing after the cut?
- Did p99 latency improve?
- Did the admin endpoints work as expected?
- Did the controller logs match the Grafana timeline?

## What to include in a report
- Exact command lines
- Relevant `nvidia-smi` output
- Controller logs
- Grafana screenshots or metric snippets
- Any 404s or admin API incompatibilities
