import json
import os
import matplotlib.pyplot as plt
import numpy as np

# ── Boje po modu ──────────────────────────────────────────────
COLORS = {
    "Baseline":            "#2196F3",
    "Ambient":             "#4CAF50",
    "Sidecar Permissive":  "#FF9800",
    "Sidecar Strict":      "#F44336",
    "Sidecar DISABLE":     "#FF9800",
    "Sidecar STRICT":      "#F44336",
}

K8S_STANDARD  = "k8s/results/01_standard"
K8S_STRESS    = "k8s/results/02_stress"
K8S_RESOURCES = "k8s/results/04_resources"
LOCAL         = "k8s/results/local"
LOCAL_TESTING  = "k8s/results/local-testing"
REMOTE_TESTING = "k8s/results/remote-testing"

def load(filename, folder=K8S_STANDARD):
    path = os.path.join(folder, filename)
    with open(path) as f:
        return json.load(f)

def pct(data, p):
    for entry in data["DurationHistogram"]["Percentiles"]:
        if entry["Percentile"] == p:
            return entry["Value"] * 1000  # s → ms
    return None

def load_runs(scenario, test_type, filename_pattern, n_runs):
    """Učitaj n runova i vrati mean Avg, P90, P99."""
    folder = os.path.join(LOCAL, scenario, test_type)
    avgs, p90s, p99s = [], [], []
    for i in range(1, n_runs + 1):
        path = os.path.join(folder, filename_pattern.format(i=i))
        with open(path) as f:
            d = json.load(f)
        avgs.append(d["DurationHistogram"]["Avg"] * 1000)
        p90s.append(pct(d, 90))
        p99s.append(pct(d, 99))
    return sum(avgs)/n_runs, sum(p90s)/n_runs, sum(p99s)/n_runs

def load_stress_runs(scenario, threads, n_runs):
    """Učitaj stress runove i vrati mean QPS i Avg."""
    folder = os.path.join(LOCAL, scenario, "02_stress")
    qps_list, avg_list, p99_list = [], [], []
    for i in range(1, n_runs + 1):
        path = os.path.join(folder, f"stress-{threads}t-run{i}.json")
        with open(path) as f:
            d = json.load(f)
        qps_list.append(d["ActualQPS"])
        avg_list.append(d["DurationHistogram"]["Avg"] * 1000)
        p99_list.append(pct(d, 99))
    return sum(qps_list)/n_runs, sum(avg_list)/n_runs, sum(p99_list)/n_runs

# ── LOCAL 1. Bar chart – standard latency po payload-u ───────
def local_chart_standard():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    payloads = ["1kb", "10kb", "100kb"]
    metrics = ["Avg", "P90", "P99"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=False)

    for ax, payload in zip(axes, payloads):
        data = {}
        for label, sc in scenarios.items():
            avg, p90, p99 = load_runs(sc, "01_standard",
                                      f"standard-{payload}-run{{i}}.json", 5)
            data[label] = [avg, p90, p99]

        x = np.arange(len(metrics))
        w = 0.2
        n = len(data)
        offsets = np.linspace(-(n-1)/2 * w, (n-1)/2 * w, n)

        for i, (label, vals) in enumerate(data.items()):
            bars = ax.bar(x + offsets[i], vals, w,
                          label=label, color=COLORS[label], alpha=0.85)
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.2,
                        f"{bar.get_height():.1f}",
                        ha="center", va="bottom", fontsize=7)

        ax.set_title(f"{payload.upper()} payload", fontsize=11)
        ax.set_ylabel("Latency (ms)")
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("Latency – Standard Load (50 QPS, 60s) – Case Study A (kind)",
                 fontsize=13)
    plt.tight_layout()
    out = os.path.join(LOCAL, "chart_local_standard.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

# ── LOCAL 2. Line chart – stress QPS i latency ───────────────
def local_chart_stress():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    threads = [10, 50, 100]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    for label, sc in scenarios.items():
        qps_vals, avg_vals = [], []
        for t in threads:
            qps, avg, _ = load_stress_runs(sc, t, 3)
            qps_vals.append(qps)
            avg_vals.append(avg)
        color = COLORS[label]
        ax1.plot(threads, qps_vals, marker="o", label=label, color=color, linewidth=2)
        ax2.plot(threads, avg_vals, marker="o", label=label, color=color, linewidth=2)

    ax1.set_title("Throughput (QPS) vs Concurrency", fontsize=12)
    ax1.set_xlabel("Concurrent threads")
    ax1.set_ylabel("QPS")
    ax1.legend()
    ax1.grid(linestyle="--", alpha=0.4)

    ax2.set_title("Avg Latency vs Concurrency", fontsize=12)
    ax2.set_xlabel("Concurrent threads")
    ax2.set_ylabel("Latency (ms)")
    ax2.legend()
    ax2.grid(linestyle="--", alpha=0.4)

    fig.suptitle("Stress Test – Max QPS, 60s, 1 KB payload – Case Study A (kind)",
                 fontsize=13)
    plt.tight_layout()
    out = os.path.join(LOCAL, "chart_local_stress.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

# ── 1. Bar chart – avg latency, standard load (1 KB) ─────────
def chart_standard():
    files = {
        "Baseline":            "baseline.json",
        "Ambient":             "ambient.json",
        "Sidecar Permissive":  "sidecar-permissive.json",
        "Sidecar Strict":      "sidecar-strict.json",
    }
    data = {}
    for label, fname in files.items():
        d = load(fname)
        data[label] = {
            "Avg": d["DurationHistogram"]["Avg"] * 1000,
            "P90": pct(d, 90),
            "P99": pct(d, 99),
        }

    metrics = ["Avg", "P90", "P99"]
    x = np.arange(len(metrics))
    w = 0.2
    n = len(data)
    offsets = np.linspace(-(n-1)/2 * w, (n-1)/2 * w, n)

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (label, vals) in enumerate(data.items()):
        bars = ax.bar(x + offsets[i], [vals[m] for m in metrics], w,
                      label=label, color=COLORS[label], alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7.5)

    ax.set_title("Latency – Standard Load (50 QPS, 1 KB payload, 30s)", fontsize=13)
    ax.set_ylabel("Latency (ms)")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()
    ax.set_ylim(0, 38)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(f"{K8S_STANDARD}/chart_standard_load.png", dpi=150)
    print("Saved: chart_standard_load.png")
    plt.close()

# ── 2. Bar chart – avg latency, large payload (100 KB) ───────
def chart_large():
    files = {
        "Baseline":            "baseline-large.json",
        "Ambient":             "ambient-large.json",
        "Sidecar Permissive":  "sidecar-permissive-large.json",
        "Sidecar Strict":      "sidecar-strict-large.json",
    }
    data = {}
    for label, fname in files.items():
        d = load(fname)
        data[label] = {
            "Avg": d["DurationHistogram"]["Avg"] * 1000,
            "P90": pct(d, 90),
            "P99": pct(d, 99),
        }

    metrics = ["Avg", "P90", "P99"]
    x = np.arange(len(metrics))
    w = 0.2
    n = len(data)
    offsets = np.linspace(-(n-1)/2 * w, (n-1)/2 * w, n)

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (label, vals) in enumerate(data.items()):
        bars = ax.bar(x + offsets[i], [vals[m] for m in metrics], w,
                      label=label, color=COLORS[label], alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7.5)

    ax.set_title("Latency – Large Payload (50 QPS, 100 KB, 30s)", fontsize=13)
    ax.set_ylabel("Latency (ms)")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()
    ax.set_ylim(0, 55)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(f"{K8S_STANDARD}/chart_large_payload.png", dpi=150)
    print("Saved: chart_large_payload.png")
    plt.close()

# ── 3. Line chart – stress test QPS vs latency ───────────────
def chart_stress():
    stress = {
        "Baseline": {
            10:  {"qps": 2195.54, "avg": 4.54},
            50:  {"qps": 3278.20, "avg": 15.24},
            100: {"qps": 3389.98, "avg": 29.44},
        },
        "Ambient": {
            10:  {"qps": 1919.16, "avg": 5.20},
            50:  {"qps": 3040.11, "avg": 16.44},
            100: {"qps": 1661.75, "avg": 60.10},
        },
        "Sidecar": {
            10:  {"qps": 1251.69, "avg": 7.98},
            50:  {"qps": 2451.33, "avg": 20.38},
            100: {"qps": 2922.77, "avg": 34.17},
        },
    }
    threads = [10, 50, 100]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    for label, data in stress.items():
        color = list(COLORS.values())[list(stress.keys()).index(label)]
        qps_vals = [data[t]["qps"] for t in threads]
        avg_vals = [data[t]["avg"] for t in threads]
        ax1.plot(threads, qps_vals, marker="o", label=label, color=color, linewidth=2)
        ax2.plot(threads, avg_vals, marker="o", label=label, color=color, linewidth=2)

    ax1.set_title("Throughput (QPS) vs Concurrency", fontsize=12)
    ax1.set_xlabel("Concurrent threads")
    ax1.set_ylabel("QPS")
    ax1.legend()
    ax1.grid(linestyle="--", alpha=0.4)

    ax2.set_title("Avg Latency vs Concurrency", fontsize=12)
    ax2.set_xlabel("Concurrent threads")
    ax2.set_ylabel("Latency (ms)")
    ax2.legend()
    ax2.grid(linestyle="--", alpha=0.4)

    fig.suptitle("Stress Test – Max QPS, 10s, 1 KB payload", fontsize=13)
    plt.tight_layout()
    plt.savefig(f"{K8S_STRESS}/chart_stress_test.png", dpi=150)
    print("Saved: chart_stress_test.png")
    plt.close()

# ── 4. Grouped bar – CPU i Memory overhead ───────────────────
def chart_resources():
    services = ["service-a", "service-b", "service-c"]
    cpu = {
        "Baseline": [1007, 926, 304],
        "Ambient":  [773,  977, 284],
        "Sidecar":  [1401, 1175, 393],
    }
    mem = {
        "Baseline": [74,  68,  54],
        "Ambient":  [91,  78,  55],
        "Sidecar":  [126, 148, 112],
    }

    x = np.arange(len(services))
    w = 0.25
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    for i, (label, vals) in enumerate(cpu.items()):
        color = list(COLORS.values())[i]
        ax1.bar(x + (i - 1) * w, vals, w, label=label, color=color, alpha=0.85)
    ax1.set_title("CPU Usage (millicores)", fontsize=12)
    ax1.set_ylabel("millicores")
    ax1.set_xticks(x)
    ax1.set_xticklabels(services)
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    for i, (label, vals) in enumerate(mem.items()):
        color = list(COLORS.values())[i]
        ax2.bar(x + (i - 1) * w, vals, w, label=label, color=color, alpha=0.85)
    ax2.set_title("Memory Usage (MiB)", fontsize=12)
    ax2.set_ylabel("MiB")
    ax2.set_xticks(x)
    ax2.set_xticklabels(services)
    ax2.legend()
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("Resource Usage During Stress Test (100 threads)", fontsize=13)
    plt.tight_layout()
    plt.savefig(f"{K8S_RESOURCES}/chart_resources.png", dpi=150)
    print("Saved: chart_resources.png")
    plt.close()

def lt_load_runs(scenario, payload, n_runs=5):
    """Učitaj standard runove iz local-testing i vrati mean Avg, P90, P99."""
    folder = os.path.join(LOCAL_TESTING, scenario, "01_standard", payload)
    avgs, p90s, p99s = [], [], []
    for i in range(1, n_runs + 1):
        with open(os.path.join(folder, f"run{i}.json")) as f:
            d = json.load(f)
        avgs.append(d["DurationHistogram"]["Avg"] * 1000)
        p90s.append(pct(d, 90))
        p99s.append(pct(d, 99))
    return sum(avgs)/n_runs, sum(p90s)/n_runs, sum(p99s)/n_runs

def lt_load_stress_runs(scenario, threads, payload, n_runs=3):
    """Učitaj stress runove iz local-testing i vrati mean QPS, Avg, P99."""
    folder = os.path.join(LOCAL_TESTING, scenario, "02_stress", payload)
    qps_list, avg_list, p99_list = [], [], []
    for i in range(1, n_runs + 1):
        with open(os.path.join(folder, f"stress-{threads}t-run{i}.json")) as f:
            d = json.load(f)
        qps_list.append(d["ActualQPS"])
        avg_list.append(d["DurationHistogram"]["Avg"] * 1000)
        p99_list.append(pct(d, 99))
    return sum(qps_list)/n_runs, sum(avg_list)/n_runs, sum(p99_list)/n_runs

def lt_load_resources_csv(scenario, test_type, payload, run_id):
    """Učitaj resources CSV za jedan run, vrati peak CPU (sum sva 3 servisa) i peak RAM."""
    if test_type == "standard":
        path = os.path.join(LOCAL_TESTING, scenario, "03_resources_standard",
                            payload, f"run{run_id}_resources.csv")
    else:
        threads, run = run_id
        path = os.path.join(LOCAL_TESTING, scenario, "04_resources_stress",
                            payload, f"stress-{threads}t-run{run}_resources.csv")
    cpu_by_svc = {"service-a": [], "service-b": [], "service-c": []}
    ram_by_svc = {"service-a": [], "service-b": [], "service-c": []}
    with open(path) as f:
        for line in f:
            parts = [p for p in line.strip().split(",") if p]
            if len(parts) >= 4 and parts[0].isdigit():
                pod, cpu_s, ram_s = parts[1], parts[2], parts[3]
            elif len(parts) >= 3:
                pod, cpu_s, ram_s = parts[0], parts[1], parts[2]
            else:
                continue
            cpu_val = int(cpu_s.replace("m", ""))
            ram_val = int(ram_s.replace("Mi", ""))
            for svc in cpu_by_svc:
                if svc in pod:
                    cpu_by_svc[svc].append(cpu_val)
                    ram_by_svc[svc].append(ram_val)
    peak_cpu = sum(max(v) if v else 0 for v in cpu_by_svc.values())
    peak_ram = sum(max(v) if v else 0 for v in ram_by_svc.values())
    return peak_cpu, peak_ram

# ── LOCAL-TESTING 1. Bar chart – standard latency po payload-u ──
def lt_chart_standard():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    payloads = ["1kb", "10kb", "100kb"]
    metrics = ["Avg", "P90", "P99"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=False)

    for ax, payload in zip(axes, payloads):
        data = {}
        for label, sc in scenarios.items():
            avg, p90, p99 = lt_load_runs(sc, payload)
            data[label] = [avg, p90, p99]

        x = np.arange(len(metrics))
        w = 0.2
        offsets = np.linspace(-(len(data)-1)/2 * w, (len(data)-1)/2 * w, len(data))

        for i, (label, vals) in enumerate(data.items()):
            bars = ax.bar(x + offsets[i], vals, w,
                          label=label, color=COLORS[label], alpha=0.85)
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.2,
                        f"{bar.get_height():.1f}",
                        ha="center", va="bottom", fontsize=7)

        ax.set_title(f"{payload.upper()} payload", fontsize=11)
        ax.set_ylabel("Latency (ms)")
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("Latency – Standard Load (50 QPS, 60s) – local-testing (kind)",
                 fontsize=13)
    plt.tight_layout()
    out = os.path.join(LOCAL_TESTING, "chart_lt_standard.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

# ── LOCAL-TESTING 2. Line chart – stress QPS i latency po payload-u ──
def lt_chart_stress():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    thread_levels = [10, 50, 100]
    payloads = ["1kb", "10kb", "100kb"]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    for col, payload in enumerate(payloads):
        ax_qps = axes[0][col]
        ax_lat = axes[1][col]

        for label, sc in scenarios.items():
            qps_vals, avg_vals = [], []
            for t in thread_levels:
                qps, avg, _ = lt_load_stress_runs(sc, t, payload)
                qps_vals.append(qps)
                avg_vals.append(avg)
            color = COLORS[label]
            ax_qps.plot(thread_levels, qps_vals, marker="o", label=label,
                        color=color, linewidth=2)
            ax_lat.plot(thread_levels, avg_vals, marker="o", label=label,
                        color=color, linewidth=2)

        ax_qps.set_title(f"QPS – {payload.upper()} payload", fontsize=11)
        ax_qps.set_ylabel("QPS")
        ax_qps.set_xticks(thread_levels)
        ax_qps.legend(fontsize=8)
        ax_qps.grid(linestyle="--", alpha=0.4)

        ax_lat.set_title(f"Avg Latency – {payload.upper()} payload", fontsize=11)
        ax_lat.set_xlabel("Concurrent threads")
        ax_lat.set_ylabel("Latency (ms)")
        ax_lat.set_xticks(thread_levels)
        ax_lat.legend(fontsize=8)
        ax_lat.grid(linestyle="--", alpha=0.4)

    fig.suptitle("Stress Test – Max QPS, 60s – local-testing (kind)", fontsize=13)
    plt.tight_layout()
    out = os.path.join(LOCAL_TESTING, "chart_lt_stress.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

# ── LOCAL-TESTING 3. Bar chart – peak CPU i RAM po scenariju ──
def lt_chart_resources():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    payloads = ["1kb", "10kb", "100kb"]

    # Prikupi peak CPU i RAM za standard testove (mean po 5 runova)
    std_cpu = {label: [] for label in scenarios}
    std_ram = {label: [] for label in scenarios}
    for label, sc in scenarios.items():
        for payload in payloads:
            cpus, rams = [], []
            for i in range(1, 6):
                try:
                    cpu, ram = lt_load_resources_csv(sc, "standard", payload, i)
                    cpus.append(cpu)
                    rams.append(ram)
                except Exception:
                    pass
            std_cpu[label].append(sum(cpus)/len(cpus) if cpus else 0)
            std_ram[label].append(sum(rams)/len(rams) if rams else 0)

    # Prikupi peak CPU i RAM za stress 100t 1kb (mean po 3 runa)
    stress_cpu = {label: 0 for label in scenarios}
    stress_ram = {label: 0 for label in scenarios}
    for label, sc in scenarios.items():
        cpus, rams = [], []
        for i in range(1, 4):
            try:
                cpu, ram = lt_load_resources_csv(sc, "stress", "1kb", (100, i))
                cpus.append(cpu)
                rams.append(ram)
            except Exception:
                pass
        stress_cpu[label] = sum(cpus)/len(cpus) if cpus else 0
        stress_ram[label] = sum(rams)/len(rams) if rams else 0

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    x = np.arange(len(payloads))
    w = 0.2
    offsets = np.linspace(-(len(scenarios)-1)/2 * w, (len(scenarios)-1)/2 * w, len(scenarios))

    # Standard CPU
    ax = axes[0][0]
    for i, (label, sc) in enumerate(scenarios.items()):
        bars = ax.bar(x + offsets[i], std_cpu[label], w,
                      label=label, color=COLORS[label], alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=7)
    ax.set_title("Standard – Peak CPU (sum 3 servisa)", fontsize=11)
    ax.set_ylabel("millicores")
    ax.set_xticks(x)
    ax.set_xticklabels(payloads)
    ax.legend(fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Standard RAM
    ax = axes[0][1]
    for i, (label, sc) in enumerate(scenarios.items()):
        bars = ax.bar(x + offsets[i], std_ram[label], w,
                      label=label, color=COLORS[label], alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=7)
    ax.set_title("Standard – Peak RAM (sum 3 servisa)", fontsize=11)
    ax.set_ylabel("MiB")
    ax.set_xticks(x)
    ax.set_xticklabels(payloads)
    ax.legend(fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Stress CPU (100t, 1kb)
    ax = axes[1][0]
    labels = list(scenarios.keys())
    vals = [stress_cpu[l] for l in labels]
    colors = [COLORS[l] for l in labels]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Stress (100t, 1KB) – Peak CPU", fontsize=11)
    ax.set_ylabel("millicores")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Stress RAM (100t, 1kb)
    ax = axes[1][1]
    vals = [stress_ram[l] for l in labels]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Stress (100t, 1KB) – Peak RAM", fontsize=11)
    ax.set_ylabel("MiB")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("CPU & RAM – local-testing (kind)", fontsize=13)
    plt.tight_layout()
    out = os.path.join(LOCAL_TESTING, "chart_lt_resources.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

def rt_load_runs(scenario, payload, n_runs=5):
    """Učitaj standard runove iz remote-testing i vrati mean Avg, P90, P99."""
    folder = os.path.join(REMOTE_TESTING, scenario, "01_standard", payload)
    avgs, p90s, p99s = [], [], []
    for i in range(1, n_runs + 1):
        with open(os.path.join(folder, f"run{i}.json")) as f:
            d = json.load(f)
        avgs.append(d["DurationHistogram"]["Avg"] * 1000)
        p90s.append(pct(d, 90))
        p99s.append(pct(d, 99))
    return sum(avgs)/n_runs, sum(p90s)/n_runs, sum(p99s)/n_runs

def rt_load_stress_runs(scenario, threads, payload, n_runs=3):
    """Učitaj stress runove iz remote-testing i vrati mean QPS, Avg, P99."""
    folder = os.path.join(REMOTE_TESTING, scenario, "02_stress", payload)
    qps_list, avg_list, p99_list = [], [], []
    for i in range(1, n_runs + 1):
        with open(os.path.join(folder, f"stress-{threads}t-run{i}.json")) as f:
            d = json.load(f)
        qps_list.append(d["ActualQPS"])
        avg_list.append(d["DurationHistogram"]["Avg"] * 1000)
        p99_list.append(pct(d, 99))
    return sum(qps_list)/n_runs, sum(avg_list)/n_runs, sum(p99_list)/n_runs

def rt_load_resources_csv(scenario, test_type, payload, run_id):
    """Učitaj resources CSV za jedan run iz remote-testing."""
    if test_type == "standard":
        path = os.path.join(REMOTE_TESTING, scenario, "03_resources_standard",
                            payload, f"run{run_id}_resources.csv")
    else:
        threads, run = run_id
        path = os.path.join(REMOTE_TESTING, scenario, "04_resources_stress",
                            payload, f"stress-{threads}t-run{run}_resources.csv")
    cpu_by_svc = {"service-a": [], "service-b": [], "service-c": []}
    ram_by_svc = {"service-a": [], "service-b": [], "service-c": []}
    with open(path) as f:
        for line in f:
            parts = [p for p in line.strip().split(",") if p]
            if len(parts) >= 4 and parts[0].isdigit():
                pod, cpu_s, ram_s = parts[1], parts[2], parts[3]
            elif len(parts) >= 3:
                pod, cpu_s, ram_s = parts[0], parts[1], parts[2]
            else:
                continue
            cpu_val = int(cpu_s.replace("m", ""))
            ram_val = int(ram_s.replace("Mi", ""))
            for svc in cpu_by_svc:
                if svc in pod:
                    cpu_by_svc[svc].append(cpu_val)
                    ram_by_svc[svc].append(ram_val)
    peak_cpu = sum(max(v) if v else 0 for v in cpu_by_svc.values())
    peak_ram = sum(max(v) if v else 0 for v in ram_by_svc.values())
    return peak_cpu, peak_ram

def rt_chart_standard():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    payloads = ["1kb", "10kb", "100kb"]
    metrics = ["Avg", "P90", "P99"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=False)
    for ax, payload in zip(axes, payloads):
        data = {}
        for label, sc in scenarios.items():
            avg, p90, p99 = rt_load_runs(sc, payload)
            data[label] = [avg, p90, p99]
        x = np.arange(len(metrics))
        w = 0.2
        offsets = np.linspace(-(len(data)-1)/2 * w, (len(data)-1)/2 * w, len(data))
        for i, (label, vals) in enumerate(data.items()):
            bars = ax.bar(x + offsets[i], vals, w,
                          label=label, color=COLORS[label], alpha=0.85)
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.2,
                        f"{bar.get_height():.1f}",
                        ha="center", va="bottom", fontsize=7)
        ax.set_title(f"{payload.upper()} payload", fontsize=11)
        ax.set_ylabel("Latency (ms)")
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.suptitle("Latency – Standard Load (50 QPS, 60s) – remote-testing (GKE)", fontsize=13)
    plt.tight_layout()
    out = os.path.join(REMOTE_TESTING, "chart_rt_standard.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

def rt_chart_stress():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    thread_levels = [10, 50, 100]
    payloads = ["1kb", "10kb", "100kb"]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for col, payload in enumerate(payloads):
        ax_qps = axes[0][col]
        ax_lat = axes[1][col]
        for label, sc in scenarios.items():
            qps_vals, avg_vals = [], []
            for t in thread_levels:
                try:
                    qps, avg, _ = rt_load_stress_runs(sc, t, payload)
                except Exception:
                    qps, avg = 0, 0
                qps_vals.append(qps)
                avg_vals.append(avg)
            color = COLORS[label]
            ax_qps.plot(thread_levels, qps_vals, marker="o", label=label,
                        color=color, linewidth=2)
            ax_lat.plot(thread_levels, avg_vals, marker="o", label=label,
                        color=color, linewidth=2)
        ax_qps.set_title(f"QPS – {payload.upper()} payload", fontsize=11)
        ax_qps.set_ylabel("QPS")
        ax_qps.set_xticks(thread_levels)
        ax_qps.legend(fontsize=8)
        ax_qps.grid(linestyle="--", alpha=0.4)
        ax_lat.set_title(f"Avg Latency – {payload.upper()} payload", fontsize=11)
        ax_lat.set_xlabel("Concurrent threads")
        ax_lat.set_ylabel("Latency (ms)")
        ax_lat.set_xticks(thread_levels)
        ax_lat.legend(fontsize=8)
        ax_lat.grid(linestyle="--", alpha=0.4)
    fig.suptitle("Stress Test – Max QPS, 60s – remote-testing (GKE)", fontsize=13)
    plt.tight_layout()
    out = os.path.join(REMOTE_TESTING, "chart_rt_stress.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

def rt_chart_resources():
    scenarios = {
        "Baseline":        "baseline",
        "Sidecar DISABLE": "sidecar-disable",
        "Sidecar STRICT":  "sidecar-strict",
        "Ambient":         "ambient",
    }
    payloads = ["1kb", "10kb", "100kb"]

    std_cpu = {label: [] for label in scenarios}
    std_ram = {label: [] for label in scenarios}
    for label, sc in scenarios.items():
        for payload in payloads:
            cpus, rams = [], []
            for i in range(1, 6):
                try:
                    cpu, ram = rt_load_resources_csv(sc, "standard", payload, i)
                    cpus.append(cpu)
                    rams.append(ram)
                except Exception:
                    pass
            std_cpu[label].append(sum(cpus)/len(cpus) if cpus else 0)
            std_ram[label].append(sum(rams)/len(rams) if rams else 0)

    stress_cpu = {label: 0 for label in scenarios}
    stress_ram = {label: 0 for label in scenarios}
    for label, sc in scenarios.items():
        cpus, rams = [], []
        for i in range(1, 4):
            try:
                cpu, ram = rt_load_resources_csv(sc, "stress", "1kb", (100, i))
                cpus.append(cpu)
                rams.append(ram)
            except Exception:
                pass
        stress_cpu[label] = sum(cpus)/len(cpus) if cpus else 0
        stress_ram[label] = sum(rams)/len(rams) if rams else 0

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    x = np.arange(len(payloads))
    w = 0.2
    offsets = np.linspace(-(len(scenarios)-1)/2 * w, (len(scenarios)-1)/2 * w, len(scenarios))

    ax = axes[0][0]
    for i, (label, sc) in enumerate(scenarios.items()):
        bars = ax.bar(x + offsets[i], std_cpu[label], w,
                      label=label, color=COLORS[label], alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=7)
    ax.set_title("Standard – Peak CPU (sum 3 servisa)", fontsize=11)
    ax.set_ylabel("millicores")
    ax.set_xticks(x)
    ax.set_xticklabels(payloads)
    ax.legend(fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax = axes[0][1]
    for i, (label, sc) in enumerate(scenarios.items()):
        bars = ax.bar(x + offsets[i], std_ram[label], w,
                      label=label, color=COLORS[label], alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=7)
    ax.set_title("Standard – Peak RAM (sum 3 servisa)", fontsize=11)
    ax.set_ylabel("MiB")
    ax.set_xticks(x)
    ax.set_xticklabels(payloads)
    ax.legend(fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax = axes[1][0]
    labels = list(scenarios.keys())
    vals = [stress_cpu[l] for l in labels]
    colors = [COLORS[l] for l in labels]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Stress (100t, 1KB) – Peak CPU", fontsize=11)
    ax.set_ylabel("millicores")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax = axes[1][1]
    vals = [stress_ram[l] for l in labels]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Stress (100t, 1KB) – Peak RAM", fontsize=11)
    ax.set_ylabel("MiB")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("CPU & RAM – remote-testing (GKE)", fontsize=13)
    plt.tight_layout()
    out = os.path.join(REMOTE_TESTING, "chart_rt_resources.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()


if __name__ == "__main__":
    chart_large()
    chart_stress()
    chart_resources()
    print("\n── Lokalni grafici (stari local/) ──")
    local_chart_standard()
    local_chart_stress()
    print("\n── Local-testing grafici ──")
    lt_chart_standard()
    lt_chart_stress()
    lt_chart_resources()
    print("\n── Remote-testing grafici (GKE) ──")
    _rt_probe = os.path.join(REMOTE_TESTING, "baseline", "01_standard", "1kb", "run1.json")
    if os.path.exists(_rt_probe):
        rt_chart_standard()
        rt_chart_stress()
        rt_chart_resources()
    else:
        print("  (preskočeno – remote-testing nema podataka)")
    print("\nDone! Generated all charts.")
