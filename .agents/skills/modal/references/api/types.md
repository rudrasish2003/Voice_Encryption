# types

Public data types returned by Modal APIs.

## AppInfo


Information about a modal App, including its lifecycle and member Functions and Servers.

**Attributes**

<Parameter name="app_id" type="str" description="" />
<Parameter name="description" type="str" description="" />
<Parameter name="lifecycle" type="AppLifecycle" description="" />
<Parameter name="functions" type="dict[str, str]" description="" />
<Parameter name="servers" type="dict[str, str]" description="" />

## AppLifecycle


Timestamps and attributions for events in an App's lifecycle.

Timestamps or attributions may be None when they do not apply to this App
(e.g., App is not deployed, App was not explicitly stopped).

**Attributes**

<Parameter name="state" type="AppState" description="" />
<Parameter name="version" type="int | None" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="created_by" type="str" description="" />
<Parameter name="deployed_at" type="datetime | None" description="" />
<Parameter name="deployed_by" type="str | None" description="" />
<Parameter name="stopped_at" type="datetime | None" description="" />
<Parameter name="stopped_by" type="str | None" description="" />

## AppState


```python
class AppState(str, enum.Enum)
```

An enumeration.

The possible values are:

* `EPHEMERAL`
* `DETACHED`
* `DEPLOYED`
* `STOPPING`
* `STOPPED`
* `INITIALIZING`
* `DISABLED`
## AppStats


App-wide statistics over [since, until), with current Functions and Servers indexed by name.

Lifecycle metadata describes the App when queried, including for historical windows.

**Attributes**

<Parameter name="since" type="datetime" description="" />
<Parameter name="until" type="datetime" description="" />
<Parameter name="functions" type="FunctionStatsGroup" description="">




Totals across current Functions, with individual Function stats keyed by name.

<Parameter name="total" type="AppStats.FunctionCounts" description="" />
<Parameter name="by_name" type="dict[str, AppStats.FunctionStats]" description="" />


#### get

```python
get(self, key, default=None)
```
D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None.

#### keys

```python
keys(self)
```
D.keys() -> a set-like object providing a view on D's keys

#### items

```python
items(self)
```
D.items() -> a set-like object providing a view on D's items

#### values

```python
values(self)
```
D.values() -> an object providing a view on D's values

</Parameter>
<Parameter name="servers" type="ServerStatsGroup" description="">




Totals across current Servers, with individual Server stats keyed by name.

<Parameter name="total" type="AppStats.ServerCounts" description="" />
<Parameter name="by_name" type="dict[str, AppStats.ServerStats]" description="" />


#### get

```python
get(self, key, default=None)
```
D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None.

#### keys

```python
keys(self)
```
D.keys() -> a set-like object providing a view on D's keys

#### items

```python
items(self)
```
D.items() -> a set-like object providing a view on D's items

#### values

```python
values(self)
```
D.values() -> an object providing a view on D's values

</Parameter>
<Parameter name="sandboxes" type="SandboxCounts" description="">




Sandboxes that finished in the window and those that are live as of the until cutoff.

Total is finished + live.

<Parameter name="total" type="int" description="" />
<Parameter name="finished" type="int" description="" />
<Parameter name="live" type="int" description="" />


</Parameter>
<Parameter name="lifecycle" type="AppLifecycle" description="" />
<Parameter name="deployment_count" type="int | None" description="" />

<Collapsible title="CallCounts">

Completed Function inputs; each map item counts separately.

**Attributes**

<Parameter name="total" type="int" description="" />
<Parameter name="succeeded" type="int" description="" />
<Parameter name="failed" type="int" description="" />

</Collapsible>

<Collapsible title="ContainerCounts">

Terminal container errors and distinct containers reporting resource activity in the window.

**Attributes**

<Parameter name="errors" type="int" description="" />
<Parameter name="total" type="int" description="" />

</Collapsible>

<Collapsible title="FunctionCounts">

Function call and container counts.

**Attributes**

<Parameter name="calls" type="AppStats.CallCounts" description="" />
<Parameter name="containers" type="AppStats.ContainerCounts" description="" />

</Collapsible>

<Collapsible title="FunctionStats">

Object ID and counts for a Function.

**Attributes**

<Parameter name="object_id" type="str" description="" />
<Parameter name="counts" type="AppStats.FunctionCounts" description="" />

</Collapsible>

<Collapsible title="RequestCounts">

Server requests split into HTTP 1xx/2xx/3xx and all other outcomes, including status zero.

**Attributes**

<Parameter name="total" type="int" description="" />
<Parameter name="ok" type="int" description="" />
<Parameter name="failed" type="int" description="" />

</Collapsible>

<Collapsible title="ServerCounts">

Server request and container counts.

**Attributes**

<Parameter name="requests" type="AppStats.RequestCounts" description="" />
<Parameter name="containers" type="AppStats.ContainerCounts" description="" />

</Collapsible>

<Collapsible title="ServerStats">

Object ID and counts for a Server.

**Attributes**

<Parameter name="object_id" type="str" description="" />
<Parameter name="counts" type="AppStats.ServerCounts" description="" />

</Collapsible>

## BillingReportItem


Costs generated by a specific object during a specific time interval.

**Attributes**

<Parameter name="object_id" type="str" description="" />
<Parameter name="description" type="str" description="" />
<Parameter name="environment_name" type="str" description="" />
<Parameter name="interval_start" type="datetime" description="" />
<Parameter name="cost" type="Decimal" description="" />
<Parameter name="cost_by_resource" type="dict[str, Decimal]" description="" />
<Parameter name="tags" type="dict[str, str]" description="" />

## CloudBucketMountInfo


**Attributes**

<Parameter name="bucket_name" type="str" description="" />
<Parameter name="bucket_type" type="Literal[&quot;s3&quot;, &quot;r2&quot;, &quot;gcp&quot;]" description="" />
<Parameter name="read_only" type="bool" description="" />
<Parameter name="key_prefix" type="str | None" description="" />

## DictInfo


Information about a Dict object.

**Attributes**

<Parameter name="name" type="str | None" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="created_by" type="str | None" description="" />

## EnvironmentBillingSummary


**Attributes**

<Parameter name="start" type="datetime" description="" />
<Parameter name="end" type="datetime" description="" />
<Parameter name="metered_cost" type="Decimal" description="" />
<Parameter name="metered_cost_breakdown" type="dict[str, Decimal]" description="" />

## FileEntry


A file or directory entry listed from a Modal volume.

**Attributes**

<Parameter name="path" type="str" description="" />
<Parameter name="type" type="FileEntryType" description="" />
<Parameter name="mtime" type="int" description="" />
<Parameter name="size" type="int" description="" />

## FileEntryType


```python
class FileEntryType(enum.IntEnum)
```

Type of a file entry listed from a Modal volume.

The possible values are:

* `UNSPECIFIED`
* `FILE`
* `DIRECTORY`
* `SYMLINK`
* `FIFO`
* `SOCKET`
## FileInfo


Metadata for a file or directory entry in a Sandbox.

**Attributes**

<Parameter name="name" type="str" description="" />
<Parameter name="path" type="str" description="" />
<Parameter name="type" type="FileType" description="" />
<Parameter name="size" type="int" description="" />
<Parameter name="mode" type="int" description="" />
<Parameter name="permissions" type="str" description="" />
<Parameter name="owner" type="str" description="" />
<Parameter name="group" type="str" description="" />
<Parameter name="modified_time" type="float" description="" />
<Parameter name="symlink_target" type="str | None" description="" />


### is_file

```python
is_file(self)
```
Return `True` if this entry is a regular file.

### is_dir

```python
is_dir(self)
```
Return `True` if this entry is a directory.

### is_symlink

```python
is_symlink(self)
```
Return `True` if this entry is a symbolic link.
## FileType


```python
class FileType(enum.Enum)
```

Type of a filesystem entry.

The possible values are:

* `FILE`
* `DIRECTORY`
* `SYMLINK`
## FileWatchEvent


A filesystem change event reported by `Sandbox.filesystem.watch()`.

`paths` contains the absolute path(s) affected by the event. For most
event types it holds a single entry. Rename operations are reported as
`Modify` events: when both the source and destination fall within the
watched scope, `paths` holds `[source, destination]`; when only one
side of the rename is visible, `paths` holds that single path.

**Attributes**

<Parameter name="paths" type="list[str]" description="" />
<Parameter name="type" type="FileWatchEventType" description="" />

## FileWatchEventType


```python
class FileWatchEventType(enum.Enum)
```

Type of a filesystem watch event reported by `Sandbox.filesystem.watch()`.

The possible values are:

* `Unknown`
* `Access`
* `Create`
* `Modify`
* `Remove`
## FunctionAutoscalerSettings


**Attributes**

<Parameter name="min_containers" type="int | None" description="" />
<Parameter name="max_containers" type="int | None" description="" />
<Parameter name="scaledown_window" type="int | None" description="" />
<Parameter name="buffer_containers" type="int | None" description="" />

## FunctionCurrentStats


Simple data structure storing stats for a running function.

**Attributes**

<Parameter name="backlog" type="int" description="" />
<Parameter name="num_total_runners" type="int" description="" />
<Parameter name="num_running_inputs" type="int" description="" />
<Parameter name="input_headroom" type="int" description="" />

## FunctionInfo


A simple data structure containing static info about a Function handle.

**Attributes**

<Parameter name="cpu" type="float | tuple[float, float] | None" description="" />
<Parameter name="memory_mib" type="int | tuple[int, int] | None" description="" />
<Parameter name="gpus" type="list[tuple[str, int]]" description="" />
<Parameter name="ephemeral_disk_mib" type="int | None" description="" />
<Parameter name="image_info" type="ImageInfo" description="">




<Parameter name="image_name" type="str | None" description="" />
<Parameter name="image_id" type="str | None" description="" />


</Parameter>
<Parameter name="startup_timeout" type="int | None" description="" />
<Parameter name="timeout" type="int" description="" />
<Parameter name="max_retries" type="int | None" description="" />
<Parameter name="nonpreemptible" type="bool" description="" />
<Parameter name="regions" type="list[str] | None" description="" />
<Parameter name="routing_region" type="str | None" description="" />
<Parameter name="cloud" type="str | None" description="" />
<Parameter name="cluster_info" type="ClusterInfo | None" description="">




<Parameter name="size" type="int" description="" />
<Parameter name="rdma" type="bool" description="" />
<Parameter name="fabric_size" type="int | None" description="" />


</Parameter>
<Parameter name="batching_info" type="BatchingInfo | None" description="">




<Parameter name="max_batch_size" type="int" description="" />
<Parameter name="wait_ms" type="int" description="" />


</Parameter>
<Parameter name="concurrency_info" type="ConcurrencyInfo | None" description="">




<Parameter name="max_inputs" type="int | None" description="" />
<Parameter name="target_inputs" type="int | None" description="" />


</Parameter>
<Parameter name="schedule" type="str | None" description="" />
<Parameter name="restrict_modal_access" type="bool" description="" />
<Parameter name="block_network" type="bool" description="" />
<Parameter name="single_use_containers" type="bool" description="" />
<Parameter name="volumes" type="dict[str, VolumeMountInfo]" description="" />
<Parameter name="cloud_bucket_mounts" type="dict[str, CloudBucketMountInfo]" description="" />
<Parameter name="secrets" type="list[str]" description="" />
<Parameter name="web_info" type="WebInfo | None" description="">




<Parameter name="web_url" type="str" description="" />
<Parameter name="method" type="str | None" description="" />
<Parameter name="unauthenticated" type="bool" description="" />


</Parameter>
<Parameter name="method_names" type="list[str] | None" description="" />
<Parameter name="method_details" type="dict[str, WebInfo] | None" description="">




<Parameter name="web_url" type="str" description="" />
<Parameter name="method" type="str | None" description="" />
<Parameter name="unauthenticated" type="bool" description="" />


</Parameter>

## FunctionStats


Historical Function statistics for a time range.

**Attributes**

<Parameter name="since" type="datetime" description="" />
<Parameter name="until" type="datetime" description="" />
<Parameter name="input_success_count" type="int" description="" />
<Parameter name="input_failure_count" type="int" description="" />
<Parameter name="input_timeout_count" type="int" description="" />
<Parameter name="input_running_at_end_count" type="int" description="" />
<Parameter name="input_percentile_stats" type="dict[str, StatsPercentileDistribution]" description="" />
<Parameter name="container_started_count" type="int" description="" />
<Parameter name="container_error_count" type="int" description="" />
<Parameter name="container_creating_at_end_count" type="int" description="" />
<Parameter name="container_percentile_stats" type="dict[str, StatsPercentileDistribution]" description="" />
<Parameter name="container_total_count" type="int" description="" />
<Parameter name="variant_count" type="int" description="" />
<Parameter name="all_variants" type="bool" description="" />

## InputInfo


Simple data structure storing information about a function input.

**Attributes**

<Parameter name="input_id" type="str" description="" />
<Parameter name="function_call_id" type="str" description="" />
<Parameter name="task_id" type="str" description="" />
<Parameter name="status" type="InputStatus" description="" />
<Parameter name="function_name" type="str" description="" />
<Parameter name="module_name" type="str" description="" />
<Parameter name="children" type="list[&quot;InputInfo&quot;]" description="" />

## InputStatus


```python
class InputStatus(enum.IntEnum)
```

Enum representing status of a function input.

The possible values are:

* `PENDING`
* `SUCCESS`
* `FAILURE`
* `INIT_FAILURE`
* `TERMINATED`
* `TIMEOUT`
## LogEntry


A log entry queried through a Modal object or App.

The object_id field identifies the object or App whose log manager produced the entry. The context_ids field
contains progressively narrower IDs corresponding to the context in which the log entry was emitted. For example,
for a function log entry, this will contain the function call ID, the input ID, and the container ID.

**Attributes**

<Parameter name="message" type="str" description="" />
<Parameter name="timestamp" type="datetime" description="" />
<Parameter name="source" type="LogSource" description="" />
<Parameter name="object_id" type="str" description="" />
<Parameter name="context_ids" type="list[str]" description="" />

## MemberTokenInfo


**Attributes**

<Parameter name="name" type="str | None" description="" />
<Parameter name="token_id" type="str" description="" />
<Parameter name="user_id" type="str" description="" />
<Parameter name="username" type="str" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="last_used_at" type="datetime | None" description="" />
<Parameter name="expires_at" type="datetime | None" description="" />
<Parameter name="disabled" type="bool" description="" />

## MetricDefinition


The name, unit, and meaning of an individual exportable series.

**Attributes**

<Parameter name="name" type="str" description="" />
<Parameter name="unit" type="str" description="" />
<Parameter name="description" type="str" description="" />

## MetricSeries


An individual metric series with points ordered by time.

**Attributes**

<Parameter name="name" type="str" description="" />
<Parameter name="unit" type="str" description="" />
<Parameter name="aggregation" type="str" description="" />
<Parameter name="points" type="list[TimeSeriesPoint]" description="" />
<Parameter name="description" type="str" defaultValue="&#x27;&#x27;" description="" />

## MetricsSchema


A metrics group and its individual series definitions.

**Attributes**

<Parameter name="name" type="str" description="" />
<Parameter name="definitions" type="list[MetricDefinition]" description="" />

## ObjectMetrics


Exported metrics over the effective, UTC-aligned [since, until) range.

**Attributes**

<Parameter name="object_id" type="str" description="" />
<Parameter name="since" type="datetime" description="" />
<Parameter name="until" type="datetime" description="" />
<Parameter name="bucket_size" type="timedelta" description="" />
<Parameter name="point_count" type="int" description="" />
<Parameter name="series" type="dict[str, MetricSeries]" description="" />

## ProxyTokenInfo


Metadata about a proxy token, not including the token secret.

**Attributes**

<Parameter name="token_id" type="str" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="scoped" type="bool" description="" />
<Parameter name="name" type="str" defaultValue="&#x27;&#x27;" description="" />
<Parameter name="created_by" type="str" defaultValue="&#x27;&#x27;" description="" />

## QueueInfo


Information about a Queue object.

**Attributes**

<Parameter name="name" type="str | None" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="created_by" type="str | None" description="" />

## SandboxConnectCredentials


Simple data structure storing credentials for making HTTP connections to a sandbox.

**Attributes**

<Parameter name="url" type="str" description="" />
<Parameter name="token" type="str" description="" />

## SandboxGroupStats


Statistics for a group of Sandboxes over a time range.

**Attributes**

<Parameter name="tags" type="dict[str, str | None]" description="" />
<Parameter name="cost" type="Decimal" description="" />
<Parameter name="cost_by_resource" type="dict[str, Decimal]" description="" />

## SandboxStats


Statistics for a single Sandbox over a time range.

**Attributes**

<Parameter name="since" type="datetime" description="" />
<Parameter name="until" type="datetime" description="" />
<Parameter name="duration" type="timedelta" description="" />
<Parameter name="percentile_stats" type="dict[str, StatsPercentileDistribution]" description="" />
<Parameter name="cost" type="Decimal | None" description="" />
<Parameter name="cost_by_resource" type="dict[str, Decimal]" description="" />
<Parameter name="billed_cpu_core_seconds" type="float" description="" />
<Parameter name="billed_memory_gib_seconds" type="float" description="" />

## SecretInfo


Information about a Secret object.

**Attributes**

<Parameter name="name" type="str | None" description="" />
<Parameter name="environment_name" type="str" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="created_by" type="str | None" description="" />
<Parameter name="last_used" type="datetime | None" description="" />

## ServerAutoscalerSettings


**Attributes**

<Parameter name="target_concurrency" type="int | float | None" description="" />
<Parameter name="min_containers" type="int | None" description="" />
<Parameter name="max_containers" type="int | None" description="" />
<Parameter name="buffer_containers" type="int | None" description="" />
<Parameter name="scaleup_window" type="int | None" description="" />
<Parameter name="scaledown_window" type="int | None" description="" />

## ServerContainerInfo


Information about a container serving requests for a Server.

**Attributes**

<Parameter name="container_id" type="str" description="" />
<Parameter name="host" type="str" description="" />
<Parameter name="port" type="int" description="" />

## ServerInfo


A simple data structure containing static info about a Server handle.

**Attributes**

<Parameter name="server_url" type="str" description="" />
<Parameter name="port" type="int" description="" />
<Parameter name="unauthenticated" type="bool" description="" />
<Parameter name="h2_enabled" type="bool" description="" />
<Parameter name="routing_region" type="str | None" description="" />
<Parameter name="sessioned" type="bool" description="" />
<Parameter name="startup_timeout" type="int" description="" />
<Parameter name="exit_grace_period" type="int" description="" />
<Parameter name="image_info" type="ImageInfo" description="">




<Parameter name="image_name" type="str | None" description="" />
<Parameter name="image_id" type="str | None" description="" />


</Parameter>
<Parameter name="cpu" type="float | tuple[float, float] | None" description="" />
<Parameter name="memory_mib" type="int | tuple[int, int] | None" description="" />
<Parameter name="gpus" type="list[tuple[str, int]]" description="" />
<Parameter name="ephemeral_disk_mib" type="int | None" description="" />
<Parameter name="nonpreemptible" type="bool" description="" />
<Parameter name="compute_regions" type="list[str] | None" description="" />
<Parameter name="cloud" type="str | None" description="" />
<Parameter name="cluster_info" type="ClusterInfo | None" description="">




<Parameter name="size" type="int" description="" />
<Parameter name="rdma" type="bool" description="" />
<Parameter name="fabric_size" type="int | None" description="" />


</Parameter>
<Parameter name="volumes" type="dict[str, VolumeMountInfo]" description="" />
<Parameter name="cloud_bucket_mounts" type="dict[str, CloudBucketMountInfo]" description="" />
<Parameter name="secrets" type="list[str]" description="" />

## ServerSessionCredentials


Credentials for a sticky session on a Server.

Requests carrying `token` are routed to the same container.

**Attributes**

<Parameter name="session_id" type="str" description="" />
<Parameter name="token" type="str" description="" />

## ServerStats


Historical Server statistics for a time range.

**Attributes**

<Parameter name="since" type="datetime" description="" />
<Parameter name="until" type="datetime" description="" />
<Parameter name="request_count" type="int" description="" />
<Parameter name="request_count_by_status_code" type="dict[int, int]" description="" />
<Parameter name="request_rate_per_second" type="float" description="" />
<Parameter name="request_percentile_stats" type="dict[str, StatsPercentileDistribution]" description="" />
<Parameter name="container_started_count" type="int" description="" />
<Parameter name="container_error_count" type="int" description="" />
<Parameter name="container_creating_at_end_count" type="int" description="" />
<Parameter name="container_total_count" type="int" description="" />
<Parameter name="container_percentile_stats" type="dict[str, StatsPercentileDistribution]" description="" />
<Parameter name="inference" type="InferenceStats | None" description="">




Inference-engine statistics for a Server.

<Parameter name="engine" type="str" description="" />
<Parameter name="status" type="str" description="" />
<Parameter name="percentile_stats" type="dict[str, StatsPercentileDistribution]" description="" />
<Parameter name="scalar_stats" type="dict[str, float]" description="" />


</Parameter>

## ServiceUserInfo


A lightweight dataclass containing metadata about a Modal Service User.

**Attributes**

<Parameter name="service_user_id" type="str" description="" />
<Parameter name="name" type="str" description="" />
<Parameter name="token_id" type="str" description="" />
<Parameter name="created_by" type="str" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="last_used_at" type="datetime | None" description="" />
<Parameter name="expires_at" type="datetime | None" description="" />
<Parameter name="environment_roles" type="dict[str, str]" description="" />

## StatsPercentile


A percentile measurement for a metric or strat.

**Attributes**

<Parameter name="percentile" type="float" description="" />
<Parameter name="value" type="float" description="" />

## StatsPercentileDistribution


**Attributes**

<Parameter name="unit" type="str" description="" />
<Parameter name="percentiles" type="list[StatsPercentile]" description="" />

## TimeSeriesPoint


A metric sample at a UTC bucket start. A missing observation has value None.

**Attributes**

<Parameter name="time" type="datetime" description="" />
<Parameter name="value" type="float | None" description="" />

## TokenData


A token ID / secret pair.

**Attributes**

<Parameter name="token_id" type="str" description="" />
<Parameter name="token_secret" type="str" description="" />

## VolumeCreateOptions


Options used when creating a Volume.

**Attributes**

<Parameter name="experimental_options" type="NotRequired[dict[str, Any]]" description="" />

## VolumeInfo


Information about a Volume object.

**Attributes**

<Parameter name="name" type="str | None" description="" />
<Parameter name="created_at" type="datetime" description="" />
<Parameter name="created_by" type="str | None" description="" />

## VolumeMountInfo


**Attributes**

<Parameter name="name" type="str | None" description="" />
<Parameter name="volume_id" type="str | None" description="" />
<Parameter name="read_only" type="bool" description="" />
<Parameter name="sub_path" type="str | None" description="" />

## WorkspaceBillingSummary


**Attributes**

<Parameter name="start" type="datetime" description="" />
<Parameter name="end" type="datetime" description="" />
<Parameter name="metered_cost" type="Decimal" description="" />
<Parameter name="metered_cost_breakdown" type="dict[str, Decimal]" description="" />
<Parameter name="adjustments" type="dict[str, Decimal]" description="" />
<Parameter name="billed_cost" type="Decimal" description="" />

## WorkspaceMemberInfo


Metadata about a Workspace member.

**Attributes**

<Parameter name="name" type="str" description="" />
<Parameter name="email" type="str" description="" />
<Parameter name="user_id" type="str" description="" />
<Parameter name="role" type="str" description="" />
<Parameter name="joined_at" type="datetime" description="" />
<Parameter name="last_active_at" type="Optional[datetime]" description="" />

## WorkspaceSettings


Current settings for the workspace.

**Attributes**

<Parameter name="default_environment" type="str" description="" />
<Parameter name="image_builder_version" type="str" description="" />

