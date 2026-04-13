#!/usr/bin/env python3
import os, subprocess, time, requests, yaml, logging, signal, sys
from prometheus_client import start_http_server, Gauge
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

SIMULATE = os.getenv("SIMULATE_THERMAL") == "1" or "--simulate" in sys.argv

CONFIG_PATH = Path("/etc/thermal-ctrl/config.yaml")
DEFAULT_CONFIG = {
    "throttle_temp": 85, "recover_temp": 80, "poll_ms": 500,
    "vllm_admin": "http://localhost:8000/v1/admin",
    "migrate_pct": 0.1, "min_batch": 4, "max_batch": 256, "metrics_port": 9091
}

temp_gauge = Gauge('gpu_hbm_temp_celsius', 'HBM temperature per GPU', ['gpu'])
batch_gauge = Gauge('vllm_max_batch_size', 'Current max batch size')
throttle_gauge = Gauge('thermal_throttle_active', '1 if throttling')

class ThermalController:
    def __init__(self, cfg):
        self.cfg = cfg
        self.throttling = False
        self.current_batch = cfg["max_batch"] // 2
        self.running = True
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, *args):
        logging.info("Shutting down, restoring batch")
        self.set_vllm_batch(self.cfg["max_batch"], 0)
        self.running = False
        sys.exit(0)

    def get_hbm_temps(self):
        if SIMULATE:
            # Simulate 72C -> 84C -> 86C -> 82C over a short loop for demos.
            t = int(time.time()) % 20
            if t < 5:
                return [(0, 72)]
            if t < 10:
                return [(0, 84)]
            if t < 12:
                return [(0, 86)]
            return [(0, 82)]
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=index,memory.temp", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip()
            return [(int(i), int(t)) for i, t in [l.split(", ") for l in out.split("\n") if l]]
        except Exception as e:
            logging.error(f"nvidia-smi failed: {e}")
            return []

    def set_vllm_batch(self, max_batch, migrate_pct=0.0):
        try:
            r = requests.post(f"{self.cfg['vllm_admin']}/batch", 
                            json={"max_num_seqs": max_batch}, timeout=1)
            if migrate_pct > 0:
                requests.post(f"{self.cfg['vllm_admin']}/kv_migrate", 
                            json={"pct": migrate_pct}, timeout=1)
            r.raise_for_status()
            batch_gauge.set(max_batch)
            return True
        except Exception as e:
            logging.error(f"vLLM admin call failed: {e}")
            return False

    def run(self):
        start_http_server(self.cfg["metrics_port"])
        batch_gauge.set(self.current_batch)
        throttle_gauge.set(0)
        logging.info(f"Started. Metrics :{self.cfg['metrics_port']}. Poll {self.cfg['poll_ms']}ms")
        while self.running:
            temps = self.get_hbm_temps()
            if not temps:
                time.sleep(self.cfg["poll_ms"] / 1000)
                continue

            max_temp = max(t for _, t in temps)
            for idx, t in temps:
                temp_gauge.labels(gpu=idx).set(t)

            if max_temp >= self.cfg["throttle_temp"] and not self.throttling:
                self.throttling = True
                throttle_gauge.set(1)
                new_batch = max(self.cfg["min_batch"], self.current_batch // 2)
                self.set_vllm_batch(new_batch, self.cfg["migrate_pct"])
                self.current_batch = new_batch
                logging.warning(f"THROTTLE {max_temp}C: batch->{new_batch}")

            elif max_temp <= self.cfg["recover_temp"] and self.throttling:
                self.throttling = False
                throttle_gauge.set(0)
                new_batch = min(self.cfg["max_batch"], self.current_batch * 2)
                self.set_vllm_batch(new_batch, 0)
                self.current_batch = new_batch
                logging.info(f"RECOVER {max_temp}C: batch->{new_batch}")

            time.sleep(self.cfg["poll_ms"] / 1000)

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return {**DEFAULT_CONFIG, **yaml.safe_load(f)}
    return DEFAULT_CONFIG

if __name__ == "__main__":
    ThermalController(load_config()).run()
