import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SZENARIEN = [
    "status_quo",
    "alle_pv_mit_last",
    "alle_pv_ohne_last",
    "60_pv_mit_last",
    "60_pv_ohne_last",
]

# Nur Szenarien auswerten, deren Ordner tatsächlich existiert
SZENARIEN = [s for s in SZENARIEN
             if os.path.isdir(os.path.join(BASE_DIR, f"results_{s}"))]

# Ausgabeordner für die Plots
PLOT_DIR = os.path.join(BASE_DIR, "auswertung_plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# Spannungsgrenzen nach EN 50160 (±6% von Un)
U_MIN = 0.94
U_MAX = 1.06


def load_result(szenario, subfolder, filename):
    """Lädt eine Ergebnisdatei und hängt einen stündlichen Zeitindex an."""
    path = os.path.join(BASE_DIR, f"results_{szenario}", subfolder, filename)
    df = pd.read_excel(path, index_col=0)
    df.index = pd.date_range("2021-01-01", periods=len(df), freq="h")
    return df


def save_and_close(fig, filename):
    """Matplotlib-Figur speichern und schließen."""
    path = os.path.join(PLOT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  gespeichert: {path}")


def plot_max_line_loading(szenario):
    df = load_result(szenario, "res_line", "loading_percent.xlsx")
    max_loading = df.max()

    fig, ax = plt.subplots(figsize=(max(10, len(max_loading) * 0.25), 6))
    colors = ["#d62728" if v > 100 else "#ff9800" if v > 80 else "#2ca02c"
              for v in max_loading]
    ax.bar(range(len(max_loading)), max_loading.values, color=colors)
    ax.axhline(100, color="red", linestyle="--", linewidth=1, label="100 %")
    ax.axhline(80, color="orange", linestyle=":", linewidth=1, label="80 %")
    ax.set_xticks(range(len(max_loading)))
    ax.set_xticklabels([f"Leitung {c}" for c in max_loading.index],
                       rotation=90, fontsize=8)
    ax.set_ylabel("max. Belastung [%]")
    ax.set_title(f"Maximale Leitungsbelastung – {szenario}")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    save_and_close(fig, f"max_line_loading_{szenario}.png")


def plot_voltage_band(szenario):
    df = load_result(szenario, "res_bus", "vm_pu.xlsx")
    v_min = df.min()
    v_max = df.max()

    # Abweichungen von der Nennspannung 1.0 p.u.
    delta_up = (v_max - 1.0).values      # positiv
    delta_down = (v_min - 1.0).values    # negativ (Balken zeigt nach unten)

    x = np.arange(len(df.columns))

    fig, ax = plt.subplots(figsize=(max(10, len(df.columns) * 0.25), 6))
    ax.bar(x, delta_up, bottom=1.0, width=0.7,
           color="#ff7f0e", label="max")
    ax.bar(x, delta_down, bottom=1.0, width=0.7,
           color="#1f77b4", label="min")

    # Nennspannung als Nulllinie
    ax.axhline(1.0, color="black", linewidth=0.8)
    # Grenzen
    ax.axhline(U_MAX, color="red", linestyle="--", linewidth=1,
               label=f"{U_MAX} p.u.")
    ax.axhline(U_MIN, color="red", linestyle="--", linewidth=1,
               label=f"{U_MIN} p.u.")

    ax.set_xticks(x)
    ax.set_xticklabels([f"Bus {c}" for c in df.columns],
                       rotation=90, fontsize=8)
    ax.set_ylabel("Spannung [p.u.]")
    ax.set_title(f"Spannungsband (min/max je Bus) – {szenario}")

    # y-Achse symmetrisch um 1.0 setzen
    max_dev = max(abs(delta_down.min()), delta_up.max(),
                  1.0 - U_MIN, U_MAX - 1.0) + 0.005
    ax.set_ylim(1.0 - max_dev, 1.0 + max_dev)

    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    save_and_close(fig, f"voltage_band_{szenario}.png")


def plot_trafo_duration_curve(szenario):
    df = load_result(szenario, "res_trafo", "loading_percent.xlsx")

    fig, ax = plt.subplots(figsize=(10, 6))
    # Jede Trafo-Spalte einzeln (in der Regel nur eine)
    for col in df.columns:
        sorted_vals = np.sort(df[col].values)[::-1]  # absteigend
        hours = np.arange(1, len(sorted_vals) + 1)
        ax.plot(hours, sorted_vals, label=f"Trafo {col}")

    ax.axhline(100, color="red", linestyle="--", linewidth=1, label="100 %")
    ax.set_xlabel("Stunden [h]")
    ax.set_ylabel("Belastung [%]")
    ax.set_title(f"Jahresdauerlinie Trafo-Belastung – {szenario}")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    save_and_close(fig, f"trafo_duration_curve_{szenario}.png")


def plot_worst_line_heatmap(szenario, zmax=100):
    df = load_result(szenario, "res_line", "loading_percent.xlsx")
    df.columns = [f"Leitung {c}" for c in df.columns]

    # meistbelastete Leitung identifizieren
    worst_line = df.max().idxmax()
    worst_value = df.max().max()
    print(f"  meistbelastete Leitung: {worst_line} (max {worst_value:.1f} %)")

    # Als Tages-x-Stunden-Matrix (365 x 24) umformen
    series = df[worst_line]
    matrix = series.values.reshape(365, 24)

    fig = px.imshow(
        matrix.T,
        color_continuous_scale="RdYlGn_r",
        origin="lower",
        aspect="auto",
        zmin=0,
        zmax=70,
        labels={"x": "Tag im Jahr", "y": "Stunde des Tages",
                "color": "Loading [%]"},
        title=f"Teppichplot – {worst_line} (max {worst_value:.1f} %) – {szenario}",
    )
    fig.update_layout(
        width=1500,
        height=500,
        margin=dict(l=20, r=20, t=50, b=20),
    )

    out_path = os.path.join(PLOT_DIR, f"heatmap_worst_line_{szenario}.html")
    fig.write_html(out_path)
    print(f"  gespeichert: {out_path}")
    fig.show()


if __name__ == "__main__":
    if not SZENARIEN:
        raise SystemExit("Keine results_*-Ordner neben dem Skript gefunden.")

    print(f"Gefundene Szenarien: {SZENARIEN}")
    print(f"Plots werden gespeichert in: {PLOT_DIR}\n")

    # Globales Maximum über alle Szenarien für einheitliche Heatmap-Skala
    global_max = 0
    for sz in SZENARIEN:
        df = load_result(sz, "res_line", "loading_percent.xlsx")
        global_max = max(global_max, df.max().max())
    print(f"Globales Maximum Leitungsbelastung: {global_max:.1f} %\n")

    for sz in SZENARIEN:
        print(f"--- Szenario: {sz} ---")
        plot_max_line_loading(sz)
        plot_voltage_band(sz)
        plot_trafo_duration_curve(sz)
        plot_worst_line_heatmap(sz, zmax=global_max)
        print()

    print("Fertig.")