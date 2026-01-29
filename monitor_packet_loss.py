#!/usr/bin/env python3
"""
Simple packet loss monitor for broadband connection.
Pings 8.8.8.8 and logs results with packet loss statistics.
"""

import subprocess
import re
from datetime import datetime
import signal
import sys
import statistics
from collections import defaultdict

class PacketLossMonitor:
    def __init__(self, target="8.8.8.8"):
        self.target = target
        self.packets_sent = 0
        self.packets_received = 0
        self.window_sent = 0  # Packets sent in current 100-packet window
        self.window_received = 0  # Packets received in current 100-packet window

        # Latency tracking
        self.latencies = []  # All latencies for overall average
        self.window_latencies = []  # Latencies for current 100-packet window
        self.min_latency = None
        self.max_latency = None
        self.max_window_loss_pct = 0.0  # Worst packet loss in any 100-packet window

        # Hourly statistics tracking
        self.hourly_stats = defaultdict(lambda: {
            'sent': 0,
            'received': 0,
            'latencies': []
        })

        self.log_filename = f"ping_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.target.replace('.', '_')}.txt"
        self.log_file = None

    def calculate_loss_percentage(self):
        if self.packets_sent == 0:
            return 0.0
        return ((self.packets_sent - self.packets_received) / self.packets_sent) * 100

    def print_summary(self):
        loss_pct = self.calculate_loss_percentage()
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        jitter = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0

        summary = f"\n{'='*60}\nOVERALL SUMMARY\n{'='*60}\n"
        summary += f"Total packets sent: {self.packets_sent}\n"
        summary += f"Total packets received: {self.packets_received}\n"
        summary += f"Packet loss: {loss_pct:.2f}%\n"
        summary += f"Max packet loss (In any 100 packet window): {self.max_window_loss_pct:.2f}%\n"
        summary += f"\nLatency statistics:\n"
        summary += f"  Average: {avg_latency:.2f} ms\n"
        summary += f"  Minimum: {self.min_latency:.2f} ms\n" if self.min_latency is not None else "  Minimum: N/A\n"
        summary += f"  Maximum: {self.max_latency:.2f} ms\n" if self.max_latency is not None else "  Maximum: N/A\n"
        summary += f"  Jitter (stdev): {jitter:.2f} ms\n"

        # Hourly breakdown
        if self.hourly_stats:
            summary += f"\n{'='*60}\nHOURLY BREAKDOWN\n{'='*60}\n"
            for hour in sorted(self.hourly_stats.keys()):
                stats = self.hourly_stats[hour]
                sent = stats['sent']
                received = stats['received']
                loss = ((sent - received) / sent * 100) if sent > 0 else 0
                avg_lat = sum(stats['latencies']) / len(stats['latencies']) if stats['latencies'] else 0
                hour_jitter = statistics.stdev(stats['latencies']) if len(stats['latencies']) > 1 else 0

                summary += f"\n{hour}\n"
                summary += f"  Packets: {received}/{sent} received (loss: {loss:.2f}%)\n"
                summary += f"  Latency: {avg_lat:.2f} ms avg, {hour_jitter:.2f} ms jitter\n"

        summary += f"\n{'='*60}\n"
        summary += f"Log file: {self.log_filename}\n"
        summary += f"{'='*60}\n"
        print(summary)
        if self.log_file:
            self.log_file.write(summary)
            self.log_file.flush()

    def log(self, message):
        """Write to both console and file."""
        print(message)
        if self.log_file:
            self.log_file.write(message + "\n")
            self.log_file.flush()

    def run(self):
        # Set up signal handler for clean exit
        def signal_handler(sig, frame):
            self.print_summary()
            if self.log_file:
                self.log_file.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Open log file
        self.log_file = open(self.log_filename, 'w')

        # Log header
        header = f"Packet Loss Monitor - Started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.log(f"{'='*60}")
        self.log(header)
        self.log(f"Target: {self.target}")
        self.log(f"{'='*60}\n")

        # Start ping process
        ping_process = subprocess.Popen(
            ['ping', self.target],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        try:
            for line in ping_process.stdout:
                line = line.strip()
                if not line:
                    continue

                now = datetime.now()
                timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
                hour_key = now.strftime('%Y-%m-%d %H:00')  # Group by hour
                log_line = f"{timestamp} - {line}"
                self.log(log_line)

                # Count packets and extract latency
                if 'icmp_seq' in line or 'icmp_seq=' in line:
                    self.packets_sent += 1
                    self.window_sent += 1
                    self.hourly_stats[hour_key]['sent'] += 1

                    if 'time=' in line or 'time =' in line:
                        self.packets_received += 1
                        self.window_received += 1
                        self.hourly_stats[hour_key]['received'] += 1

                        # Extract latency
                        time_match = re.search(r'time[=\s]+(\d+\.?\d*)\s*ms', line)
                        if time_match:
                            latency = float(time_match.group(1))
                            self.latencies.append(latency)
                            self.window_latencies.append(latency)
                            self.hourly_stats[hour_key]['latencies'].append(latency)

                            # Track min/max
                            if self.min_latency is None or latency < self.min_latency:
                                self.min_latency = latency
                            if self.max_latency is None or latency > self.max_latency:
                                self.max_latency = latency

                elif 'Request timeout' in line or 'timeout' in line.lower():
                    self.packets_sent += 1
                    self.window_sent += 1
                    self.hourly_stats[hour_key]['sent'] += 1

                # Print periodic summary (every 100 packets)
                if self.packets_sent > 0 and self.packets_sent % 100 == 0:
                    window_loss_pct = ((self.window_sent - self.window_received) / self.window_sent) * 100 if self.window_sent > 0 else 0
                    window_lost = self.window_sent - self.window_received
                    if window_loss_pct > self.max_window_loss_pct:
                        self.max_window_loss_pct = window_loss_pct
                    window_avg_latency = sum(self.window_latencies) / len(self.window_latencies) if self.window_latencies else 0
                    window_jitter = statistics.stdev(self.window_latencies) if len(self.window_latencies) > 1 else 0

                    stats = f"\n--- Statistics for packets {self.packets_sent - 99} to {self.packets_sent} ---"
                    stats += f"\nPacket loss: {window_loss_pct:.2f}% ({window_lost}/{self.window_sent} lost)"
                    stats += f"\nAverage latency: {window_avg_latency:.2f} ms"
                    stats += f"\nJitter (stdev): {window_jitter:.2f} ms\n"
                    self.log(stats)

                    # Reset window counters
                    self.window_sent = 0
                    self.window_received = 0
                    self.window_latencies = []

        except Exception as e:
            self.log(f"\nError: {e}")
        finally:
            ping_process.terminate()
            self.print_summary()
            if self.log_file:
                self.log_file.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "8.8.8.8"
    monitor = PacketLossMonitor(target=target)
    print(f"Starting packet loss monitor... (Press Ctrl+C to stop)")
    print(f"Target: {target}")
    print(f"Logging to: {monitor.log_filename}\n")
    monitor.run()
