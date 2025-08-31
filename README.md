# :mailbox: Signals

Signals is a basic signaling tool which regularly probes some sources of information and sends signals accordingly. 

# Core concepts

**Probing** is carried out by a **probe** which is a python script. 

**Signaling** is implemented via a Telegram chat bot sending messages. 

A probe, accompanied by a certain combination of **probing parameters** and a **schedule** defining the moments when probing and signaling should take place, constitute a **monitoring job** (in reference to cron jobs).

Conceptually, **monitoring** is the conjunction of probing and signaling accordingly. Signaling accordingly can mean not signaling at all.

Monitoring jobs are orchestrated by **GitHub workflows**. Each workflow corresponds to one schedule and contains all the monitoring jobs with the same schedule. 
