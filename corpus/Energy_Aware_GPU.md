# Energy-Aware GPU Computing

A system that **measures** the energy GPU workloads consume and **schedules** GPU jobs
so they meet their deadlines while using as little energy as possible.

## Problem

GPUs are usually run in "performance mode": the largest batch, the default
precision, and finishing as fast as possible. That is not always the most
energy-efficient choice. Energy depends on *how* a job runs (batch size,
numeric precision, clock frequency), and many jobs do not need to finish as
early as possible, only before a deadline. This project answers two
questions:

1. How do batch size and precision affect GPU power, speed and energy per unit of work?
2. Given a set of jobs with deadlines, which configuration should each job use to
   minimise total energy without missing any deadline?

## Architecture

```
            ┌────────────────────┐
            │  workloads.py      │  matmul · ResNet-18 train · ResNet-50 inference
            │  knobs: batch,     │  precision ∈ {FP32, TF32, FP16-AMP}
            │  precision         │
            └─────────┬──────────┘
                      │ runs on GPU
┌──────────────┐      ▼
│ monitor.py   │◄── NVML: hardware energy counter (mJ) + power sampling thread
└──────┬───────┘
       │ time, energy, power per configuration
       ▼
┌──────────────┐   results/profile.csv    ┌───────────────┐
│ profiler.py  │ ───────────────────────► │ scheduler.py  │ ◄── jobs.json (work + deadlines)
└──────────────┘                          │ 3 policies    │
                                          └──────┬────────┘
                                                 │ plan, predicted & measured energy
                                                 ▼
                              plots.py (report figures) · dashboard.py (live demo)
```

| Module | Purpose |
|---|---|
| `eagpu/monitor.py` | Energy measurement through NVML: samples power every 10 ms and integrates it (trapezoidal rule). The hardware energy counter is cross-checked and used only when it agrees within 20% (see *Measurement validation*). Optional clock locking (DVFS). |
| `eagpu/workloads.py` | Three representative GPU workloads with tunable batch size and precision. Uses synthetic data, so no dataset download is needed and disk I/O does not affect measurements. |
| `eagpu/profiler.py` | Sweeps every configuration and records throughput, average/peak power, energy per sample and energy-delay product (EDP). |
| `eagpu/scheduler.py` | Plans configurations for a batch of jobs under three policies, predicts energy, and can run the plan on the GPU to measure the real energy use. |
| `eagpu/plots.py` | Report-quality figures. |
| `dashboard.py` | Streamlit dashboard with live power/utilisation and the results. |

## Measurement validation

Four findings on the test machine (RTX 4060 Laptop GPU, driver 566.07) shaped the design:

1. **The hardware energy counter is unreliable on this GPU.** Under a steady
   matrix-multiply load, the NVML energy counter implied 325–367 W. That is
   impossible for a laptop GPU rated at about 140 W. Instantaneous power readings
   stayed at a steady ~95 W. The monitor therefore integrates sampled power and
   trusts the counter only when the two agree to within 20%. Raw counter values
   are still recorded in `profile.csv` (`counter_energy_j`).
2. **The GPU does not go idle immediately.** After work stops, the driver keeps it
   at a high clock (about 20–27 W) for about 7–10 s, then it drops to deep idle
   (about 2 W). The profiler measures both levels and the scheduler models idle
   energy with these two levels.

3. **The power cap changes with the laptop's power mode.** During testing, the
   driver's enforced power limit dropped from about 100 W to 55 W without any
   change to the code, which changed every energy figure. The limit is recorded
   with each measurement (`power_limit_w`). The profiler warns if it changes
   mid-sweep, and the scheduler warns if it differs from the profile. **Keep the
   laptop plugged in, in one fixed power mode, for all experiments.**
4. **The power sensor occasionally glitches** near deep idle (one reading of 590 W).
   Samples above twice the power limit are discarded.

Laptop GPUs also shift power with the CPU (Dynamic Boost) and throttle when hot,
so each configuration is measured 3 times and the median run is kept. The
`energy_spread_pct` column reports the spread between the repeats.

## Energy model and scheduling algorithm

Over a scheduling window of length *H*, the GPU is either running job *i* (energy
*Eᵢ*, time *tᵢ*) or idling at power *P_idle*:

```
E_window = Σ Eᵢ + P_idle · (H − Σ tᵢ)  =  Σ (Eᵢ − P_idle · tᵢ)  +  P_idle · H
```

`P_idle · H` is the same for every policy, so minimising window energy is the
same as minimising each job's **dynamic energy** `Eᵢ − P_idle·tᵢ` (energy above
idle). This captures the **race-to-idle** trade-off: running fast lets the GPU
reach idle sooner, but idle power is not zero. Reported window energy uses the
two-level idle model (active idle for the hold time, then deep idle). The
optimiser uses deep-idle power as `P_idle`.

**Policies**

| Policy | Rule |
|---|---|
| `default` | FP32 at a typical batch size: what most users run. |
| `performance` | Highest-throughput configuration (race to idle). |
| `energy_aware` | Slack reclamation. Jobs are ordered by earliest deadline first (EDF), and each starts at its minimum-dynamic-energy configuration. While a deadline is missed, the heuristic applies the configuration switch (among jobs up to the first miss) with the lowest *extra energy per second saved*, and repeats until every deadline is met or no faster option remains. |

## Setup

Requirements: NVIDIA GPU with a recent driver and Python 3.10 or newer.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install nvidia-ml-py pandas matplotlib streamlit
```

## Running the experiments

```powershell
# 1. Profile all workloads (≈5–10 min; use --quick for a fast check)
python -m eagpu.profiler

# 2. Plan the job set in jobs.json with all three policies, then run each on the GPU
python -m eagpu.scheduler --jobs jobs.json --run

# 3. How do savings change as deadlines get looser? (prediction only, instant)
python -m eagpu.scheduler --jobs jobs.json --sweep

# 4. Figures for the report → results/fig_*.png
python -m eagpu.plots

# 5. Live demo dashboard
streamlit run dashboard.py
```

Other options:
- `--slack 1.5` sets every deadline to 1.5 × the fastest possible finish time.
- `python -m eagpu.profiler --clocks 1200 1800 2400 3105` also sweeps SM clock
  frequencies (DVFS). This needs an **administrator** terminal and may be blocked
  on laptop GPUs.

## Outputs (`results/`)

| File | Contents |
|---|---|
| `profile.csv`, `profile_meta.json` | Per-configuration measurements, idle power and GPU info |
| `schedule_<policy>.csv` | Job-by-job plan: config, start/finish, deadline met, energy (predicted and measured) |
| `schedule_summary.csv` | Energy, makespan, deadlines met and % saving for each policy |
| `slack_sweep.csv` | Predicted energy per policy for slack 1.0–3.0 |
| `fig_profile.png`, `fig_schedule.png`, `fig_slack_sweep.png` | Report figures |

## Results (RTX 4060 Laptop GPU, ~95 W power mode)

**Profiling** (`fig_profile.png`). Precision and batch size change energy per sample a lot:

| Workload | Default (FP32, typical batch) | Best config | Energy reduction |
|---|---|---|---|
| matmul 2048² | 220 mJ (bs 1) | FP16, bs 1: 77 mJ | 65% |
| ResNet-18 training | 17.0 mJ (bs 32) | FP16, bs 256: 2.9 mJ | 83% |
| ResNet-50 inference | 176 mJ (bs 8) | FP16, bs 16: 81 mJ | 54% |

**Scheduling** (`jobs.json`: 5 jobs, deadlines between 1.6× and 2.4× the fastest
finish time; executed and measured on the GPU, `fig_schedule.png`):

| Policy | Window energy | Deadlines met | vs default |
|---|---|---|---|
| default | 3690 J | 0 / 5 | — |
| performance | 1326 J | 5 / 5 | −64% |
| energy-aware | 1401 J | 5 / 5 | −62% |

Predicted job times matched measurements to within about 1–3% for most jobs
(worst case 14%), and predicted energy matched to within about 10%.

**Key finding.** With only batch size and precision as knobs, the fastest
configuration is also the most energy-efficient one for every workload, because
higher GPU utilisation improves both. So energy-aware and race-to-idle choose
**identical** plans. The 1326 J vs 1401 J difference above is run-to-run
measurement noise, not a policy difference. Energy-aware scheduling has room to
beat race-to-idle only with a knob that trades speed for energy, which is
**clock frequency (DVFS)**. In a simulation where lower clocks are 1.4× slower
but use 25% less energy per sample, the energy-aware policy saved up to 32% more
than race-to-idle at 1.5× slack, while meeting every deadline.

### Next step: DVFS experiment (requires administrator)

Open PowerShell **as Administrator**, keep the laptop plugged in in one power mode, then:

```powershell
cd "D:\trans bhoiii\Energy_Aware_GPU"
.venv\Scripts\activate
python -m eagpu.profiler --clocks 1000 1500 2000 2500
python -m eagpu.scheduler --jobs jobs.json --run
python -m eagpu.scheduler --jobs jobs.json --sweep
python -m eagpu.plots
```

## Limitations and future work

- NVML reports **whole-board** power, so other GPU activity (such as the desktop or a
  browser) adds noise. Close other GPU applications while measuring, and repeat runs.
- Laptop GPUs usually do not allow changing the power limit, and clock locking
  may require admin rights, so the main knobs here are batch size and precision.
- FP16 changes numerics. For training, check that accuracy is not affected.
- Possible extensions: an ML model that predicts energy for unseen workloads;
  online scheduling of jobs that arrive over time; multi-GPU placement;
  carbon-aware scheduling using grid carbon intensity.
