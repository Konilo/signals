# :mailbox: Signals

Signals is a basic signaling tool which regularly probes some sources of information and sends signals accordingly. 

# Core concepts

**Probing** is carried out by a **probe** which is a python script. 

**Signaling** is implemented via a Telegram chat bot sending messages. 

A probe, accompanied by a certain combination of **probing parameters** and a **schedule** defining the moments when probing and signaling should take place, constitute a **monitoring job** (in reference to cron jobs).

Conceptually, **monitoring** is the conjunction of probing and signaling accordingly. Signaling accordingly can mean not signaling at all.

Monitoring jobs are orchestrated by **GitHub workflows**. Each workflow corresponds to one schedule and contains all the monitoring jobs with the same schedule. 


# Development setup

Clone the repo and start the container used for development ([Docker](https://www.docker.com/) required):
```
git clone git@github.com:Konilo/signals.git
cd signals
make start_dev_container
```

Once inside the container, move to the `/app` directory and install the recommended extensions.

List the probes like so:
```
python /app/signals/main.py --help
```

Get details about a specific probe like so:
```
python /app/signals/main.py sma_crossover --help
Usage: main.py sma_crossover [OPTIONS] TICKER LOOKBACK TRADING_HOURS_OPEN                                                                                                    
                              TRADING_HOURS_CLOSE TIMEZONE                                                                                                                    
                                                                                                                                                                              
 Monitor a ticker for crossovers of its close price and close price SMA                                                                                                       
                                                                                                                                                                              
                                                                                                                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    ticker                   TEXT     Yahoo Finance ticker to probe [default: None] [required]                                                                            │
│ *    lookback                 INTEGER  Lookback window (in days) over which the SMA is computed [default: None] [required]                                                 │
│ *    trading_hours_open       TEXT     Opening hour of the ticker's exchange (HH:MM, ISO 8601, local time) [default: None] [required]                                      │
│ *    trading_hours_close      TEXT     Closing hour of the ticker's exchange (HH:MM, ISO 8601, local time) [default: None] [required]                                      │
│ *    timezone                 TEXT     Timezone of the ticker's exchange (e.g., America/New_York) [default: None] [required]                                               │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --upward-tolerance          FLOAT  Starting from a 'neutral', or 'below' state, the price must exceed 100 + <upward_tolerance>% of the SMA to trigger a signal             │
│                                    [default: 0]                                                                                                                            │
│ --downward-tolerance        FLOAT  Starting from a 'neutral', or 'above' state, the price must fall below 100 - <downward_tolerance>% of the SMA to trigger a signal       │
│                                    [default: 0]                                                                                                                            │
│ --previous-state            TEXT   Last state: 'neutral', 'below', or 'above' [default: neutral]                                                                           │
│ --help                             Show this message and exit.                                                                                                             │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

Find VS Code Run and debug configs under `.vscode/launch.json`.

Manage Python dependencies with [uv](https://docs.astral.sh/uv/getting-started/features/#projects) commands.
