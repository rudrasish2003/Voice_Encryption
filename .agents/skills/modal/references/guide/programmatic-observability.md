# Programmatic observability

After deploying an App, you may want to check whether it is receiving traffic,
whether calls are succeeding, or whether GPU containers are still running after
traffic stops.

The CLI and SDKs expose commands for querying configuration, statistics, metrics, call and request history, and
logs. Use these tools to investigate from your terminal
or build your own scripts for observability.

This guide covers five types of commands, each answering a different question:

| Command              | Question                                           |
| -------------------- | -------------------------------------------------- |
| `info`               | What is deployed, and how is it configured?        |
| `stats`              | Is my deployment healthy?                          |
| `metrics`            | How has the deployment behaved over time?          |
| `calls` / `requests` | Which calls or requests did the deployment handle? |
| `logs`               | What happened inside the containers?               |

The examples below use a deployed [App](/docs/sdk/py/latest/App) named `example-app`
with a [Function](/docs/guide/functions) named `func` and a
[Server](/docs/guide/servers) named `Server`. Replace these names with your own.

<Callout>
  SDK support varies by command; each section shows the languages currently supported.
</Callout>

## What is deployed?

Start with `info` to see which Functions and Servers belong to your App:

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal app info example-app
```

{/snippet}
{#snippet python()}

```python notest
app = modal.App.lookup("example-app")
info = app.info()
print(info.lifecycle)
print(info.functions)
print(info.servers)
```

{/snippet}
{#snippet javascript()}

```javascript notest
const app = await modal.apps.fromName("example-app");
const info = await app.info();
console.log(info.lifecycle);
console.log(info.functions);
console.log(info.servers);
```

{/snippet}
{#snippet go()}

```go notest
app, _ := mc.Apps.FromName(ctx, "example-app", nil)
info, _ := app.Info(ctx, nil)
fmt.Printf("%+v\n", info.Lifecycle)
fmt.Println(info.Functions)
fmt.Println(info.Servers)
```

{/snippet} </CodeTabs>

App information includes its Functions and Servers, state, deployment version,
creation and deployment times, and the users who created and deployed it.

Next, inspect an individual Function or Server. The CLI commands accept either
an `APP_NAME/NAME` identifier or the `fu-...` object ID returned by `info`.

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal function info example-app/func
modal server info example-app/Server
```

{/snippet}
{#snippet python()}

```python notest
function = modal.Function.from_name("example-app", "func")
server = modal.Server.from_name("example-app", "Server")
print(function.info())
print(server.info())
```

{/snippet}
{#snippet javascript()}

```javascript notest
const fn = await modal.functions.fromName("example-app", "func");
console.log(await fn.info());
```

{/snippet}
{#snippet go()}

```go notest
fn, _ := mc.Functions.FromName(ctx, "example-app", "func", nil)
info, err := fn.Info(ctx, nil)
if err != nil {
	panic(err)
}
fmt.Printf("%+v\n", info)
```

{/snippet} </CodeTabs>

Function and Server information includes the Modal `Image`, requested hardware resources,
execution settings, autoscaling configuration, and any configured networking settings.

## Is my deployment healthy?

Once you have checked the configuration, use `stats` for a summary of activity
over a time window. The default window is the most recent hour; these examples
use the last 15 minutes:

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal function stats example-app/func --since 15m
modal server stats example-app/Server --since 15m
```

{/snippet}
{#snippet python()}

```python notest
until = datetime.now(timezone.utc)
since = until - timedelta(minutes=15)
function = modal.Function.from_name("example-app", "func")
server = modal.Server.from_name("example-app", "Server")
print(function.stats(since=since, until=until))
print(server.stats(since=since, until=until))
```

{/snippet}
{#snippet javascript()}

```javascript notest
const fn = await modal.functions.fromName("example-app", "func");
const until = new Date();
const since = new Date(until.getTime() - 15 * 60 * 1000);
console.log(await fn.stats({ since, until }));
```

{/snippet}
{#snippet go()}

```go notest
fn, _ := mc.Functions.FromName(ctx, "example-app", "func", nil)
until := time.Now().UTC()
since := until.Add(-15 * time.Minute)
stats, _ := fn.Stats(ctx, &modal.FunctionStatsParams{Since: &since, Until: &until})
fmt.Printf("%+v\n", stats)
```

{/snippet} </CodeTabs>

For Functions, `stats` reports counts of successful, failed, and timed-out inputs,
along with distributions of execution time and end-to-end latency. Use these
statistics to spot increases in errors or slower calls.

The `stats` command also shows how many containers started or errored during the
window, how many were still being created at its end, and distributions of
container startup time. These can help you investigate repeated container
failures or slow startup.

For Servers, `stats` reports the same container statistics, along with request
latency distributions and request counts by HTTP status code. Servers running
supported LLM inference engines, such as SGLang or vLLM, also report inference
metrics such as time to first token.

<Callout>
  Statistics are provided on a best-effort basis and can be delayed or incomplete.
  Give newly generated traffic time to appear. They are intended for investigation and not
  for driving autoscaling decisions.
</Callout>

## How has the deployment behaved over time?

While `stats` summarizes a time window, `metrics` returns time series for a
deployed Function or Server. These show how measurements, such as successful
Function calls or GPU utilization, change within that window. Compare series to
investigate questions such as whether GPUs are under-utilized during traffic spikes.

First, discover the available series and their units:

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal function metrics example-app/func
modal server metrics example-app/Server
```

{/snippet}
{#snippet python()}

```python notest
function = modal.Function.from_name("example-app", "func")
schema = function.metrics.schema()
print(schema)
```

{/snippet}
{#snippet javascript()}

```javascript notest
const fn = await modal.functions.fromName("example-app", "func");
const schema = await fn.metrics.schema();
console.log(schema);
```

{/snippet}
{#snippet go()}

```go notest
fn, _ := mc.Functions.FromName(ctx, "example-app", "func", nil)
schema, err := fn.Metrics.Schema(ctx, nil)
if err != nil {
	panic(err)
}
fmt.Println(schema)
```

{/snippet} </CodeTabs>

The default CLI output lists the available metrics and their units. To export
measurements, select metric groups with `--group` and choose `--json` or `--csv`.
We recommend piping the output of this command to a file, especially when called
in an agent harness, to prevent exhausting the context with raw data.

In the Python and JavaScript SDKs, use `schema()` to discover Function metrics
and `export()` to fetch their measurements. In Go, use `Metrics.Schema()` and
`Metrics.Export()`:

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal function metrics example-app/func \
    --group calls --group containers --group cpu \
    --since 1h --bucket-size 1m --json > function-metrics.json
modal server metrics example-app/Server \
    --group requests --group containers --group gpu \
    --since 1h --bucket-size 1m --csv > server-metrics.csv
```

{/snippet}
{#snippet python()}

```python notest
function = modal.Function.from_name("example-app", "func")
until = datetime.now(timezone.utc)
since = until - timedelta(hours=1)
metrics = function.metrics.export(
    groups=["calls", "containers", "cpu"],
    since=since,
    until=until,
    bucket_size=timedelta(minutes=1),
)

for point in metrics.series["successful_calls_count"].points:
    print(point.time, point.value)

find_spike_in_traffic(metrics.series["succesfull_calls_count"])
```

{/snippet}
{#snippet javascript()}

```javascript notest
const fn = await modal.functions.fromName("example-app", "func");
const until = new Date();
const since = new Date(until.getTime() - 60 * 60 * 1000);
const metrics = await fn.metrics.export({
  groups: ["calls", "containers", "cpu"],
  since,
  until,
  bucketSizeSecs: 60,
});

for (const point of metrics.series["successful_calls_count"].points) {
  console.log(point.time, point.value);
}

findSpikeInTraffic(metrics.series["successful_calls_count"]);
```

{/snippet}
{#snippet go()}

```go notest
fn, _ := mc.Functions.FromName(ctx, "example-app", "func", nil)
until := time.Now().UTC()
since := until.Add(-time.Hour)
bucketSize := time.Minute
metrics, err := fn.Metrics.Export(ctx, &modal.FunctionMetricsExportParams{
	Groups:     []string{"calls", "containers", "cpu"},
	Since:      &since,
	Until:      &until,
	BucketSize: &bucketSize,
})
if err != nil {
	panic(err)
}

for _, point := range metrics.Series["successful_calls_count"].Points {
	if point.Value == nil {
		fmt.Println(point.Time, "missing")
	} else {
		fmt.Println(point.Time, *point.Value)
	}
}

FindSpikeInTraffic(metrics.Series["successful_calls_count"])
```

{/snippet} </CodeTabs>

These examples export the last hour of measurements in one-minute buckets. Each
bucket summarizes measurements from that minute.

SDK results contain a `series` mapping (`Series` in Go) keyed by metric name. Each
series includes its unit, description, and points. A point's `time` is the
bucket's start time, and its `value` is `None` (Python), `null` (JavaScript), or `nil` (Go)
when no observation is available.

## Which calls or requests did the deployment handle?

To investigate individual calls or requests, use `calls` for Functions and
`requests` for Servers:

* `calls` lists Function inputs with their statuses, execution times, and container
  IDs. Add `--show-function-call-id` to include Function call IDs.
* `requests` lists Server HTTP requests with their paths, status codes, and timing
  information.

List the 10 most recent inputs or requests:

```shell
modal function calls example-app/func --tail 10
modal server requests example-app/Server --tail 10
```

To investigate a specific time window, use `--since` and, optionally, `--until`.
Add `--json` to return structured output for use in scripts:

```shell
modal function calls example-app/func --since 15m --json
modal server requests example-app/Server --since 15m --json
```

## What happened inside the containers?

Once you have identified a failure or unexpected behavior, use `logs` to look
for details. Logs contain messages written by your code, exceptions, and system
output. These examples fetch logs from the last 15 minutes:

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal function logs example-app/func --since 15m --timestamps
modal server logs example-app/Server --since 15m --timestamps
```

{/snippet}
{#snippet python()}

```python notest
function = modal.Function.from_name("example-app", "func")
until = datetime.now(timezone.utc)
since = until - timedelta(minutes=15)
for entry in function.logs.fetch(since=since, until=until):
    print(entry.timestamp, entry.source, entry.message)
```

{/snippet}
{#snippet javascript()}

```javascript notest
const fn = await modal.functions.fromName("example-app", "func");
const until = new Date();
const since = new Date(until.getTime() - 15 * 60 * 1000);
for await (const entry of fn.logs.fetch({ since, until })) {
  console.log(entry.timestamp, entry.source, entry.message);
}
```

{/snippet}
{#snippet go()}

```go notest
fn, _ := mc.Functions.FromName(ctx, "example-app", "func", nil)
until := time.Now().UTC()
since := until.Add(-15 * time.Minute)
entries, err := fn.Logs.Fetch(ctx, since, &modal.FunctionLogFetchParams{Until: &until})
if err != nil {
	panic(err)
}
for entry, err := range entries {
	if err != nil {
		panic(err)
	}
	fmt.Println(entry.Timestamp, entry.Source, entry.Message)
}
```

{/snippet} </CodeTabs>

To fetch the most recent logs instead use `--tail` in the CLI
or `logs.tail` (`Logs.Tail`) in Go.
to change the count, or `--since` and `--until` to select a historical interval.

To watch new logs as they arrive, use `--follow` in the CLI or `logs.stream()`
(`Logs.Stream()` in Go). The CLI will follow until explicitly stopped via Ctrl+C;
the SDKs expose a `timeout` parameter.

\<CodeTabs languageOrder={\["cli", "python", "javascript", "go"]}>
{#snippet cli()}

```shell
modal function logs example-app/func --follow --timestamps
```

{/snippet}
{#snippet python()}

```python notest
function = modal.Function.from_name("example-app", "func")
for entry in function.logs.stream():
    print(entry.timestamp, entry.source, entry.message)
```

{/snippet}
{#snippet javascript()}

```javascript notest
const fn = await modal.functions.fromName("example-app", "func");
for await (const entry of fn.logs.stream()) {
  console.log(entry.timestamp, entry.source, entry.message);
}
```

{/snippet}
{#snippet go()}

```go notest
fn, err := mc.Functions.FromName(ctx, "example-app", "func", nil)
if err != nil {
	panic(err)
}
entries, err := fn.Logs.Stream(ctx, nil)
if err != nil {
	panic(err)
}
for entry, err := range entries {
	if err != nil {
		panic(err)
	}
	fmt.Println(entry.Timestamp, entry.Source, entry.Message)
}
```

{/snippet} </CodeTabs>

SDK streams wait indefinitely by default. To stop after a period without new
entries, pass `timeout` (in seconds) in Python, `timeoutMs` in JavaScript, or
`Timeout` in Go's `modal.LogStreamParams`.
Go streams also stop when their context is canceled.

## Putting it together

Monitoring a deployment involves moving from the broad to the specific. For example:

1. List apps in your environment with `modal app list`
2. For a given app, get its `info`
3. For one of its Functions, get its `stats`
4. If something looks off, like many failed function calls, get the recent `calls`
5. Look at the logs for a given call with `logs --function-call-id`

This is just a suggested workflow; the CLI and SDK features have been designed to be
general tools that can be combined to perform arbitrary analyses.
