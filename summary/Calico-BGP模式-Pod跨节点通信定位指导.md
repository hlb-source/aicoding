# Calico BGP 模式 Pod 间跨节点通信路由转发指导

## 1. Calico BGP 模式概述

Calico BGP 模式通过 BGP 协议在集群中分发路由信息，实现 Pod 间的跨节点通信。该模式下，数据包直接通过三层路由转发，无需任何封装。

### 1.1 核心特性

| 特性 | 说明 |
|------|------|
| 路由协议 | BGP (Bird) |
| 封装方式 | 无封装 |
| 数据包格式 | 标准 IP 数据包 |
| 性能 | 高（无封装开销） |
| 依赖 | 节点间三层互通 |

## 2. 报文转发整体流程

### 2.1 数据包转发路径图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Calico BGP 模式跨节点通信报文转发流程                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Pod A (192.168.1.10)                                                 │
│       │                                                                 │
│       │ ① 数据包: Src=192.168.1.10, Dst=192.168.2.10                │
│       ▼                                                                 │
│  veth pair (calixxx)                                                  │
│       │                                                                 │
│       │ ② 数据包到达主机网络命名空间                                     │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐      │
│  │                    Node1 路由表查找                          │      │
│  │  192.168.2.0/26 via 10.0.0.2 dev eth0 proto bird        │      │
│  │  → 匹配到 192.168.2.0/26 网段，下一跳是 Node2 IP        │      │
│  └─────────────────────────────────────────────────────────────┘      │
│       │                                                                 │
│       │ ③ 直接路由: Src=192.168.1.10, Dst=192.168.2.10           │
│       ▼                                                                 │
│  eth0 (物理网卡)                                                        │
│       │                                                                 │
│       │ ④ 通过物理网络交换机三层转发到 Node2                        │
│       ▼                                                                 │
│  eth0 (Node2 物理网卡)                                                  │
│       │                                                                 │
│       │ ⑤ 数据包: Src=192.168.1.10, Dst=192.168.2.10              │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐      │
│  │                    Node2 路由表查找                          │      │
│  │  192.168.2.0/26 dev cali0 proto kernel scope link       │      │
│  │  → 匹配到本地网段，直接交付给 veth pair                      │      │
│  └─────────────────────────────────────────────────────────────┘      │
│       │                                                                 │
│       │ ⑥ 数据包到达 veth pair                                       │
│       ▼                                                                 │
│  Pod B (192.168.2.10)                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. 详细路由表分析

### 3.1 Node1 路由表

```bash
# 查看 Node1 的路由表
ip route

# 输出示例：
default via 10.0.0.1 dev eth0 proto dhcp src 10.0.0.10 metric 100
10.0.0.0/24 dev eth0 proto kernel scope link src 10.0.0.10
192.168.1.0/26 dev cali0 proto kernel scope link src 192.168.1.1
192.168.2.0/26 via 10.0.0.2 dev eth0 proto bird onlink
192.168.3.0/26 via 10.0.0.3 dev eth0 proto bird onlink
```

| 路由条目 | 含义 | 动作 |
|---------|------|------|
| `default via 10.0.0.1` | 默认路由 | 匹配其他所有流量 |
| `10.0.0.0/24 dev eth0` | 本机网络段 | 本地链路直接交付 |
| `192.168.1.0/26 dev cali0` | 本节点 Pod 网段 | 直接通过 cali0 设备交付 |
| `192.168.2.0/26 via 10.0.0.2` | Node2 Pod 网段 | 通过 eth0 发送到 Node2 |
| `192.168.3.0/26 via 10.0.0.3` | Node3 Pod 网段 | 通过 eth0 发送到 Node3 |

### 3.2 Node2 路由表

```bash
# 查看 Node2 的路由表
ip route

# 输出示例：
default via 10.0.0.1 dev eth0 proto dhcp src 10.0.0.20 metric 100
10.0.0.0/24 dev eth0 proto kernel scope link src 10.0.0.20
192.168.1.0/26 via 10.0.0.10 dev eth0 proto bird onlink
192.168.2.0/26 dev cali0 proto kernel scope link src 192.168.2.1
192.168.3.0/26 via 10.0.0.30 dev eth0 proto bird onlink
```

| 路由条目 | 含义 | 动作 |
|---------|------|------|
| `192.168.1.0/26 via 10.0.0.10` | Node1 Pod 网段 | 通过 eth0 发送到 Node1 |
| `192.168.2.0/26 dev cali0` | 本节点 Pod 网段 | 直接通过 cali0 设备交付 |
| `192.168.3.0/26 via 10.0.0.30` | Node3 Pod 网段 | 通过 eth0 发送到 Node3 |

### 3.3 路由条目字段解析

```bash
# 路由条目格式解析
192.168.2.0/26 via 10.0.0.2 dev eth0 proto bird onlink

# 字段说明：
192.168.2.0/26    : 目标网络（目标 Pod 所在网段）
via 10.0.0.2      : 下一跳 IP 地址（目标节点的物理 IP）
dev eth0           : 出接口（发送到哪个网卡）
proto bird         : 路由协议（bird = BGP 分发的路由）
onlink            : 标志（表示下一跳强制在指定接口上可达）
```

## 4. 报文转发详细步骤

### 4.1 Pod A 发送到 Pod B 的完整过程

#### 步骤 1：Pod A 发出数据包

```
位置：Pod A 内部
数据包：
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
├─────────────────────────────────┤
│ TCP/UDP 头                      │
└─────────────────────────────────┘
```

**动作**：Pod A 根据自己的路由表发送数据包

```bash
# Pod A 内部的路由表
ip route

# 输出：
default via 192.168.1.1 dev eth0
192.168.1.0/26 dev eth0 proto kernel scope link src 192.168.1.10
```

**分析**：
- 目标 192.168.2.10 不匹配本地网段 192.168.1.0/26
- 匹配默认路由，下一跳是 192.168.1.1
- 数据包通过 veth pair 发送到主机侧

#### 步骤 2：数据包到达 veth pair

```
位置：veth pair (calixxx)
数据包：
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
└─────────────────────────────────┘
```

**动作**：数据包通过 veth pair 到达主机网络命名空间

#### 步骤 3：Node1 路由表查找

```
位置：Node1 主机网络命名空间
执行命令：ip route get 192.168.2.10
输出：192.168.2.10 via 10.0.0.2 dev eth0 src 10.0.0.10
```

**查找过程**：

1. **查询路由表**：`ip route get 192.168.2.10`
2. **匹配目标网络**：`192.168.2.10` 匹配 `192.168.2.0/26`
3. **确定下一跳**：`via 10.0.0.2`（Node2 的物理 IP）
4. **确定出接口**：`dev eth0`（物理网卡）

**路由决策**：
```
匹配路由：192.168.2.0/26 via 10.0.0.2 dev eth0 proto bird onlink
下一跳 IP：10.0.0.2 (Node2)
出接口：eth0
```

#### 步骤 4：ARP 解析获取 MAC 地址

```
位置：Node1 ARP 表
执行命令：ip neigh show 10.0.0.2
```

**首次通信时**：
1. 检查 ARP 缓存中是否有 10.0.0.2 的 MAC 地址
2. 如果没有，发送 ARP 请求获取
3. 将 MAC 地址存入 ARP 缓存

```bash
# 查看 ARP 缓存
ip neigh show

# 示例输出：
10.0.0.2 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
```

**数据包封装**：
```
┌─────────────────────────────────────────┐
│ Ethernet 头                              │
│   Source MAC: aa:bb:cc:dd:ee:11 (Node1)│
│   Destination MAC: aa:bb:cc:dd:ee:ff    │
├─────────────────────────────────────────┤
│ IP 头                                    │
│   Source IP: 192.168.1.10              │
│   Destination IP: 192.168.2.10          │
├─────────────────────────────────────────┤
│ TCP/UDP 头                              │
└─────────────────────────────────────────┘
```

#### 步骤 5：通过物理网络传输

```
位置：物理网络交换机
传输路径：
┌─────────┐      ┌─────────┐      ┌─────────┐
│ Node1   │ ──── │ Switch  │ ──── │ Node2   │
│ eth0    │      │ (L3)   │      │ eth0    │
└─────────┘      └─────────┘      └─────────┘
   10.0.0.10                   10.0.0.20
```

> **备注**：如果家里测试环境没有 L3 Switch，两个节点处于同一二层网络（通过普通交换机或直连），数据包会通过二层交换机转发，无需三层路由。此时交换机只做 MAC 地址学习，不修改 IP 报文。

**数据包**：
```
┌─────────────────────────────────────────┐
│ Ethernet 头                              │
│   Source MAC: aa:bb:cc:dd:ee:11       │
│   Destination MAC: aa:bb:cc:dd:ee:ff    │
├─────────────────────────────────────────┤
│ IP 头                                    │
│   Source IP: 192.168.1.10              │
│   Destination IP: 192.168.2.10          │
└─────────────────────────────────────────┘
```

**注意**：数据包直接使用原始 IP 地址，无任何封装

#### 步骤 6：Node2 接收数据包

```
位置：Node2 网络栈
执行命令：tcpdump -i eth0 -n
```

**接收过程**：
1. 网卡 eth0 收到数据包
2. 识别目标 MAC 是本机
3. 识别目标 IP 是 192.168.2.10（不是本机 eth0 的 IP 10.0.0.20）
4. 触发本地路由表查找

#### 步骤 7：Node2 路由表查找

```
位置：Node2 主机网络命名空间
执行命令：ip route get 192.168.2.10
输出：192.168.2.10 dev cali0 src 192.168.2.1
```

**查找过程**：

1. **查询路由表**：`ip route get 192.168.2.10`
2. **匹配本地网段**：`192.168.2.10` 匹配本地网段 `192.168.2.0/26`
3. **确定出接口**：`dev cali0`（Pod 网络接口）
4. **确定交付方式**：`scope link`（本地链路直接交付）

**路由决策**：
```
匹配路由：192.168.2.0/26 dev cali0 proto kernel scope link
出接口：cali0
交付方式：直接交付（无需路由到其他设备）
```

#### 步骤 8：通过 veth pair 到达 Pod B

```
位置：veth pair (caliyyy)
数据包：
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
└─────────────────────────────────┘
```

**动作**：数据包通过 veth pair 进入 Pod B

#### 步骤 9：Pod B 接收数据包

```
位置：Pod B 内部
数据包：
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
└─────────────────────────────────┘
```

**动作**：Pod B 的应用程序接收数据包

## 5. 返回路径 (Pod B → Pod A)

返回路径完全对称：

```
Pod B → veth pair → Node2 路由查找 → ARP 解析 →
物理网络传输 → Node1 路由查找 → veth pair → Pod A
```

**关键路由表**：
```bash
# Node2 到 Node1 的路由
192.168.1.0/26 via 10.0.0.10 dev eth0 proto bird onlink

# Node2 到 Node1 的 ARP
10.0.0.10 dev eth0 lladdr aa:bb:cc:dd:ee:11 REACHABLE
```

## 6. 关键命令详解

### 6.1 路由表命令

```bash
# 查看主机路由表
ip route

# 查看特定 IP 的路由路径（关键命令）
ip route get <目标IP>

# 示例：
ip route get 192.168.2.10
# 输出：192.168.2.10 via 10.0.0.2 dev eth0 src 10.0.0.10

# 查看路由表详细信息
ip route show detail

# 查看所有路由规则（优先级）
ip rule list
```

### 6.2 ARP 表命令

```bash
# 查看 ARP 缓存
ip neigh show

# 示例输出：
10.0.0.2 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE

# 查看特定 IP 的 ARP 条目
ip neigh show 10.0.0.2

# 查看 ARP 表详细信息
ip -s neigh show

# 清除 ARP 缓存（测试用）
ip neigh flush all
```

### 6.3 Bird BGP 命令

```bash
# 查看 BGP 对等体状态
birdcl show protocols

# 示例输出：
Name       Proto      Table      State  Since         Info
device1    Device     master     up     2024-01-01
kernel1    Kernel     master     up     2024-01-01
bgp1       BGP        master     up     2024-01-01    Established

# 查看 BGP 路由表
birdcl show route

# 示例输出：
192.168.2.0/26    via 10.0.0.2 dev eth0 proto bird
192.168.3.0/26    via 10.0.0.3 dev eth0 proto bird

# 查看特定路由详情
birdcl show route 192.168.2.0/26

# 查看 Bird 日志
birdcl show log
```

### 6.4 网络接口命令

```bash
# 查看所有网络接口
ip link show

# 查看网络接口详情
ip addr show

# 查看 eth0 接口
ip addr show eth0

# 查看 cali 接口（Calico Pod 网络接口）
ip addr show cali0

# 查看 veth pair
ip link show type veth
```

### 6.5 抓包命令

```bash
# 抓取节点间通信报文
tcpdump -i eth0 host 10.0.0.20 -n

# 抓取 ICMP 报文
tcpdump -i eth0 icmp -n

# 抓取 TCP 报文
tcpdump -i eth0 tcp port 80 -n

# 抓取并保存到文件
tcpdump -i eth0 -w capture.pcap

# 读取抓包文件
tcpdump -r capture.pcap -n
```

### 6.6 连通性测试命令

```bash
# 测试节点间连通性
ping -I 10.0.0.10 10.0.0.20

# 测试 Pod 间连通性
kubectl exec -it <pod-name> -- ping -c 3 <目标PodIP>

# 跟踪路由
kubectl exec -it <pod-name> -- traceroute <目标PodIP>

# 使用 mtr 工具（持续跟踪）
mtr <目标IP>

# 测试带宽
iperf3 -s  # 在 Node2 上启动服务器
iperf3 -c 10.0.0.20  # 在 Node1 上启动客户端
```

## 7. 报文转发核心要点

### 7.1 路由查找顺序

```
┌─────────────────────────────────────────────────────────────┐
│                    路由查找流程                              │
├─────────────────────────────────────────────────────────────┤
│  1. 精确匹配：查找与目标 IP 精确匹配的路由                  │
│     例：192.168.2.10 匹配 192.168.2.0/26                   │
│                                                             │
│  2. 协议优先级：同类路由比较协议优先级                       │
│     kernel > bird > static > default                        │
│                                                             │
│  3. 度量值比较：相同协议路由比较度量值（metric）            │
│     值越小优先级越高                                         │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 路由类型说明

| 路由类型 | proto 值 | 来源 | 说明 |
|---------|----------|------|------|
| 本地网段 | kernel | 内核自动生成 | 描述本地直连网络 |
| BGP 分发 | bird | Bird BGP 协议 | Calico 分发的跨节点路由 |
| 默认路由 | default | 手动或 DHCP 配置 | 匹配所有其他流量 |

### 7.3 数据包转发流程图

```
┌─────────────────────────────────────────────────────────────┐
│                  BGP 模式数据包处理完整流程                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Pod A                                                        │
│    │                                                          │
│    │ 发出数据包 (Src=Pod IP, Dst=Pod IP)                   │
│    ▼                                                          │
│  veth pair                                                    │
│    │                                                          │
│    │ 到达主机网络                                             │
│    ▼                                                          │
│  路由表查找 (ip route get <Dst Pod IP>)                     │
│    │                                                          │
│    ├── 匹配本地 Pod 网段 → 直接通过 caliX 交付             │
│    │                                                          │
│    └── 匹配远程 Pod 网段 → 通过 eth0 发送到目标节点        │
│              │                                                │
│              ▼                                                │
│         ARP 解析 (ip neigh show <Next Hop IP>)              │
│              │                                                │
│              ▼                                                │
│         二层封装 (Src=MAC, Dst=Next Hop MAC)                 │
│              │                                                │
│              ▼                                                │
│         物理网络三层转发                                      │
│              │                                                │
│              ▼                                                │
│         目标节点                                              │
│              │                                                │
│              ▼                                                │
│         路由表查找                                            │
│              │                                                │
│              ▼                                                │
│         本地交付 → veth pair → Pod B                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.4 关键表项

| 表项类型 | 作用 | 查看命令 | 示例 |
|---------|------|----------|------|
| 路由表 | 决定数据包下一跳 | `ip route` | `192.168.2.0/26 via 10.0.0.2` |
| ARP 表 | 解析 MAC 地址 | `ip neigh` | `10.0.0.2 lladdr aa:bb:cc:dd:ee:ff` |
| Bird 路由 | BGP 分发的路由 | `birdcl show route` | `192.168.2.0/26 via 10.0.0.2` |

## 8. 故障排查

### 8.1 排查流程

```
┌─────────────────────────────────────────────────────────────┐
│                    故障排查流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 检查路由                                                │
│     ip route get <目标PodIP>                               │
│     ↓                                                       │
│  2. 检查 ARP                                                │
│     ip neigh show <目标NodeIP>                             │
│     ↓                                                       │
│  3. 检查 Bird BGP                                           │
│     birdcl show protocols                                   │
│     birdcl show route                                       │
│     ↓                                                       │
│  4. 抓包分析                                                │
│     tcpdump -i eth0 host <目标NodeIP> -n                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 常见问题及解决方法

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 路由缺失 | Bird BGP 会话未建立 | 检查 Bird 日志和 BGP 配置 |
| ARP 解析失败 | 节点间二层不通 | 检查交换机配置 |
| 路由正确但不通 | 交换机 ACL | 检查交换机访问控制列表 |
| BGP 会话 down | 网络或配置问题 | 检查 Bird 日志 |
| 路由消失 | Bird 异常 | 重启 Bird 或检查配置 |

### 8.3 故障排查命令汇总

```bash
# 1. 检查源节点路由
echo "=== 源节点路由 ==="
ip route get <目标PodIP>

# 2. 检查目标节点路由
echo "=== 目标节点路由 ==="
ssh <目标节点> "ip route get <源PodIP>"

# 3. 检查 ARP 表
echo "=== ARP 表 ==="
ip neigh show <目标NodeIP>

# 4. 检查 Bird BGP 会话
echo "=== BGP 会话 ==="
birdcl show protocols
birdcl show route

# 5. 检查网络接口
echo "=== 网络接口 ==="
ip link show
ip addr show

# 6. 抓包分析
echo "=== 抓包 ==="
tcpdump -i eth0 host <目标NodeIP> -n -c 10
```


## 9. 最佳实践

### 9.1 故障排查建议

1. **分层排查**
   - 先检查物理网络连通性
   - 再检查路由表
   - 最后检查应用日志

2. **善用工具**
   - `ip route get` 定位路由问题
   - `ip neigh show` 定位 ARP 问题
   - `birdcl show route` 定位 BGP 问题
   - `tcpdump` 抓包分析

3. **保留证据**
   - 出现故障时保留路由表、ARP 表、抓包文件
   - 记录故障发生时间和持续时间

通过以上分析，可以清晰看到 Calico BGP 模式下 Pod 间跨节点通信时，数据包如何经过路由表查找、ARP 解析、二层封装、物理网络三层转发等步骤，最终到达目标 Pod。
