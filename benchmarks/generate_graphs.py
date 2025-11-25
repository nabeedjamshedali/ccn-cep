#!/usr/bin/env python3
"""
Generate visualization graphs for Energy Efficiency Benchmark
Creates charts comparing Default vs Adaptive scheduler performance
"""

import json
import os

# Check if matplotlib is available, if not provide instructions
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("matplotlib not installed. Install with: pip3 install matplotlib --break-system-packages")


def create_energy_comparison_chart(default_energy, adaptive_energy, filename="energy_comparison.png"):
    """Create bar chart comparing total energy consumption"""
    if not MATPLOTLIB_AVAILABLE:
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    schedulers = ['Default\nScheduler', 'Adaptive\nScheduler']
    energies = [default_energy, adaptive_energy]
    colors = ['#FF6B6B', '#4ECDC4']

    bars = ax.bar(schedulers, energies, color=colors, width=0.5, edgecolor='black', linewidth=2)

    # Add value labels on bars
    for bar, energy in zip(bars, energies):
        height = bar.get_height()
        ax.annotate(f'{energy:.1f} J',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=14, fontweight='bold')

    # Calculate savings
    savings = default_energy - adaptive_energy
    savings_pct = (savings / default_energy) * 100

    ax.set_ylabel('Energy Consumption (Joules)', fontsize=12, fontweight='bold')
    ax.set_title(f'Energy Efficiency Comparison\n(Adaptive saves {savings_pct:.1f}% energy)',
                 fontsize=14, fontweight='bold')

    # Add savings annotation
    ax.annotate(f'Savings: {savings:.1f} J',
                xy=(0.5, (default_energy + adaptive_energy) / 2),
                xytext=(1.5, default_energy * 0.8),
                fontsize=12,
                arrowprops=dict(arrowstyle='->', color='green'),
                color='green', fontweight='bold')

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")


def create_load_distribution_chart(default_metrics, adaptive_metrics, filename="load_distribution.png"):
    """Create comparison of load distribution across nodes"""
    if not MATPLOTLIB_AVAILABLE:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Default scheduler
    nodes = [m['node'].replace('minikube', 'Node') for m in default_metrics]
    cpu_default = [m['cpu_percent'] for m in default_metrics]

    bars1 = ax1.bar(nodes, cpu_default, color='#FF6B6B', edgecolor='black', linewidth=2)
    ax1.set_ylabel('CPU Utilization (%)', fontsize=12)
    ax1.set_title('Default Scheduler\n(Imbalanced Distribution)', fontsize=12, fontweight='bold')
    ax1.set_ylim(0, 100)

    # Add variance
    import statistics
    variance_default = statistics.variance(cpu_default) if len(cpu_default) > 1 else 0
    ax1.text(0.5, 0.95, f'Variance: {variance_default:.2f}',
             transform=ax1.transAxes, fontsize=11,
             verticalalignment='top', horizontalalignment='center',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Adaptive scheduler
    cpu_adaptive = [m['cpu_percent'] for m in adaptive_metrics]

    bars2 = ax2.bar(nodes, cpu_adaptive, color='#4ECDC4', edgecolor='black', linewidth=2)
    ax2.set_ylabel('CPU Utilization (%)', fontsize=12)
    ax2.set_title('Adaptive Scheduler\n(Balanced Distribution)', fontsize=12, fontweight='bold')
    ax2.set_ylim(0, 100)

    variance_adaptive = statistics.variance(cpu_adaptive) if len(cpu_adaptive) > 1 else 0
    ax2.text(0.5, 0.95, f'Variance: {variance_adaptive:.2f}',
             transform=ax2.transAxes, fontsize=11,
             verticalalignment='top', horizontalalignment='center',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.suptitle('Load Distribution Comparison (40 Pods)', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")


def create_phase_comparison_chart(default_phases, adaptive_phases, filename="phase_comparison.png"):
    """Create line chart showing energy consumption per phase"""
    if not MATPLOTLIB_AVAILABLE:
        return

    fig, ax = plt.subplots(figsize=(12, 6))

    phases = [p['target_pods'] for p in default_phases]
    default_energy = [p['energy']['energy_joules'] for p in default_phases]
    adaptive_energy = [p['energy']['energy_joules'] for p in adaptive_phases]

    ax.plot(phases, default_energy, 'o-', color='#FF6B6B', linewidth=3,
            markersize=10, label='Default Scheduler')
    ax.plot(phases, adaptive_energy, 's-', color='#4ECDC4', linewidth=3,
            markersize=10, label='Adaptive Scheduler')

    ax.fill_between(phases, default_energy, adaptive_energy,
                    alpha=0.3, color='green', label='Energy Savings')

    ax.set_xlabel('Number of Pods', fontsize=12, fontweight='bold')
    ax.set_ylabel('Energy Consumption (Joules)', fontsize=12, fontweight='bold')
    ax.set_title('Energy Consumption During Exponential Growth', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")


def create_summary_dashboard(results, filename="benchmark_dashboard.png"):
    """Create a complete dashboard with all metrics"""
    if not MATPLOTLIB_AVAILABLE:
        return

    fig = plt.figure(figsize=(16, 12))

    default = results['default_scheduler']
    adaptive = results['adaptive_scheduler']

    # 1. Energy Comparison (top left)
    ax1 = fig.add_subplot(2, 2, 1)
    schedulers = ['Default', 'Adaptive']
    energies = [default['total_energy_joules'], adaptive['total_energy_joules']]
    colors = ['#FF6B6B', '#4ECDC4']
    bars = ax1.bar(schedulers, energies, color=colors, edgecolor='black', linewidth=2)
    ax1.set_ylabel('Energy (Joules)')
    ax1.set_title('Total Energy Consumption', fontweight='bold')
    for bar, energy in zip(bars, energies):
        ax1.annotate(f'{energy:.1f}J', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                     ha='center', va='bottom', fontweight='bold')

    # 2. Phase-by-phase comparison (top right)
    ax2 = fig.add_subplot(2, 2, 2)
    phases = [p['target_pods'] for p in default['phases']]
    d_energy = [p['energy']['energy_joules'] for p in default['phases']]
    a_energy = [p['energy']['energy_joules'] for p in adaptive['phases']]

    x = range(len(phases))
    width = 0.35
    ax2.bar([i - width/2 for i in x], d_energy, width, label='Default', color='#FF6B6B')
    ax2.bar([i + width/2 for i in x], a_energy, width, label='Adaptive', color='#4ECDC4')
    ax2.set_xlabel('Pod Count')
    ax2.set_ylabel('Energy (Joules)')
    ax2.set_title('Energy per Scaling Phase', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(phases)
    ax2.legend()

    # 3. Load Variance Comparison (bottom left)
    ax3 = fig.add_subplot(2, 2, 3)
    d_variance = [p['energy']['load_variance'] for p in default['phases']]
    a_variance = [p['energy']['load_variance'] for p in adaptive['phases']]

    ax3.plot(phases, d_variance, 'o-', color='#FF6B6B', linewidth=2, markersize=8, label='Default')
    ax3.plot(phases, a_variance, 's-', color='#4ECDC4', linewidth=2, markersize=8, label='Adaptive')
    ax3.set_xlabel('Pod Count')
    ax3.set_ylabel('Load Variance')
    ax3.set_title('Load Distribution Variance\n(Lower = More Balanced)', fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Summary Statistics (bottom right)
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.axis('off')

    savings = default['total_energy_joules'] - adaptive['total_energy_joules']
    savings_pct = (savings / default['total_energy_joules']) * 100

    summary_text = f"""
    BENCHMARK SUMMARY
    {'='*40}

    Default Scheduler:
      • Total Energy: {default['total_energy_joules']:.2f} J
      • Total Time: {default['total_time_seconds']:.2f} s
      • Avg Power: {default['average_power_watts']:.2f} W

    Adaptive Scheduler:
      • Total Energy: {adaptive['total_energy_joules']:.2f} J
      • Total Time: {adaptive['total_time_seconds']:.2f} s
      • Avg Power: {adaptive['average_power_watts']:.2f} W

    {'='*40}
    ENERGY SAVINGS: {savings:.2f} J ({savings_pct:.1f}%)
    {'='*40}
    """

    ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes,
             fontsize=11, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.suptitle('Adaptive Scheduler Energy Efficiency Benchmark', fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")


def generate_all_graphs(results_file="/tmp/energy_benchmark_results.json"):
    """Generate all graphs from benchmark results"""
    if not os.path.exists(results_file):
        print(f"Results file not found: {results_file}")
        print("Run energy_benchmark.py first to generate results.")
        return

    with open(results_file, 'r') as f:
        results = json.load(f)

    output_dir = "/tmp/benchmark_graphs"
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nGenerating graphs in: {output_dir}")
    print("-" * 50)

    # Generate all charts
    default = results['default_scheduler']
    adaptive = results['adaptive_scheduler']

    create_energy_comparison_chart(
        default['total_energy_joules'],
        adaptive['total_energy_joules'],
        f"{output_dir}/1_energy_comparison.png"
    )

    # Get final phase metrics for load distribution
    if default['phases'] and adaptive['phases']:
        create_load_distribution_chart(
            default['phases'][-1]['node_metrics'],
            adaptive['phases'][-1]['node_metrics'],
            f"{output_dir}/2_load_distribution.png"
        )

        create_phase_comparison_chart(
            default['phases'],
            adaptive['phases'],
            f"{output_dir}/3_phase_comparison.png"
        )

    create_summary_dashboard(
        results,
        f"{output_dir}/4_benchmark_dashboard.png"
    )

    print("-" * 50)
    print(f"\nAll graphs saved to: {output_dir}")
    print("\nTo view graphs:")
    print(f"  ls {output_dir}")


if __name__ == "__main__":
    generate_all_graphs()
