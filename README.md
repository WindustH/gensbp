# gensbp

sing-box 配置自动生成器 - 从订阅链接自动生成 sing-box 配置文件

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd gensbp

# 使用 uv 安装（推荐）
uv venv
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 配置文件

在 `~/.config/gensbp/` 目录下创建以下文件：

#### config.json
主配置文件，定义默认值：

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
sing-box 基础配置模板：

```json
{
  "log": { "level": "info" },
  "dns": { ... },
  "inbounds": [ ... ],
  "outbounds": []
}
```

#### outbound-presets.json
预设出站配置（如直连、拦截等）：

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
节点分组规则：

```json
{
  "selector_groups": {
    "🇭🇰 香港节点": {
      "filter": "香港|HK|Hong Kong",
      "preserve_order": true
    }
  },
  "urltest_groups": {
    "⚡ 自动选择": {
      "filter": ".*"
    }
  }
}
```

- `filter`: 正则表达式，匹配节点标签
- `preserve_order`: 是否保留模板中的原有顺序

#### dial-fields.json（可选）
为所有节点添加额外的拨号字段：

```json
{
  "tcp_fast_open": true,
  "tcp_multi_path": true
}
```

#### extra-nodes.json（可选）
手动添加的额外节点：

```json
[
  {
    "tag": "备用节点",
    "type": "vmess",
    "server": "example.com",
    "server_port": 443
  }
]
```

### 补丁系统

补丁文件使用 `::` 前缀语法修改配置：

```json
{
  // 覆盖值
  "::log::level": "debug",

  // 合并值
  "::dns+": {
    "servers": [
      {
        "tag": "dns-local",
        "address": "local"
      }
    ]
  },

  // 删除键
  "x::experimental": null,

  // 替换整个配置
  "::": { ... }
}
```

**补丁操作符：**

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `::key` | 覆盖值 | `"::log::level": "debug"` |
| `::key+` | 合并值（dict 合并，list 拼接） | `"::outbounds+": [...]` |
| `x::key` | 删除键 | `"x::experimental": null` |
| `::` | 替换整个配置 | `"::": {...}` |
| `::+` | 合并整个配置 | `"::+": {...}` |

### 使用方法

```bash
# 直接运行
python main.py -o output.json

# 命令行覆盖配置
python main.py -o output.json -n <订阅链接>

# 指定模板
python main.py -o output.json -t custom-template.json

# 使用补丁
python main.py -o output.json -p patch.json

# 多个补丁（按顺序应用）
python main.py -o output.json -p patch1.json -p patch2.json

# 添加额外节点
python main.py -o output.json --extra extra-nodes.json

# 绕过缓存
python main.py -o output.json --no-cache
```

### 命令行参数

| 参数 | 简写 | 说明 | 必需 |
|------|------|------|------|
| `--output` | `-o` | 输出文件路径 | ✅ |
| `--template` | `-t` | 模板文件路径 | ❌ |
| `--node-url` | `-n` | 订阅链接 | ❌ |
| `--patch` | `-p` | 补丁文件（可多个） | ❌ |
| `--extra` | `-e` | 额外节点文件 | ❌ |
| `--outbound-presets` | | 预设出站文件 | ❌ |
| `--outbound-rules` | | 出站规则文件 | ❌ |
| `--no-cache` | | 绕过缓存 | ❌ |

### 节点分组机制

1. **按规则过滤** - 使用正则表达式匹配节点标签
2. **自动创建额外组** - 额外节点会被放入 "➕ 附加" 组
3. **清理空组** - 自动删除没有匹配节点的空组
4. **级联清理** - 如果某个组被删除，引用它的组也会更新

### 缓存机制

- **缓存目录**: `~/.cache/gensbp/`
- **缓存时间**: 6 小时
- **缓存键**: 订阅链接的 MD5 哈希

### 项目结构

```
gensbp/
├── main.py              # 入口文件
├── src/
│   ├── cli.py           # CLI 实现
│   ├── config/          # 配置模块
│   ├── core/            # 核心功能
│   └── utils/           # 工具函数
├── pyproject.toml       # 项目配置
└── README.md
```

### License

MIT
