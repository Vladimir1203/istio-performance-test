# Istio Performance Benchmark

Empirijska studija koja meri uticaj Istio Service Mesh-a na latenciju, propusnost i potrošnju resursa u Kubernetes okruženju. Poređenje četiri scenarija: čist K8s, Sidecar bez mTLS-a, Sidecar sa mTLS-om i Ambient mod.

---

## Arhitektura

```
[Fortio] → [Service-A] → [Service-B] → [Service-C]
```

Tri Node.js/Express mikroservisa u lancu. Service-C generiše payload zadatog KB, odgovor putuje nazad kroz lanac. Lančana arhitektura multiplicira overhead mesh-a i čini razlike između scenarija merljivim.

---

## Test scenariji

| # | Scenario | Opis |
|---|----------|------|
| 1 | Baseline | Čist Kubernetes, bez Istio-a |
| 2 | Sidecar + mTLS DISABLE | Envoy proxy aktivan, mTLS eksplicitno isključen |
| 3 | Sidecar + mTLS STRICT | Envoy proxy + obavezni mTLS |
| 4 | Ambient | Istio ztunnel (sidecarless), L4 mTLS |

Napomena: Istio podržava tri mTLS moda unutar service mesh-a: DISABLE, PERMISSIVE i STRICT.
U ovom istraživanju korišćeni su isključivo DISABLE i STRICT modovi kako bi se obezbedili deterministični i jasno uporedivi rezultati.
PERMISSIVE mod, koji omogućava istovremeno plaintext i mTLS komunikaciju, izostavljen je jer uvodi nedeterminističko ponašanje i otežava precizno merenje performansi.

### Test matrica

| Test | Payload | QPS | Trajanje | Threads | Ponavljanja |
|------|---------|-----|----------|---------|-------------|
| Standard | 1 KB | 50 | 60s | 4 | 5 |
| Standard | 10 KB | 50 | 60s | 4 | 5 |
| Standard | 100 KB | 50 | 60s | 4 | 5 |
| Stress | 1 KB | max | 60s | 10 / 50 / 100 | 3 |
| Stress | 10 KB | max | 60s | 10 / 50 / 100 | 3 |
| Stress | 100 KB | max | 60s | 10 / 50 / 100 | 3 |

---

## Metodologija testiranja

Za svaki od 4 scenarija pokreću se isti tipovi testova, samo se menja Istio konfiguracija.

### Tipovi testova

**Standard test** – kontrolisano opterećenje od tačno 50 zahteva u sekundi, trajanje 60s = 3000 zahteva po runu. Cilj je merenje latencije u normalnim, predvidivim uslovima. Pokreće se za 3 veličine payload-a (1KB, 10KB, 100KB) da bi se videlo kako veličina odgovora utiče na overhead mesh-a. Koriste se 4 paralelna threada (`-c 4`) da Fortio nikad ne postane bottleneck – pri P99 spike-ovima do ~25ms jedan thread ne bi mogao da održi 50 QPS, dok 4 threada obezbeđuju dovoljnu marginu (matematički minimum je 2, uzeto 4 radi sigurnosti).

**Stress test** – bez ograničenja QPS-a, Fortio šalje zahteve što brže može. Cilj je nalaženje granice sistema – maksimalnog propusnog opsega i ponašanja latencije pod punim opterećenjem. Pokreće se sa 3 nivoa konkurentnosti (10, 50, 100 paralelnih konekcija) i 3 payload-a.

### Ključni pojmovi

| Pojam | Objašnjenje |
|-------|-------------|
| QPS | Queries Per Second – broj zahteva obrađenih u sekundi |
| Avg latency | Prosečno vreme od slanja zahteva do prijema odgovora |
| P90/P99 | 90% / 99% zahteva završilo za ovo vreme ili brže – meri tail latency |
| Threads | Broj paralelnih konekcija koje Fortio drži otvorenim |
| Warmup | Kratki test pre merenja čiji se rezultati bacaju – zagreva JIT kompajler i DNS cache |

### Procedura za svaki scenario

1. Deploy servisa u odgovarajući namespace
2. Port-forward service-a na `localhost:8080`
3. Paralelno pokrenuti CPU/RAM merenje (`kubectl top pods` svake 5s → CSV)
4. Warmup (20s, rezultati se bacaju)
5. 5 runova standard testa po payload-u (1KB, 10KB, 100KB), 15s pauza između runova
6. 3 runa stress testa po thread nivou (10, 50, 100) × po payload-u (1KB, 10KB, 100KB), 15s pauza
7. Čišćenje namespace-a i Istio instalacije

---

## Rezultati

### Case Study A – Lokalno (kind)

> Vrednosti su mean (5 ponavljanja za standard, 3 za stress). Warmup 20s pre svakog testa.
> Izvor: `k8s/results/local-testing/`

#### Standard test (50 QPS, 60s)

**1 KB payload:**

| Scenario | Avg ms | P90 ms | P99 ms | CPU (m) | RAM (Mi) |
|----------|--------|--------|--------|---------|----------|
| Baseline | 12.66 | 17.44 | 25.08 | 154 | 146 |
| Sidecar + DISABLE | 12.71 | 16.94 | 21.11 | 205 | 271 |
| Sidecar + STRICT | 12.83 | 16.93 | 19.59 | 195 | 327 |
| Ambient | 12.48 | 16.48 | 19.34 | 153 | 142 |

**10 KB payload:**

| Scenario | Avg ms | P90 ms | P99 ms | CPU (m) | RAM (Mi) |
|----------|--------|--------|--------|---------|----------|
| Baseline | 13.05 | 17.67 | 25.01 | 155 | 145 |
| Sidecar + DISABLE | 12.64 | 16.89 | 19.61 | 199 | 280 |
| Sidecar + STRICT | 12.84 | 16.91 | 19.75 | 191 | 330 |
| Ambient | 12.84 | 16.95 | 19.66 | 143 | 147 |

**100 KB payload:**

| Scenario | Avg ms | P90 ms | P99 ms | CPU (m) | RAM (Mi) |
|----------|--------|--------|--------|---------|----------|
| Baseline | 14.72 | 19.13 | 25.36 | 290 | 160 |
| Sidecar + DISABLE | 13.61 | 16.95 | 20.71 | 304 | 287 |
| Sidecar + STRICT | 14.13 | 17.66 | 23.20 | 317 | 341 |
| Ambient | 14.28 | 17.63 | 22.62 | 263 | 164 |

#### Stress test (max QPS, 60s, 1KB payload)

| Threads | Scenario | QPS | Avg ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|-----|--------|--------|---------|----------|
| 10 | Baseline | 1532 | 6.53 | 15.50 | 1574 | 178 |
| 10 | Sidecar + DISABLE | 1818 | 5.50 | 8.93 | 2230 | 311 |
| 10 | Sidecar + STRICT | 1728 | 5.79 | 9.42 | 2013 | 358 |
| 10 | Ambient | 1372 | 7.30 | 16.17 | 1456 | 178 |
| 50 | Baseline | 1431 | 34.97 | 67.48 | 1547 | 193 |
| 50 | Sidecar + DISABLE | 2424 | 20.62 | 32.63 | 2855 | 335 |
| 50 | Sidecar + STRICT | 2315 | 21.59 | 34.36 | 2911 | 372 |
| 50 | Ambient | 1375 | 36.45 | 72.20 | 1533 | 192 |
| 100 | Baseline | 1631 | 61.58 | 118.87 | 1614 | 215 |
| 100 | Sidecar + DISABLE | 2561 | 39.05 | 59.63 | 2930 | 392 |
| 100 | Sidecar + STRICT | 2483 | 40.27 | 63.22 | 3078 | 408 |
| 100 | Ambient | 1602 | 62.58 | 126.97 | 1648 | 216 |

#### Stress test (max QPS, 60s, 10KB payload)

| Threads | Scenario | QPS | Avg ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|-----|--------|--------|---------|----------|
| 10 | Baseline | 1523 | 6.57 | 13.71 | 1749 | 182 |
| 10 | Sidecar + DISABLE | 1564 | 6.39 | 10.60 | 2317 | 341 |
| 10 | Sidecar + STRICT | 1477 | 6.77 | 10.98 | 2255 | 372 |
| 10 | Ambient | 1513 | 6.61 | 13.89 | 1657 | 185 |
| 50 | Baseline | 1450 | 34.51 | 60.72 | 1685 | 195 |
| 50 | Sidecar + DISABLE | 2038 | 24.53 | 38.22 | 2990 | 355 |
| 50 | Sidecar + STRICT | 1955 | 25.57 | 39.72 | 3086 | 400 |
| 50 | Ambient | 1383 | 36.16 | 72.42 | 1679 | 194 |
| 100 | Baseline | 1656 | 60.60 | 108.42 | 1670 | 218 |
| 100 | Sidecar + DISABLE | 2141 | 46.70 | 69.33 | 2803 | 393 |
| 100 | Sidecar + STRICT | 2058 | 48.58 | 74.21 | 2975 | 418 |
| 100 | Ambient | 1440 | 69.56 | 188.46 | 1699 | 217 |

#### Stress test (max QPS, 60s, 100KB payload)

| Threads | Scenario | QPS | Avg ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|-----|--------|--------|---------|----------|
| 10 | Baseline | 689 | 14.51 | 23.18 | 2051 | 204 |
| 10 | Sidecar + DISABLE | 652 | 15.35 | 24.65 | 2303 | 372 |
| 10 | Sidecar + STRICT | 591 | 16.93 | 26.56 | 2669 | 380 |
| 10 | Ambient | 559 | 17.87 | 28.01 | 2078 | 187 |
| 50 | Baseline | 722 | 69.22 | 97.74 | 2148 | 233 |
| 50 | Sidecar + DISABLE | 783 | 63.81 | 93.69 | 2747 | 423 |
| 50 | Sidecar + STRICT | 761 | 65.65 | 97.24 | 2790 | 433 |
| 50 | Ambient | 654 | 76.36 | 115.23 | 1856 | 230 |
| 100 | Baseline | 825 | 121.16 | 158.09 | 2158 | 278 |
| 100 | Sidecar + DISABLE | 804 | 124.24 | 173.29 | 2849 | 448 |
| 100 | Sidecar + STRICT | 785 | 127.31 | 177.49 | 2793 | 460 |
| 100 | Ambient | 646 | 154.75 | 244.09 | 1914 | 263 |

#### Grafici

- `k8s/results/local-testing/chart_lt_standard.png`
- `k8s/results/local-testing/chart_lt_stress.png`
- `k8s/results/local-testing/chart_lt_resources.png`

---

### Case Study B – Remote (GKE)

> Vrednosti su mean (5 ponavljanja za standard, 3 za stress). Warmup 20s pre svakog testa.
> Klaster: `istio-research-cluster`, `europe-west3-a`, `e2-standard-2` (2 vCPU, 8 GB RAM).
> Izvor: `k8s/results/remote-testing/`

#### Standard test (50 QPS, 60s)

| Payload | Scenario | Avg ms | P90 ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|--------|--------|--------|---------|----------|
| 1KB | Baseline | 68.21 | 77.28 | 107.03 | 272 | 137 |
| 1KB | Sidecar + DISABLE | 80.39 | 91.58 | 125.22 | 421 | 241 |
| 1KB | Sidecar + STRICT | 78.07 | 88.18 | 123.86 | 394 | 278 |
| 1KB | Ambient | 83.89 | 100.11 | 167.97 | 316 | 148 |
| 10KB | Baseline | 69.99 | 78.65 | 105.23 | 266 | 145 |
| 10KB | Sidecar + DISABLE | 84.69 | 99.69 | 150.01 | 409 | 250 |
| 10KB | Sidecar + STRICT | 81.96 | 91.67 | 127.50 | 419 | 282 |
| 10KB | Ambient | 88.54 | 103.49 | 163.92 | 321 | 159 |
| 100KB | Baseline | 94.48 | 118.66 | 170.67 | 566 | 154 |
| 100KB | Sidecar + DISABLE | 105.37 | 136.25 | 224.71 | 826 | 268 |
| 100KB | Sidecar + STRICT | 97.16 | 120.19 | 186.89 | 687 | 294 |
| 100KB | Ambient | 107.67 | 135.15 | 220.00 | 660 | 180 |

> **Napomena 100KB:** Fortio nije mogao da dostigne 50 QPS (100KB odgovor traje ~100ms, interval za 50 QPS = 20ms). Stvarni QPS bio je ~38–50 (zavisno od scenarija). Ovo je I/O-bound ponašanje, ne greška.

#### Stress test (max QPS, 60s, 1KB)

| Threads | Scenario | QPS | Avg ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|-----|--------|--------|---------|----------|
| 10 | Baseline | 141 | 70.97 | 128.37 | 516 | 159 |
| 10 | Sidecar + DISABLE | 125 | 80.16 | 154.49 | 873 | 253 |
| 10 | Sidecar + STRICT | 130 | 77.05 | 165.48 | 820 | 260 |
| 10 | Ambient | 116 | 86.44 | 170.68 | 650 | 157 |
| 50 | Baseline | 296 | 168.61 | 302.05 | 1071 | 183 |
| 50 | Sidecar + DISABLE | 188 | 265.11 | 455.54 | 1110 | 286 |
| 50 | Sidecar + STRICT | 211 | 236.88 | 414.99 | 1129 | 298 |
| 50 | Ambient | 155 | 322.38 | 558.27 | 712 | 170 |
| 100 | Baseline | 310 | 322.68 | 518.55 | 1188 | 202 |
| 100 | Sidecar + DISABLE | 195 | 510.85 | 797.05 | 1153 | 305 |
| 100 | Sidecar + STRICT | 219 | 455.99 | 710.45 | 1238 | 336 |
| 100 | Ambient | 138 | 765.89 | 2410.23 | 691 | 179 |

#### Stress test (max QPS, 60s, 10KB)

| Threads | Scenario | QPS | Avg ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|-----|--------|--------|---------|----------|
| 10 | Baseline | 139 | 71.89 | 149.62 | 773 | 186 |
| 10 | Sidecar + DISABLE | 106 | 94.10 | 203.80 | 870 | 288 |
| 10 | Sidecar + STRICT | 123 | 80.94 | 174.99 | 793 | 294 |
| 10 | Ambient | 102 | 98.26 | 196.79 | 613 | 163 |
| 50 | Baseline | 270 | 184.88 | 349.92 | 1141 | 200 |
| 50 | Sidecar + DISABLE | 173 | 289.35 | 496.21 | 1130 | 307 |
| 50 | Sidecar + STRICT | 192 | 260.71 | 452.64 | 1180 | 331 |
| 50 | Ambient | 139 | 359.87 | 586.77 | 729 | 179 |
| 100 | Baseline | 277 | 359.72 | 581.74 | 1288 | 222 |
| 100 | Sidecar + DISABLE | 179 | 558.79 | 896.43 | 1210 | 325 |
| 100 | Sidecar + STRICT | 197 | 507.57 | 805.12 | 1239 | 342 |
| 100 | Ambient | 145 | 689.35 | 1037.16 | 755 | 209 |

#### Stress test (max QPS, 60s, 100KB)

| Threads | Scenario | QPS | Avg ms | P99 ms | CPU (m) | RAM (Mi) |
|---------|----------|-----|--------|--------|---------|----------|
| 10 | Baseline | 77 | 129.22 | 252.05 | 897 | 195 |
| 10 | Sidecar + DISABLE | 47 | 216.48 | 468.91 | 774 | 286 |
| 10 | Sidecar + STRICT | 83 | 120.99 | 270.41 | 1101 | 328 |
| 10 | Ambient | 38 | 269.58 | 689.92 | 468 | 162 |
| 50 | Baseline | 83 | 602.61 | 969.41 | 814 | 207 |
| 50 | Sidecar + DISABLE | 61 | 822.88 | 1759.15 | 900 | 331 |
| 50 | Sidecar + STRICT | 96 | 519.18 | 935.88 | 1225 | 382 |
| 50 | Ambient | 50 | 999.54 | 2276.51 | 534 | 202 |
| 100 | Baseline | 87 | 1141.42 | 2104.18 | 904 | 215 |
| 100 | Sidecar + DISABLE | 68 | 1462.48 | 1998.32 | 916 | 327 |
| 100 | Sidecar + STRICT | 95 | 1049.13 | 1878.66 | 1232 | 382 |
| 100 | Ambient | 63 | 1577.95 | 2409.02 | 608 | 205 |

#### Grafici

- `k8s/results/remote-testing/chart_rt_standard.png`
- `k8s/results/remote-testing/chart_rt_stress.png`
- `k8s/results/remote-testing/chart_rt_resources.png`

---

### Poređenje lokalno vs. remote

> **Napomena:** lokalni (kind) i GKE rezultati mere fundamentalno različite stvari.
> - **Lokalno:** loopback komunikacija unutar jednog Docker kontejnera – nema realnog RTT. Meri čisti overhead proxy-ja.
> - **GKE:** fizički odvojeni čvorovi u Frankfurtu, realni RTT ~0.38ms između pod-ova. Meri proxy overhead + realna mreža.

#### Standard – Avg latencija (ms)

**1 KB:**

| Scenario | Lokalno (kind) | GKE | Razlika |
|----------|---------------|-----|---------|
| Baseline | 12.66 | 68.21 | +55.55 |
| Sidecar DISABLE | 12.71 | 80.39 | +67.68 |
| Sidecar STRICT | 12.83 | 78.07 | +65.24 |
| Ambient | 12.48 | 83.89 | +71.41 |

**10 KB:**

| Scenario | Lokalno (kind) | GKE | Razlika |
|----------|---------------|-----|---------|
| Baseline | 13.05 | 69.99 | +56.94 |
| Sidecar DISABLE | 12.64 | 84.69 | +72.05 |
| Sidecar STRICT | 12.84 | 81.96 | +69.12 |
| Ambient | 12.84 | 88.54 | +75.70 |

**100 KB:**

| Scenario | Lokalno (kind) | GKE | Razlika |
|----------|---------------|-----|---------|
| Baseline | 14.72 | 94.48 | +79.76 |
| Sidecar DISABLE | 13.61 | 105.37 | +91.76 |
| Sidecar STRICT | 14.13 | 97.16 | +83.03 |
| Ambient | 14.28 | 107.67 | +93.39 |

> Sa rastom payload-a razlika između lokalno i GKE raste — mrežni overhead prenosa većih podataka dolazi do izražaja na GKE-u.

---

#### Stress – QPS (1 KB)

| Threads | Scenario | Lokalno (kind) | GKE | Faktor |
|---------|----------|---------------|-----|--------|
| 10 | Baseline | 1532 | 141 | 10.9× |
| 10 | Sidecar DISABLE | 1818 | 125 | 14.5× |
| 10 | Sidecar STRICT | 1728 | 130 | 13.3× |
| 10 | Ambient | 1372 | 116 | 11.8× |
| 50 | Baseline | 1431 | 296 | 4.8× |
| 50 | Sidecar DISABLE | 2424 | 188 | 12.9× |
| 50 | Sidecar STRICT | 2315 | 211 | 11.0× |
| 50 | Ambient | 1375 | 155 | 8.9× |
| 100 | Baseline | 1631 | 310 | 5.3× |
| 100 | Sidecar DISABLE | 2561 | 195 | 13.1× |
| 100 | Sidecar STRICT | 2483 | 219 | 11.3× |
| 100 | Ambient | 1602 | 138 | 11.6× |

#### Stress – QPS (10 KB)

| Threads | Scenario | Lokalno (kind) | GKE | Faktor |
|---------|----------|---------------|-----|--------|
| 10 | Baseline | 1523 | 139 | 11.0× |
| 10 | Sidecar DISABLE | 1564 | 106 | 14.8× |
| 10 | Sidecar STRICT | 1477 | 123 | 12.0× |
| 10 | Ambient | 1513 | 102 | 14.8× |
| 50 | Baseline | 1450 | 270 | 5.4× |
| 50 | Sidecar DISABLE | 2038 | 173 | 11.8× |
| 50 | Sidecar STRICT | 1955 | 192 | 10.2× |
| 50 | Ambient | 1383 | 139 | 9.9× |
| 100 | Baseline | 1656 | 277 | 6.0× |
| 100 | Sidecar DISABLE | 2141 | 179 | 12.0× |
| 100 | Sidecar STRICT | 2058 | 197 | 10.4× |
| 100 | Ambient | 1440 | 145 | 9.9× |

#### Stress – QPS (100 KB)

| Threads | Scenario | Lokalno (kind) | GKE | Faktor |
|---------|----------|---------------|-----|--------|
| 10 | Baseline | 689 | 77 | 8.9× |
| 10 | Sidecar DISABLE | 652 | 47 | 13.9× |
| 10 | Sidecar STRICT | 591 | 83 | 7.1× |
| 10 | Ambient | 559 | 38 | 14.7× |
| 50 | Baseline | 722 | 83 | 8.7× |
| 50 | Sidecar DISABLE | 783 | 61 | 12.8× |
| 50 | Sidecar STRICT | 761 | 96 | 7.9× |
| 50 | Ambient | 654 | 50 | 13.1× |
| 100 | Baseline | 825 | 87 | 9.5× |
| 100 | Sidecar DISABLE | 804 | 68 | 11.8× |
| 100 | Sidecar STRICT | 785 | 95 | 8.3× |
| 100 | Ambient | 646 | 63 | 10.3× |

> GKE ima ~5–15× niži QPS u odnosu na lokalno zbog realne mrežne latencije. Relativni redosled scenarija ostaje uglavnom konzistentan, uz izuzetak 100KB gde Sidecar STRICT na GKE-u nadmašuje Baseline zahvaljujući connection pooling-u Envoy proxy-ja.

---

## Kako reprodukovati

### Preduslovi

| Alat | Verzija |
|------|---------|
| kind | v0.31.0 |
| kubectl | v1.34.1 |
| istioctl | v1.28.3 |
| Docker | v29.2.0 |
| fortio | v1.75.0 |

```bash
# Instalacija fortio (ako nije prisutan)
brew install fortio
```

### Case Study A – Lokalno (kind)

#### Folder struktura rezultata

```
local-testing/
├── baseline/
│   ├── 01_standard/
│   │   ├── 1kb/    → run1.json .. run5.json
│   │   ├── 10kb/   → run1.json .. run5.json
│   │   └── 100kb/  → run1.json .. run5.json
│   ├── 02_stress/
│   │   ├── 1kb/    → stress-10t-run1.json .. stress-100t-run3.json
│   │   ├── 10kb/
│   │   └── 100kb/
│   ├── 03_resources_standard/
│   │   ├── 1kb/    → run1_resources.csv .. run5_resources.csv
│   │   ├── 10kb/
│   │   └── 100kb/
│   └── 04_resources_stress/
│       ├── 1kb/    → stress-10t-run1_resources.csv .. stress-100t-run3_resources.csv
│       ├── 10kb/
│       └── 100kb/
├── sidecar-disable/  (ista struktura)
├── sidecar-strict/   (ista struktura)
└── ambient/          (ista struktura)
```

> **CPU/RAM merenje:** svaki run ima sopstveni CSV fajl koji se pokreće i stopira zajedno sa tim runom.
> Format: `timestamp,pod-name,CPU(m),RAM(Mi)` – uzorkovanje svake 5 sekundi.
> `RetCodes` u Fortio JSON-u pokazuje broj uspešnih/neuspešnih zahteva (npr. `{"200": 3000}` = 0 grešaka za 50 QPS × 60s).

#### Priprema (jednom)

```bash
# 1. Kreiranje klastera
kind create cluster --name istio-perf

# 2. Build Docker slika
cd services/service-a && docker build -t europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-a:latest .
cd ../service-b       && docker build -t europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-b:latest .
cd ../service-c       && docker build -t europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-c:latest .
cd ../..

# 3. Učitavanje slika u kind klaster
kind load docker-image europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-a:latest --name istio-perf
kind load docker-image europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-b:latest --name istio-perf
kind load docker-image europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-c:latest --name istio-perf

# 4. Instalacija metrics-server (potreban za kubectl top pods)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Sačekaj da metrics-server bude spreman (30-60s)
kubectl wait --for=condition=Ready pod -l k8s-app=metrics-server -n kube-system --timeout=90s
kubectl top nodes  # treba da vrati CPU/RAM vrednosti
```

---

#### Scenario 1 – Baseline (bez Istio-a)

```bash
kubectl create ns plain-k8s
kubectl apply -f k8s/services.yaml -n plain-k8s
kubectl wait --for=condition=Ready pod --all -n plain-k8s --timeout=60s

# Sanity check
kubectl run curl-test --image=curlimages/curl --rm -i --restart=Never -n plain-k8s \
  -- curl -s "http://service-a/test?size=1"

# Port-forward (u pozadini)
kubectl port-forward svc/service-a 8080:80 -n plain-k8s &
PF_PID=$!
sleep 3
curl -s "http://localhost:8080/test?size=1" | head -c 80

# Inicijalni warmup
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

# Standard testovi – 5 runova × 3 payload-a
for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n plain-k8s --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/local-testing/baseline/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/local-testing/baseline/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

# Stress testovi – 3 runa × 3 thread nivoa × 3 payload-a
for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n plain-k8s --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/local-testing/baseline/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/local-testing/baseline/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# Čišćenje
kill $PF_PID
kubectl delete ns plain-k8s
```

---

#### Scenario 2 i 3 – Sidecar (mTLS DISABLE i STRICT)

> Scenariji 2 i 3 dele istu Istio instalaciju (`profile=default`). Prvo se pokreću testovi sa DISABLE,
> zatim se politika menja na STRICT i testovi se ponavljaju. Istio se instalira i deinstalira samo jednom.
>
> **Napomena o mTLS kontroli:** `PeerAuthentication` definiše server-side policy. Istio auto mTLS
> mehanizam automatski prilagođava klijentsku stranu bez potrebe za `DestinationRule` – pod uslovom
> da nema conflicting pravila (što je slučaj u ovom jednonamespace setupu).

```bash
istioctl install --set profile=default --skip-confirmation

kubectl create ns istio-sidecar
kubectl label ns istio-sidecar istio-injection=enabled
kubectl apply -f k8s/services.yaml -n istio-sidecar
kubectl wait --for=condition=Ready pod --all -n istio-sidecar --timeout=90s
kubectl get pods -n istio-sidecar  # treba da vidi 2/2 (app + envoy sidecar)

# Port-forward (u pozadini)
kubectl port-forward svc/service-a 8080:80 -n istio-sidecar &
PF_PID=$!
sleep 3

# --- Scenario 2: mTLS DISABLE ---
kubectl apply -n istio-sidecar -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: mtls-policy
  namespace: istio-sidecar
spec:
  mtls:
    mode: DISABLE
EOF

# Verifikacija da je mTLS isključen (transportSocket: {} = plaintext)
SIDECAR_POD_B=$(kubectl get pod -n istio-sidecar -l app=service-b -o jsonpath='{.items[0].metadata.name}')
kubectl exec ${SIDECAR_POD_B} -n istio-sidecar -c istio-proxy -- \
  curl -s localhost:15000/config_dump | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d.get('configs', []):
  if c.get('@type','').endswith('ListenersConfigDump'):
    for l in c.get('dynamic_listeners', []):
      if 'virtualInbound' in l.get('name',''):
        for fc in l.get('active_state',{}).get('listener',{}).get('filter_chains',[]):
          ts = fc.get('transport_socket',{})
          if ts: print('TLS aktivan:', ts.get('name'))
          else: print('plaintext (nema transport_socket)')
        break
"

# Sanity check + inicijalni warmup
curl -s "http://localhost:8080/test?size=1" | head -c 80
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/local-testing/sidecar-disable/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/local-testing/sidecar-disable/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/local-testing/sidecar-disable/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/local-testing/sidecar-disable/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# --- Scenario 3: mTLS STRICT ---
kubectl apply -n istio-sidecar -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: mtls-policy
  namespace: istio-sidecar
spec:
  mtls:
    mode: STRICT
EOF

# Sačekaj da Envoy osvježi konfiguraciju
sleep 5

# Verifikacija da je mTLS uključen (transport_socket = envoy.transport_sockets.tls)
SIDECAR_POD_B=$(kubectl get pod -n istio-sidecar -l app=service-b -o jsonpath='{.items[0].metadata.name}')
kubectl exec ${SIDECAR_POD_B} -n istio-sidecar -c istio-proxy -- \
  curl -s localhost:15000/config_dump | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d.get('configs', []):
  if c.get('@type','').endswith('ListenersConfigDump'):
    for l in c.get('dynamic_listeners', []):
      if 'virtualInbound' in l.get('name',''):
        for fc in l.get('active_state',{}).get('listener',{}).get('filter_chains',[]):
          ts = fc.get('transport_socket',{})
          if ts: print('TLS aktivan:', ts.get('name'))
        break
"

# Sanity check + inicijalni warmup
curl -s "http://localhost:8080/test?size=1" | head -c 80
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/local-testing/sidecar-strict/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/local-testing/sidecar-strict/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/local-testing/sidecar-strict/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/local-testing/sidecar-strict/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# Čišćenje
kill $PF_PID
kubectl delete ns istio-sidecar
istioctl uninstall --purge --skip-confirmation
kubectl delete ns istio-system
```

---

#### Scenario 4 – Ambient

```bash
istioctl install --set profile=ambient --skip-confirmation

kubectl create ns istio-ambient
kubectl label ns istio-ambient istio.io/dataplane-mode=ambient
kubectl apply -f k8s/services.yaml -n istio-ambient
kubectl wait --for=condition=Ready pod --all -n istio-ambient --timeout=90s

# Verifikacija – podovi imaju 1/1 (nema sidecar-a), ztunnel radi na node nivou
kubectl get pods -n istio-ambient
kubectl get pods -n istio-system | grep ztunnel

# Port-forward (u pozadini)
kubectl port-forward svc/service-a 8080:80 -n istio-ambient &
PF_PID=$!
sleep 3

# Sanity check + inicijalni warmup
curl -s "http://localhost:8080/test?size=1" | head -c 80
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-ambient --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/local-testing/ambient/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/local-testing/ambient/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n istio-ambient --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/local-testing/ambient/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/local-testing/ambient/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# Čišćenje
kill $PF_PID
kubectl delete ns istio-ambient
istioctl uninstall --purge --skip-confirmation
kubectl delete ns istio-system
```

---

## Kako reprodukovati – Case Study B (GKE)

### Infrastruktura (GKE)

| Komponenta | Vrednost |
|-----------|---------|
| Cloud | GCP (Google Cloud Platform) |
| Projekat | `istio-perf-1771697804` |
| Klaster | `istio-research-cluster` |
| Zona | `europe-west3-a` (Frankfurt) |
| Mašine | `e2-standard-2` (2 vCPU, 8 GB RAM) |
| Nodovi | 2 |
| Docker registry | `europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/` |

### Preduslovi

```bash
# Instalirani alati
gcloud   # Google Cloud CLI
kubectl
istioctl # v1.28+
fortio
```

#### Priprema (jednom)

```bash
# 1. Login na GCP
gcloud auth login

# 2. Povezi se na klaster
gcloud container clusters get-credentials istio-research-cluster \
  --zone europe-west3-a \
  --project istio-perf-1771697804

# 3. Skaliranje nodova na 2 (ako su na 0)
gcloud container clusters resize istio-research-cluster \
  --node-pool default-pool \
  --num-nodes 2 \
  --zone europe-west3-a \
  --project istio-perf-1771697804 \
  --quiet

# Sačekaj da nodovi budu Ready
kubectl get nodes

# 4. Verifikacija metrics-server (GKE ga instalira automatski)
kubectl top nodes  # treba da vrati CPU/RAM vrednosti

# 5. Push Docker slika na GCP registry (samo ako su slike izmenjene)
gcloud auth configure-docker europe-west3-docker.pkg.dev
docker push europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-a:latest
docker push europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-b:latest
docker push europe-west3-docker.pkg.dev/istio-perf-1771697804/istio-research/service-c:latest

# 6. Čisto stanje – proveri da nema ostataka prethodnih sesija
kubectl get pods -A | grep -v "kube-system\|gke-managed\|gmp-system"
# Ako postoje ostaci:
# kubectl delete ns istio-sidecar istio-ambient plain-k8s --ignore-not-found
# istioctl uninstall --purge --skip-confirmation
# kubectl delete ns istio-system --ignore-not-found
```

---

#### Scenario 1 – Baseline (bez Istio-a)

```bash
kubectl create ns plain-k8s
kubectl apply -f k8s/services.yaml -n plain-k8s
kubectl wait --for=condition=Ready pod --all -n plain-k8s --timeout=120s

# Sanity check
kubectl run curl-test --image=curlimages/curl --rm -i --restart=Never -n plain-k8s \
  -- curl -s "http://service-a/test?size=1"

# Port-forward (u pozadini)
kubectl port-forward svc/service-a 8080:80 -n plain-k8s &
PF_PID=$!
sleep 3
curl -s "http://localhost:8080/test?size=1" | head -c 80

# Inicijalni warmup
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

# Standard testovi – 5 runova × 3 payload-a
for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n plain-k8s --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/remote-testing/baseline/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/remote-testing/baseline/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

# Stress testovi – 3 runa × 3 thread nivoa × 3 payload-a
for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n plain-k8s --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/remote-testing/baseline/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/remote-testing/baseline/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# Čišćenje
kill $PF_PID
kubectl delete ns plain-k8s
```

---

#### Scenario 2 i 3 – Sidecar (mTLS DISABLE i STRICT)

> Scenariji 2 i 3 dele istu Istio instalaciju (`profile=default`). Prvo se pokreću testovi sa DISABLE,
> zatim se politika menja na STRICT i testovi se ponavljaju. Istio se instalira i deinstalira samo jednom.
>
> **Napomena o mTLS kontroli:** `PeerAuthentication` definiše server-side policy. Istio auto mTLS
> mehanizam automatski prilagođava klijentsku stranu bez potrebe za `DestinationRule`.

```bash
istioctl install --set profile=default --skip-confirmation

kubectl create ns istio-sidecar
kubectl label ns istio-sidecar istio-injection=enabled
kubectl apply -f k8s/services.yaml -n istio-sidecar
kubectl wait --for=condition=Ready pod --all -n istio-sidecar --timeout=120s
kubectl get pods -n istio-sidecar  # treba da vidi 2/2 (app + envoy sidecar)

# Port-forward (u pozadini)
kubectl port-forward svc/service-a 8080:80 -n istio-sidecar &
PF_PID=$!
sleep 3

# --- Scenario 2: mTLS DISABLE ---
kubectl apply -n istio-sidecar -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: mtls-policy
  namespace: istio-sidecar
spec:
  mtls:
    mode: DISABLE
EOF

# Verifikacija da je mTLS isključen (transportSocket: {} = plaintext)
SIDECAR_POD_B=$(kubectl get pod -n istio-sidecar -l app=service-b -o jsonpath='{.items[0].metadata.name}')
kubectl exec ${SIDECAR_POD_B} -n istio-sidecar -c istio-proxy -- \
  curl -s localhost:15000/config_dump | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d.get('configs', []):
  if c.get('@type','').endswith('ListenersConfigDump'):
    for l in c.get('dynamic_listeners', []):
      if 'virtualInbound' in l.get('name',''):
        for fc in l.get('active_state',{}).get('listener',{}).get('filter_chains',[]):
          ts = fc.get('transport_socket',{})
          if ts: print('TLS aktivan:', ts.get('name'))
          else: print('plaintext (nema transport_socket)')
        break
"

# Sanity check + inicijalni warmup
curl -s "http://localhost:8080/test?size=1" | head -c 80
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/remote-testing/sidecar-disable/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/remote-testing/sidecar-disable/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/remote-testing/sidecar-disable/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/remote-testing/sidecar-disable/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# --- Scenario 3: mTLS STRICT ---
kubectl apply -n istio-sidecar -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: mtls-policy
  namespace: istio-sidecar
spec:
  mtls:
    mode: STRICT
EOF

sleep 5

# Verifikacija da je mTLS uključen (transport_socket = envoy.transport_sockets.tls)
SIDECAR_POD_B=$(kubectl get pod -n istio-sidecar -l app=service-b -o jsonpath='{.items[0].metadata.name}')
kubectl exec ${SIDECAR_POD_B} -n istio-sidecar -c istio-proxy -- \
  curl -s localhost:15000/config_dump | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d.get('configs', []):
  if c.get('@type','').endswith('ListenersConfigDump'):
    for l in c.get('dynamic_listeners', []):
      if 'virtualInbound' in l.get('name',''):
        for fc in l.get('active_state',{}).get('listener',{}).get('filter_chains',[]):
          ts = fc.get('transport_socket',{})
          if ts: print('TLS aktivan:', ts.get('name'))
        break
"

# Sanity check + inicijalni warmup
curl -s "http://localhost:8080/test?size=1" | head -c 80
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/remote-testing/sidecar-strict/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/remote-testing/sidecar-strict/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

for payload in 1 10 100; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n istio-sidecar --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/remote-testing/sidecar-strict/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/remote-testing/sidecar-strict/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# Čišćenje
kill $PF_PID
kubectl delete ns istio-sidecar
istioctl uninstall --purge --skip-confirmation
kubectl delete ns istio-system
```

---

#### Scenario 4 – Ambient

> **Napomena za reprodukciju – 100KB stress:**
> `kubectl port-forward` nije dizajniran za visoku konkurentnost. Pri 100 threadova × 100KB payload-u,
> Fortio otvara konekcije brže nego što tunel može da ih prosledi, što uzrokuje timeout greške i
> nepotpune CSV fajlove resursa.
>
> Rešenje: pokrenuti Fortio direktno unutar klastera kao pod i slati zahteve na `http://service-a/...`
> unutar iste mreže — zaobilazeći port-forward u potpunosti. JSON rezultati su validni; samo CPU/RAM
> monitoring (CSV) iz prvog pokušaja je bio nepotpun i morao se ponoviti sa ovom metodologijom.
> Stress testovi za 1KB i 10KB payload nisu imali ovaj problem i koriste standardni port-forward pristup.

```bash
istioctl install --set profile=ambient --skip-confirmation

kubectl create ns istio-ambient
kubectl label ns istio-ambient istio.io/dataplane-mode=ambient
kubectl apply -f k8s/services.yaml -n istio-ambient
kubectl wait --for=condition=Ready pod --all -n istio-ambient --timeout=120s

# Verifikacija – podovi imaju 1/1 (nema sidecar-a), ztunnel radi na node nivou
kubectl get pods -n istio-ambient
kubectl get pods -n istio-system | grep ztunnel

# Port-forward (u pozadini)
kubectl port-forward svc/service-a 8080:80 -n istio-ambient &
PF_PID=$!
sleep 3

# Sanity check + inicijalni warmup
curl -s "http://localhost:8080/test?size=1" | head -c 80
fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=1" > /dev/null

for payload in 1 10 100; do
  fortio load -qps 50 -t 20s -c 4 "http://localhost:8080/test?size=${payload}" > /dev/null
  for i in 1 2 3 4 5; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-ambient --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/remote-testing/ambient/03_resources_standard/${payload}kb/run${i}_resources.csv &
    RES_PID=$!

    fortio load -qps 50 -t 60s -c 4 \
      -json k8s/results/remote-testing/ambient/01_standard/${payload}kb/run${i}.json \
      "http://localhost:8080/test?size=${payload}" > /dev/null

    kill $RES_PID
    sleep 15
  done
done

# Stress testovi – 1KB i 10KB payload (port-forward je dovoljan)
for payload in 1 10; do
  for threads in 10 50 100; do
    fortio load -c $threads -qps 0 -t 10s "http://localhost:8080/test?size=${payload}" > /dev/null
    for i in 1 2 3; do
      while true; do
        echo "$(date +%s),$(kubectl top pods -n istio-ambient --no-headers 2>/dev/null | tr -s ' ' ',')"
        sleep 5
      done > k8s/results/remote-testing/ambient/04_resources_stress/${payload}kb/stress-${threads}t-run${i}_resources.csv &
      RES_PID=$!

      fortio load -c $threads -qps 0 -t 60s \
        -json k8s/results/remote-testing/ambient/02_stress/${payload}kb/stress-${threads}t-run${i}.json \
        "http://localhost:8080/test?size=${payload}" > /dev/null

      kill $RES_PID
      sleep 15
    done
  done
done

# Stress testovi – 100KB payload: koristiti in-cluster Fortio da bi se izbegao port-forward bottleneck
kubectl run fortio --image=fortio/fortio:1.75.0 -n istio-ambient -- server
kubectl wait --for=condition=Ready pod/fortio -n istio-ambient --timeout=60s

for threads in 10 50 100; do
  kubectl exec fortio -n istio-ambient -- fortio load -c $threads -qps 0 -t 10s \
    "http://service-a/test?size=100" > /dev/null
  for i in 1 2 3; do
    while true; do
      echo "$(date +%s),$(kubectl top pods -n istio-ambient --no-headers 2>/dev/null | tr -s ' ' ',')"
      sleep 5
    done > k8s/results/remote-testing/ambient/04_resources_stress/100kb/stress-${threads}t-run${i}_resources.csv &
    RES_PID=$!

    kubectl exec fortio -n istio-ambient -- fortio load -c $threads -qps 0 -t 60s \
      -json /tmp/stress-${threads}t-run${i}.json \
      "http://service-a/test?size=100" > /dev/null
    kubectl cp istio-ambient/fortio:/tmp/stress-${threads}t-run${i}.json \
      k8s/results/remote-testing/ambient/02_stress/100kb/stress-${threads}t-run${i}.json

    kill $RES_PID
    sleep 15
  done
done

kubectl delete pod fortio -n istio-ambient

# Čišćenje
kill $PF_PID
kubectl delete ns istio-ambient
istioctl uninstall --purge --skip-confirmation
kubectl delete ns istio-system

# Nakon svih scenarija – skaliranje nodova na 0 da se ne naplaćuje
gcloud container clusters resize istio-research-cluster \
  --node-pool default-pool \
  --num-nodes 0 \
  --zone europe-west3-a \
  --project istio-perf-1771697804 \
  --quiet
```

---

## Zaključci

### Case Study A – Lokalno (kind)

1. **Baseline ima najlošiji tail latency (P99) pri standardnom opterećenju** – P99 je konzistentno ~25 ms za sva 3 payload-a, dok Envoy scenariji postižu 19–21 ms. Razlog: Envoy koristi connection pooling i efikasnije upravlja konekcijama nego direktni Node.js HTTP stack.

2. **Payload veličina otkriva cenu mTLS enkripcije** – na 100KB Sidecar STRICT (14.1 ms avg) i Ambient (14.3 ms avg) su sporiji od Sidecar DISABLE (13.6 ms avg). Razlika od ~0.5 ms u avg i ~2.5 ms u P99 direktno reflektuje TLS handshake i enkripciju podataka.

3. **Sidecar dramatično nadmašuje sve pri visokom stresu, ali uz veću cenu resursa** – pri 100 threadova Sidecar DISABLE postiže 2561 QPS (avg 39 ms), Sidecar STRICT 2483 QPS (avg 40 ms), dok Baseline stagnira na 1631 QPS (avg 62 ms). Envoy event-loop model skalira daleko bolje od Node.js HTTP servera pod visokom konkurentnošću. Međutim, ta prednost dolazi uz ~2× veću potrošnju CPU-a (Sidecar DISABLE 2930m, Sidecar STRICT 3078m vs Baseline 1614m pri 100t/1KB) i ~2× veći RAM (392–408 Mi vs 215 Mi).

4. **Ambient je najlošiji pod stresom, ali ima najmanji resursni overhead** – 1602 QPS i 63 ms pri 100 threadova, gotovo identičan Baseline-u. ztunnel (L4 proxy) uvodi per-packet overhead koji ne skalira kao Envoy L7 proxy. Prednost: CPU i RAM su gotovo identični Baseline-u (1648m / 216 Mi vs 1614m / 215 Mi), što ga čini pogodnim za resource-constrained okruženja.

5. **mTLS overhead je minimalan pod stresom, ali nosi memorijsku cenu** – razlika između Sidecar DISABLE (2561 QPS) i Sidecar STRICT (2483 QPS) je svega 3%. Enkripcija nije bottleneck za propusnost, ali Sidecar STRICT konzistentno troši više RAM-a od DISABLE (408 Mi vs 392 Mi pri 100t), što reflektuje memoriju za TLS sesije i kriptografske kontekste.

> **Napomena:** Lokalni testovi mere overhead proksija bez mrežnog faktora (loopback komunikacija unutar jednog Docker kontejnera). Ovi rezultati predstavljaju "idealni donji bound" – u realnom okruženju sa fizičkom mrežom razlike između scenarija biće izraženije.

### Case Study B – Remote (GKE)

1. **Baseline je najbrži u standardnom testu – overhead Istio-a je merljiv** – svi Istio scenariji sporiji su od Baseline-a pri 50 QPS. Overhead iznosi: Sidecar DISABLE +12–15ms (~18–21%), Sidecar STRICT +10–12ms (~14–17%) pri 1KB/10KB (praktično nula pri 100KB), Ambient +16–19ms (~23–27%). Overhead je mali u kontekstu ukupne GKE latencije (~68ms), ali je konzistentan i merljiv.

2. mTLS enkripcija ne dodaje značajan overhead pri normalnom opterećenju – Sidecar STRICT (mTLS aktivan) je blago brži 
od Sidecar DISABLE pri 1KB i 10KB payload-u (78ms vs 80ms, 82ms vs 85ms). Razlog: ova razlika nije direktno vezana za mTLS mehanizam, već verovatno proizilazi iz ponašanja konekcija (connection reuse, pooling) i implementacionih detalja Envoy proxy-ja. HTTP protokol (HTTP/1.1 vs HTTP/2) nije direktno vezan za mTLS mod i konfiguriše se nezavisno. Ovo je ključan nalaz: uključivanje mTLS-a ne mora nužno dovesti do pogoršanja performansi.

3. **Sidecar STRICT + 100KB stress: viši QPS nego Baseline** – pri stress testu sa 100KB payload-om, Sidecar STRICT postiže 83–96 QPS naspram Baseline-ovih 77–87 QPS. Ovaj efekat verovatno proizilazi iz efikasnijeg upravljanja konekcijama (connection reuse, pooling) i optimizacija unutar Envoy proxy-ja, koje pri većim payload-ovima i višoj konkurentnosti dolaze do izražaja.

4. **Overhead Istio-a raste sa konkurentnošću (1KB stress)**:

   | Threads | Baseline | Sidecar DISABLE | Sidecar STRICT | Ambient |
   |---------|----------|-----------------|----------------|---------|
   | 10t QPS | 141 | 125 (-11%) | 130 (-8%) | 116 (-18%) |
   | 50t QPS | 296 | 188 (-36%) | 211 (-29%) | 155 (-48%) |
   | 100t QPS | 310 | 195 (-37%) | 219 (-29%) | 138 (-55%) |

   Relativni pad QPS-a raste od ~8–18% pri 10 threadova do 29–55% pri 100 threadova. Sistem postaje **proxy-CPU-bound**, ne mrežno-bound — merenja potvrđuju: Sidecar scenariji na GKE pri 100t troše 1153–1238m od ukupno ~2000m dostupnih (2 vCPU × 1000m), dok Baseline troši 1188m ali postiže viši QPS jer nema proxy sloj.

5. **Ambient je najslabiji pod visokim stresom, ali sa znatno manjim resursnim otiskom** – ztunnel radi na nivou čvora i svaki paket prolazi kernel ↔ ztunnel ↔ kernel tranziciju. Pod visokom konkurentnošću, ovaj overhead postaje bottleneck koji sidecar model nema. Pri 100KB stress testu Ambient postiže 38 QPS (10t), 50 QPS (50t), 63 QPS (100t) vs Baseline 77–87 QPS. Međutim, Ambient troši značajno manje resursa od Sidecar modela pri visokom stresu (691m CPU / 179 Mi vs 1238m / 336 Mi za Sidecar STRICT pri 100t/1KB na GKE), što može biti odlučujući faktor u okruženjima sa ograničenim resursima.

### Sveobuhvatni zaključci

1. **Istio overhead je realan ali umeren** – pri normalnom opterećenju (50 QPS) iznosi 10–19ms na GKE-u (~14–27% baseline latencije). Za većinu aplikacija ovo je prihvatljiva cena za napredne mesh funkcionalnosti (observability, traffic management, zero-trust sigurnost).

2. **mTLS nije "sporiji"** – Sidecar STRICT je konzistentno brži ili jednak Sidecar DISABLE-u. Mehanizmi poput connection reuse i optimizacija u radu Envoy proxy-ja mogu amortizovati overhead enkripcije pri uobičajenom opterećenju. Preporuka: koristiti STRICT mod bez značajnog rizika po performanse.

3. **Sidecar model je bolji izbor za visoko-paralelne workload-ove, uz resursni kompromis** – pod stresom (100t), Envoy L7 proxy skalira dramatično bolje od direktnog Node.js stacka (+57% QPS) ili ztunnel-a (+41% QPS). Ambient (ztunnel) ne pruža ove prednosti jer radi na L4. Cena sidecara: ~2× veći CPU i RAM od Baseline-a pod punim opterećenjem.

4. **Lokalni vs. GKE: različite dimenzije merenja** – kind meri čisti proxy overhead bez mreže (~10–16ms pri 1KB), GKE meri proxy overhead + realna mreža (~55ms RTT). Apsolutni overhead sličan je na oba okruženja, ali relativni udeo je drugačiji (14–23% na GKE vs dominantna komponenta lokalno).

5. **Ambient je perspektivna tehnologija sa jasnim tradeoff-om** – lošije performanse pod stresom, ali značajno manji resursni otisak od Sidecar modela (bez per-pod proxy kontejnera, CPU i RAM blizu Baseline nivoa). Dobra opcija za okruženja gde je jednostavnost i efikasnost resursa važnija od maksimalnog throughput-a.

6. **Sidecar modeli nose 2–3× veći RAM overhead od Baseline-a** – u standardnom testu lokalno, Sidecar DISABLE troši 271–280 Mi, Sidecar STRICT 327–341 Mi, dok Baseline i Ambient ostaju na 142–164 Mi. Ovo je relevantan trošak u resource-constrained okruženjima (npr. edge computing, mali Kubernetes klasteri) i treba ga uzeti u obzir pri planiranju kapaciteta.

---

## Struktura projekta

```
istio-performance-test/
├── services/
│   ├── service-a/          # Entry point (Node.js/Express)
│   ├── service-b/          # Intermediate service
│   └── service-c/          # Leaf service, generiše payload
├── k8s/
│   ├── services.yaml       # Kubernetes manifesti (Deployment + Service × 3)
│   └── results/
│       ├── local-testing/  # Case Study A – kind klaster (sa CPU/RAM merenjem)
│       │   ├── baseline/
│       │   │   ├── 01_standard/{1kb,10kb,100kb}/   → run1..5.json
│       │   │   ├── 02_stress/{1kb,10kb,100kb}/     → stress-10t-run1..stress-100t-run3.json
│       │   │   ├── 03_resources_standard/{1kb,10kb,100kb}/  → run1..5_resources.csv
│       │   │   └── 04_resources_stress/{1kb,10kb,100kb}/    → stress-*_resources.csv
│       │   ├── sidecar-disable/  (ista struktura)
│       │   ├── sidecar-strict/   (ista struktura)
│       │   ├── ambient/          (ista struktura)
│       │   ├── chart_lt_standard.png
│       │   ├── chart_lt_stress.png
│       │   └── chart_lt_resources.png
│       └── remote-testing/ # Case Study B – GKE (ista struktura kao local-testing)
├── generate_charts.py      # Generiše PNG grafike iz JSON rezultata
└── README.md
```
