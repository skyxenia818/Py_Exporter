def read_meminfo():
    """
    Read and parse /proc/meminfo file
    Returns a dictionary of memory metrics
    """
    meminfo = {}
    with open(PROC_MEMINFO_PATH, 'r') as f:
        for line in f:
            # Parse lines like "MemTotal:        8167848 kB"
            match = re.match(r'([^:]+):\s*(\d+)\s*(\S+)?', line)
            if match:
                key, value, unit = match.groups()
                # Convert to bytes if unit is kB
                if unit == 'kB':
                    value = int(value) * 1024
                else:
                    value = int(value)
                
                # Convert key to Prometheus format (snake_case with bytes suffix)
                prom_key = key.replace('(', '').replace(')', '')
                if unit == 'kB' or key in ['HugePages_Total', 'HugePages_Free', 'HugePages_Rsvd', 'HugePages_Surp']:
                    # For kB values, add _bytes suffix
                    if not prom_key.endswith('_bytes') and not prom_key.startswith('HugePages_'):
                        prom_key += '_bytes'
                
                meminfo[prom_key] = value
    return meminfo