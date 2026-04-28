# gensbp

sing-box configuration generator - automatically generate sing-box config from subscription URLs

### Installation

```bash
# Clone the project
git clone <repo-url>
cd gensbp

# Install with uv (recommended)
uv venv
uv pip install -e .

# Or with pip
pip install -e .
```

### Configuration Files

Create the following files in `~/.config/gensbp/`:

#### config.json
Main configuration file with default values:

```json
{
  "node_url": "https://your-subscription-url",
  "template": "template.json",
  "outbound_presets": "outbound-presets.json",
  "outbound_rules": "outbound-rules.json",
  "dial_fields": "dial-fields.json"
}
```

#### template.json
Base sing-box configuration template:

```json
{
  "log": { "level": "info" },
  "dns": { ... },
  "inbounds": [ ... ],
  "outbounds": []
}
```

#### outbound-presets.json
Preset outbound configurations (e.g., direct, block):

```json
[
  {
    "tag": "direct",
    "type": "direct"
  },
  {
    "tag": "block",
    "type": "block"
  }
]
```

#### outbound-rules.json
Node grouping rules:

```json
{
  "selector_groups": {
    "🇭🇰 Hong Kong": {
      "filter": "香港|HK|Hong Kong",
      "preserve_order": true
    }
  },
  "urltest_groups": {
    "⚡ Auto": {
      "filter": ".*"
    }
  }
}
```

- `filter`: Regex pattern to match node tags
- `preserve_order`: Keep original order from template

#### dial-fields.json (Optional)
Additional dial fields for all nodes:

```json
{
  "tcp_fast_open": true,
  "tcp_multi_path": true
}
```

#### extra-nodes.json (Optional)
Manually added extra nodes:

```json
[
  {
    "tag": "Backup",
    "type": "vmess",
    "server": "example.com",
    "server_port": 443
  }
]
```

### Patch System

Patch files use `/` separated path prefix syntax to modify configurations:

```json
{
  // Overwrite value
  "/log/level": "debug",

  // Merge value (dict merge, list concat)
  "+/dns/servers": [
    {
      "tag": "dns-local",
      "address": "local"
    }
  ],

  // Delete key
  "-/experimental": null,

  // Replace entire config
  "/": { ... },

  // Wildcard operations - batch modify all elements in lists or dicts
  "-/outbounds/*/domain_resolver": null,   // Delete domain_resolver from all outbounds
  "/servers/*/enabled": true,              // Set enabled to true for all servers
  "/groups/*/nodes/*/priority": 10,        // Nested wildcards

  // Condition definition - match all outbounds with type "anytls"
  "#cond/has_anytls/outbounds/*/type": "anytls",

  // Conditional operation - if condition matches, delete the matched outbounds
  // (.. backtracks 1 level, i.e. the outbound itself)
  "-/#if/has_anytls/..": null,

  // Conditional operation - if condition matches, modify the matched outbound's transport
  "#if/has_anytls/../transport/type": "http"
}
```

**Patch Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `/path` | Overwrite value | `"/log/level": "debug"` |
| `+/path` | Merge value (dict merge, list concat) | `"+/outbounds": [...]` |
| `-/path` | Delete key | `"-/experimental": null` |
| `/` | Replace entire config | `"/": {...}` |
| `+/` | Merge entire config | `"+/": {...}` |

**Keywords:**

| Keyword | Description | Example |
|---------|-------------|---------|
| `#cond/name/path` | Define condition `name` that matches nodes at path whose value equals the patch value | `"#cond/has_anytls/outbounds/*/type": "anytls"` |
| `#if/name/path` | If condition `name` has matches, apply operation at the given path relative to each match | `"-/#if/has_anytls/..": null` |

**Relative Paths `..`:**

`..` backtracks from the condition match position. n dots = backtrack n-1 levels:

| Path | Description |
|------|-------------|
| `..` | Backtrack 1 level (parent of matched node) |
| `...` | Backtrack 2 levels |
| `../other` | Backtrack 1 level, then descend into `other` |

**Wildcard `*` Support:**

Wildcard `*` can be used in paths to match all elements at the current level (each element in a list or each value in a dict). Supports nested wildcards.

| Pattern | Description |
|------|------|
| `/path/to/list/*/key` | Set `key` field for each element in the list |
| `-/path/to/dict/*/key` | Delete `key` field from each value in the dict |
| `/path/*/subpath/*/field` | Nested wildcards, matches multi-level structures |

**Notes:**
- Wildcards only operate on dict or list elements
- For lists, wildcard iterates all elements (only processes dict-type elements)
- For dicts, wildcard iterates all values (only processes dict-type values)
- Append operations `+` also support wildcards (e.g., `+/list/*/tags`)
- Conditions `#cond` and `#if` are processed in definition order; `#if` always evaluates against the current config state

### Usage

```bash
# Run directly
python main.py -o output.json

# Override config with CLI
python main.py -o output.json -n <subscription-url>

# Specify template
python main.py -o output.json -t custom-template.json

# Using patches
python main.py -o output.json -p patch.json

# Multiple patches (applied in order)
python main.py -o output.json -p patch1.json -p patch2.json

# Add extra nodes
python main.py -o output.json --extra extra-nodes.json

# Bypass cache
python main.py -o output.json --no-cache
```

### Command Line Arguments

| Argument | Short | Description | Required |
|----------|-------|-------------|----------|
| `--output` | `-o` | Output file path | ✅ |
| `--template` | `-t` | Template file path | ❌ |
| `--node-url` | `-n` | Subscription URL | ❌ |
| `--patch` | `-p` | Patch files (multiple) | ❌ |
| `--extra` | `-e` | Extra nodes file | ❌ |
| `--outbound-presets` | | Outbound presets file | ❌ |
| `--outbound-rules` | | Outbound rules file | ❌ |
| `--no-cache` | | Bypass cache | ❌ |

### Node Grouping Mechanism

1. **Filter by Rules** - Match node tags using regex patterns
2. **Auto Create Extra Groups** - Extra nodes go into "➕ 附加" group
3. **Clean Empty Groups** - Auto-remove groups with no matching nodes
4. **Cascade Cleanup** - If a group is deleted, references are updated
5. **Auto-Set Default Node** - For selectors without an explicit `default` configuration, automatically tests TCP connection latency of leaf node children to proxy servers and sets the node with the lowest latency as `default`. If all tests fail, `default` remains unset.

### Caching

- **Cache Directory**: `~/.cache/gensbp/`
- **Cache Duration**: 6 hours
- **Cache Key**: MD5 hash of subscription URL

### Project Structure

```
gensbp/
├── main.py              # Entry point
├── src/
│   ├── cli.py           # CLI implementation
│   ├── config/          # Configuration module
│   ├── core/            # Core functionality
│   └── utils/           # Utility functions
├── pyproject.toml       # Project config
└── README.md
```

### License

MIT
