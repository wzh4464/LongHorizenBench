# T18: Vitess Viper Configuration Framework

*Upstream reference:* Vitess issue #11788 ("Standardize on a single configuration framework"). Specification inlined; the agent must not reach the network.

## 1. Motivation

Every Vitess binary (`vtgate`, `vttablet`, `vtctld`, `vtbackup`, ...) currently declares command-line flags directly against Go's `pflag`. Configuration is duplicated across binaries, environment variable support is inconsistent, and there is no single mechanism to load values from configuration files or to re-resolve dynamic values at runtime. The goal is to introduce a Vitess-wide configuration framework, built on top of the `spf13/viper` library, that satisfies the following:

- One place to register a configuration option, with a description, a typed default value, an associated flag name (where applicable), and zero or more environment-variable aliases.
- Multiple input sources resolved with a documented precedence (CLI flag > env var > config file > registered default).
- A clear notion of *static* (resolved once at startup) vs *dynamic* (re-resolved on each access, with file-watch reload) options.
- A typed accessor API so that callers do not deal with raw `viper` `Get` calls and string keys.
- Backwards compatibility: existing flags must continue to work; existing environment-variable conventions must continue to work.

## 2. Concepts

### 2.1 `Value[T]`

A generic `Value[T]` interface with a `Get() T` accessor. The framework provides constructors for primitive types (`string`, `bool`, `int`, `int64`, `float64`, `time.Duration`) and slice variants, plus an extension point so call sites can provide custom decoders for non-trivial types.

### 2.2 Static vs dynamic values

- **Static** values are resolved once at startup (after `LoadConfig`). `Get()` returns the cached value with no further locking on the hot path.
- **Dynamic** values re-read from the underlying source on every `Get()` and respond to config-file change events. Dynamic reads pay a small synchronization cost.

### 2.3 Precedence

Values are resolved in the following order, first match wins:
1. Explicit override (programmatic `Set`).
2. Command-line flag.
3. Environment variable.
4. Config file entry (if any).
5. Default supplied at registration time.

### 2.4 Registration

Each call site registers the value during package init or at startup, supplying:
- a unique key (used for config files and env-var derivation);
- the default value (typed);
- optional aliases / deprecated names;
- whether the option is dynamic.

The framework keeps a registry of all options so that:
- `--help` for each binary lists the configurable options with their defaults;
- a debug HTTP handler can dump the current resolved values;
- a config-file template can be auto-generated.

## 3. Implementation Items

1. A new package implementing the registry, value types (static / dynamic), and the precedence rules described above.
2. Generic helpers (`Configure[T]`) that wrap the underlying `viper` instance and return a typed `Value[T]`.
3. A registration mechanism so every binary in the Vitess tree can opt in incrementally (existing flags continue to work).
4. Watch / reload plumbing for dynamic values, with the thread-safety guarantees that callers can read concurrently.
5. A debug HTTP handler (e.g. `/debug/config`) that lists all registered options, their current effective value, and the source (default / flag / env / file).
6. Migration of one or more representative call-sites to the new framework, showing the pattern.
7. Tests covering: precedence order, dynamic reload, type coverage (string / bool / numeric / duration / slices), and registration uniqueness.