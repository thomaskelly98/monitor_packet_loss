# Packet Loss Monitor

Monitor broadband connection quality by pinging a target and logging packet loss and latency statistics.

## How to Run
Run the script:
```bash
python3 monitor_packet_loss.py
```

## Command Line Args
Specify a target IP or hostname as an optional argument:
```bash
python3 monitor_packet_loss.py 1.1.1.1
```
If no argument is provided, it will default to `8.8.8.8`.

## Output
When stopped (Ctrl+C), the script prints an overall summary and an hourly breakdown of packet loss, average latency, and jitter. Results are also saved to a timestamped log file.
