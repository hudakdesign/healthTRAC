# Architecture:
## Threads:
### Producer:
  Requests the fsr subsystem at a fixed rate, then parses the responses and
  puts them into a queue.
### Consumer:
  Takes data out of the queue and inserts it into the database. Next, formats
  data for pandas and appends to `incoming_datapoints`. Once the incoming
  datapoints list reaches a certain point, it is aggregated, and pushed to the
  `fsr_data_buffer`.
### Webserver:
  Serves the dashboard with charts displaying aggregate data from `fsr_data_buffer`