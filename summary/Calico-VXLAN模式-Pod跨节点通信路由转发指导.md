# Calico VXLAN 模式 Pod 间跨节点通信路由转发指导

## 1. Calico VXLAN 模式概述

Calico VXLAN 模式通过 UDP 封装实现 Pod 间的跨节点通信，适用于节点间网络无法直接路由的场景。该模式下，数据包通过 VXLAN 隧道进行封装传输。

### 1.1 核心特性

| 特性 | 说明 |
|------|------|
| 封装方式 | VXLAN (UDP 封装) |
| 封装协议 | UDP (端口 4789) |
| 数据包格式 | VXLAN 封装的 IP 数据包 |
| 性能 | 中等（有封装开销） |
| 依赖 | 节点间二层互通 |

### 1.2 VXLAN 数据包格式

```
┌─────────────────────────────────────────────────────────────────────┐
│ Ethernet 头                                                          │
│   Source MAC: Node1 MAC                                            │
│   Destination MAC: Node2 MAC                                       │
├─────────────────────────────────────────────────────────────────────┤
│ IP 头                                                                │
│   Source IP: Node1 IP (10.0.0.10)                                 │
│   Destination IP: Node2 IP (10.0.0.20)                              │
├─────────────────────────────────────────────────────────────────────┤
│ UDP 头                                                               │
│   Source Port: 随机端口                                             │
│   Destination Port: 4789 (VXLAN 默认端口)                          │
├─────────────────────────────────────────────────────────────────────┤
│ VXLAN 头                                                             │
│   VNI: 唯一标识符（如 4096）                                      │
├─────────────────────────────────────────────────────────────────────┤
│ 原始 IP 数据包                                                         │
│   Source IP: 192.168.1.10 (Pod A)                                 │
│   Destination IP: 192.168.2.10 (Pod B)                             │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 报文转发整体流程

### 2.1 数据包转发路径图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Calico VXLAN 模式跨节点通信报文转发流程                  │
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
│  │  192.168.2.0/26 dev vxlan.calico via 10.0.0.20 onlink         │      │
│  │  → 匹配到 192.168.2.0/26 网段，下一跳是 Node2 IP        │      │
│  └─────────────────────────────────────────────────────────────┘      │
│       │                                                                 │
│       │ ③ VXLAN 封装: 外层 Src=10.0.0.10, Dst=10.0.0.20       │      │
│       ▼                                                                 │
│  eth0 (物理网卡)                                                        │
│       │                                                                 │
│       │ ④ 通过物理网络传输到 Node2                                    │
│       ▼                                                                 │
│  eth0 (Node2 物理网卡)                                                  │
│       │                                                                 │
│       │ ⑤ 解封装: 取出原始数据包 Src=192.168.1.10, Dst=192.168.2.10 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐      │
│  │                    Node2 路由表查找                          │      │
│  │  192.168.2.0/26 dev vxlan.calico proto kernel scope link     │      │
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
192.168.1.0/26 dev vxlan.calico proto kernel scope link src 192.168.1.1
192.168.2.0/26 via 192.168.2.0 dev vxlan.calico scope link onlink
192.168.3.0/26 via 192.168.3.0 dev vxlan.calico scope link onlink
```

| 路由条目 | 含义 | 动作 | 详细说明 | via 字段含义 |
|---------|------|------|----------|-------------|
| `default via 10.0.0.1` | 默认路由 | 匹配其他所有流量 | 当没有更具体的路由匹配时使用，通过 eth0 发送到网关 10.0.0.1 | `via 10.0.0.1` 表示**实际下一跳网关 IP** |
| `10.0.0.0/24 dev eth0` | 本机网络段 | 本地链路直接交付 | 节点所在的物理网络，通过 eth0 接口直接交付，无下一跳 | 无 via（本地链路直接交付） |
| `192.168.1.0/26 dev vxlan.calico` | 本节点 Pod 网段 | 直接通过 vxlan.calico 设备交付 | 由内核自动生成（proto kernel），使用 192.168.1.1 作为源地址 | 无 via（本地链路直接交付） |
| `192.168.2.0/26 via 192.168.2.0 dev vxlan.calico` | Node2 Pod 网段 | 通过 VXLAN 隧道发送到 Node2 | `via 192.168.2.0` 是目标网络地址，`onlink` 表示直接链路层发送 | `via 192.168.2.0` 表示**目标网络地址**（非下一跳），实际 VTEP IP 需查转发表 |
| `192.168.3.0/26 via 192.168.3.0 dev vxlan.calico` | Node3 Pod 网段 | 通过 VXLAN 隧道发送到 Node3 | `via 192.168.3.0` 是目标网络地址，`onlink` 表示直接链路层发送 | `via 192.168.3.0` 表示**目标网络地址**（非下一跳），实际 VTEP IP 需查转发表 |

### 3.2 Node2 路由表

```bash
# 查看 Node2 的路由表
ip route

# 输出示例：
default via 10.0.0.1 dev eth0 proto dhcp src 10.0.0.20 metric 100
10.0.0.0/24 dev eth0 proto kernel scope link src 10.0.0.20
192.168.1.0/26 via 192.168.1.0 dev vxlan.calico scope link onlink
192.168.2.0/26 dev vxlan.calico proto kernel scope link src 192.168.2.1
192.168.3.0/26 via 192.168.3.0 dev vxlan.calico scope link onlink
```

| 路由条目 | 含义 | 动作 | 详细说明 | via 字段含义 |
|---------|------|------|----------|-------------|
| `default via 10.0.0.1` | 默认路由 | 匹配其他所有流量 | 当没有更具体的路由匹配时使用，通过 eth0 发送到网关 10.0.0.1 | `via 10.0.0.1` 表示**实际下一跳网关 IP** |
| `10.0.0.0/24 dev eth0` | 本机网络段 | 本地链路直接交付 | 节点所在的物理网络，通过 eth0 接口直接交付，无下一跳 | 无 via（本地链路直接交付） |
| `192.168.1.0/26 via 192.168.1.0 dev vxlan.calico` | Node1 Pod 网段 | 通过 VXLAN 隧道发送到 Node1 | `via 192.168.1.0` 是目标网络地址，`onlink` 表示直接链路层发送 | `via 192.168.1.0` 表示**目标网络地址**（非下一跳），实际 VTEP IP 需查转发表 |
| `192.168.2.0/26 dev vxlan.calico` | 本节点 Pod 网段 | 直接通过 vxlan.calico 设备交付 | 由内核自动生成（proto kernel），使用 192.168.2.1 作为源地址 | 无 via（本地链路直接交付） |
| `192.168.3.0/26 via 192.168.3.0 dev vxlan.calico` | Node3 Pod 网段 | 通过 VXLAN 隧道发送到 Node3 | `via 192.168.3.0` 是目标网络地址，`onlink` 表示直接链路层发送 | `via 192.168.3.0` 表示**目标网络地址**（非下一跳），实际 VTEP IP 需查转发表 |


### 3.3 本地路由表

```bash
# 查看本地路由表
ip route show table local

# 输出示例：
local 10.0.0.10 dev eth0 proto kernel scope host src 10.0.0.10
local 192.168.1.1 dev vxlan.calico proto kernel scope host src 192.168.1.1
broadcast 10.0.0.0 dev eth0 proto kernel scope link src 10.0.0.10
broadcast 10.0.0.255 dev eth0 proto kernel scope link src 10.0.0.10
broadcast 192.168.1.0 dev vxlan.calico proto kernel scope link src 192.168.1.1
broadcast 192.168.1.63 dev vxlan.calico proto kernel scope link src 192.168.1.1
```

### 3.4 路由与 VXLAN 转发表的关系

```bash
# 查看 VXLAN 转发表
bridge fdb show dev vxlan.calico

# 输出示例：
00:00:00:00:00:00 dev vxlan.calico dst 10.0.0.20 self permanent
00:00:00:00:00:00 dev vxlan.calico dst 10.0.0.30 self permanent

# 查看 VXLAN 接口配置（包含 VTEP IP 信息）
ip -d link show vxlan.calico

# 输出示例：
vxlan.calico: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450 qdisc noqueue state UNKNOWN mode DEFAULT group default
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff promiscuity 0 minmtu 68 maxmtu 65535
    vxlan id 4096 local 10.0.0.10 dev eth0 srcport 0 0 dstport 4789 nolearning ageing 300 noudpcsum noudp6zerocsumtx noudp6zerocsumrx addrgenmode eui64
```

**VTEP IP 信息**：
- **本地 VTEP IP**：`local 10.0.0.10`（Node1 的物理网卡 IP）
- **对端 VTEP IP**：转发表中的 `dst 10.0.0.20`（Node2 的物理网卡 IP）和 `dst 10.0.0.30`（Node3 的物理网卡 IP）

**路由与转发表的关联**：
1. 当数据包匹配到 `192.168.2.0/26 dev vxlan.calico` 路由时
2. 系统查找 VXLAN 转发表，找到目标节点的 VTEP IP 10.0.0.20
3. 封装 VXLAN 数据包，外层 IP 头的目标地址为对端 VTEP IP 10.0.0.20
4. 通过物理接口 eth0 发送到对端节点

### 3.5 VTEP IP 与路由查找过程

**关键理解**：路由表中的 `via` 字段在不同类型路由中含义不同：

1. **普通网关路由**（如 `default via 10.0.0.1`）：
   - `via` 字段表示**实际下一跳网关 IP**
   - 数据包直接发送到该网关地址

2. **VXLAN 路由**（如 `192.168.2.0/26 via 192.168.2.0 dev vxlan.calico`）：
   - `via` 字段表示**目标网络地址**（不是下一跳）
   - `onlink` 标志表示直接链路层交付，不经过网关
   - 实际的对端 VTEP IP **不在路由表中**，而是在 VXLAN 转发表中

**VTEP IP 查找过程**：

1. 数据包匹配到 `192.168.2.0/26 via 192.168.2.0 dev vxlan.calico` 路由
2. 系统查找 VXLAN 转发表（`bridge fdb`）：
   ```bash
   bridge fdb show dev vxlan.calico
   # 输出：00:00:00:00:00:00 dev vxlan.calico dst 10.0.0.20 self permanent
   ```
3. 找到对端 VTEP IP 10.0.0.20
4. 封装 VXLAN 数据包并发送到 10.0.0.20

**路由与转发表对照**：

| 路由条目 | 目标网段 | via 字段含义 | 实际 VTEP IP（查转发表） |
|---------|---------|-------------|------------------------|
| `192.168.2.0/26 via 192.168.2.0 dev vxlan.calico` | Node2 Pod 网段 | 目标网络地址 | 10.0.0.20（Node2 IP） |
| `192.168.3.0/26 via 192.168.3.0 dev vxlan.calico` | Node3 Pod 网段 | 目标网络地址 | 10.0.0.30（Node3 IP） |

### 3.6 路由查找过程

1. **数据包到达**：数据包进入主机网络命名空间
2. **路由规则匹配**：按照优先级顺序匹配路由规则
3. **路由表查找**：在匹配的路由表中查找最具体的路由
4. **确定出接口**：根据路由条目确定出接口（vxlan.calico）
5. **VXLAN 封装**：如果是远程 Pod 网段，查找转发表并封装
6. **发送数据包**：通过物理接口发送封装后的数据包

### 3.7 附加路由信息

| 路由属性 | 含义 | 示例 |
|---------|------|------|
| `proto` | 路由协议类型 | `proto kernel`（内核生成）、`proto dhcp`（DHCP 获取） |
| `scope` | 路由作用域 | `scope link`（本地链路）、`scope host`（本机）、`scope global`（全局） |
| `metric` | 路由度量值 | 数值越小优先级越高，如 `metric 100` |
| `src` | 源 IP 地址 | 发送数据包时使用的源地址 |
| `onlink` | 链路层直接交付 | 不经过网关，直接通过链路层发送 |

### 3.8 VXLAN 接口

```bash
# 查看 VXLAN 接口
ip link show vxlan.calico

# 输出示例：
vxlan.calico: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450 qdisc noqueue state UNKNOWN mode DEFAULT group default
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff

# 查看 VXLAN 配置
ip -d link show vxlan.calico

# 输出示例：
vxlan.calico: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450 qdisc noqueue state UNKNOWN mode DEFAULT group default
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff promiscuity 0 minmtu 68 maxmtu 65535
    vxlan id 4096 local 10.0.0.10 dev eth0 srcport 0 0 dstport 4789 nolearning ageing 300 noudpcsum noudp6zerocsumtx noudp6zerocsumrx addrgenmode eui64 numtxqueues 1 numrxqueues 1 gso_max_size 65536 gso_max_segs 65535 tso_max_size 65536 tso_max_segs 65535
```

### 3.9 iptables 规则分析

#### 3.9.1 FORWARD 链中的 Calico 规则

```bash
# 查看 FORWARD 链的规则
iptables -L FORWARD -n

# 输出示例：
Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
cali-FORWARD  all  --  0.0.0.0/0            0.0.0.0/0            /* calico: forwarding policy */
```

**说明**：所有转发的数据包都会经过 Calico 的 `cali-FORWARD` 链处理。

```bash
# 查看 Calico 转发链规则
iptables -L cali-FORWARD -n

# 输出示例：
Chain cali-FORWARD (1 references)
target     prot opt source               destination
cali-failsafe-in  all  --  0.0.0.0/0            0.0.0.0/0            /* cali: failsafe for inbound traffic */
cali-failsafe-out  all  --  0.0.0.0/0            0.0.0.0/0            /* cali: failsafe for outbound traffic */
ACCEPT     all  --  0.0.0.0/0            0.0.0.0/0            /* cali: default allow */
```

#### 3.9.2 PREROUTING 链中的 Calico 规则

```bash
# 查看 Calico PREROUTING 链规则
iptables -t nat -L cali-PREROUTING -n

# 输出示例：
Chain cali-PREROUTING (1 references)
target     prot opt source               destination
ACCEPT     all  --  0.0.0.0/0            0.0.0.0/0            /* cali: preserve incoming mark */ mark match 0x10000/0x10000
DNAT       all  --  0.0.0.0/0            192.168.1.0/26       /* cali: DNAT to workload */ to:192.168.1.0/26
```

#### 3.9.3 iptables 转发流程

**Pod 间跨节点转发流程**：

1. 数据包从 Pod A 通过 veth pair 到达主机
2. 进入 `PREROUTING` 链 → `cali-PREROUTING` 链
3. 如果有 DNAT 规则，对目标地址进行转换
4. 进入 `FORWARD` 链 → `cali-FORWARD` 链
5. 经过 `cali-failsafe-in` 和 `cali-failsafe-out` 检查
6. 匹配 NetworkPolicy 规则（ACCEPT/DROP）
7. 默认允许通过，进入 `POSTROUTING` 链
8. 根据路由表匹配结果，发送到 vxlan.calico 接口

**关键规则说明**：

| 规则 | 作用 |
|------|------|
| `cali-failsafe-in` | 保障节点基本通信，允许关键端口流量 |
| `cali-failsafe-out` | 保障节点基本通信，允许关键端口流量 |
| `ACCEPT all` | 默认允许符合策略的流量通过 |

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

#### 步骤 2：数据包到达 veth pair 并经过 iptables PREROUTING 链

```
位置：veth pair (calixxx) → iptables PREROUTING 链
数据包：
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
└─────────────────────────────────┘
```

**动作**：
1. 数据包通过 veth pair 到达主机网络命名空间
2. 进入 iptables PREROUTING 链
3. 匹配 `cali-PREROUTING` 规则
4. 由于源 IP 是 Pod IP，标记为 0x10000，跳过 DNAT 处理
5. 继续路由查找

#### 步骤 3：Node1 路由表查找

```
位置：Node1 主机网络命名空间
执行命令：ip route get 192.168.2.10
输出：192.168.2.10 dev vxlan.calico scope link onlink
```

**查找过程**：

1. **查询路由表**：`ip route get 192.168.2.10`
2. **匹配目标网络**：`192.168.2.10` 匹配 `192.168.2.0/26`
3. **确定出接口**：`dev vxlan.calico`（VXLAN 接口）
4. **确定交付方式**：`scope link onlink`（通过 VXLAN 隧道）

**路由决策**：
```
匹配路由：192.168.2.0/26 dev vxlan.calico scope link onlink
出接口：vxlan.calico
交付方式：通过 VXLAN 隧道发送
```

#### 步骤 4：iptables FORWARD 链处理

```
位置：Node1 主机网络命名空间 → iptables FORWARD 链
数据包：
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
└─────────────────────────────────┘
```

**动作**：
1. 数据包进入 iptables FORWARD 链
2. 匹配 `cali-FORWARD` 规则
3. 经过 `cali-failsafe-in` 和 `cali-failsafe-out` 检查
4. 由于没有匹配到拒绝规则，执行默认的 ACCEPT 动作
5. 继续转发到 vxlan.calico 接口

#### 步骤 5：VXLAN 封装

```
位置：Node1 VXLAN 接口
执行命令：ip -d link show vxlan.calico
```

**封装过程**：
1. 识别目标 Pod IP 192.168.2.10
2. 查找 VXLAN 转发表，确定目标节点 IP 10.0.0.20
3. 封装 VXLAN 头，VNI=4096
4. 封装 UDP 头，目标端口 4789
5. 封装 IP 头，源 IP=10.0.0.10，目标 IP=10.0.0.20
6. 封装 Ethernet 头，源 MAC=Node1 MAC，目标 MAC=Node2 MAC

**封装后数据包**：
```
┌─────────────────────────────────────────────────────────────────────┐
│ Ethernet 头                                                          │
│   Source MAC: aa:bb:cc:dd:ee:11 (Node1)                            │
│   Destination MAC: aa:bb:cc:dd:ee:22 (Node2)                       │
├─────────────────────────────────────────────────────────────────────┤
│ IP 头                                                                │
│   Source IP: 10.0.0.10 (Node1)                                     │
│   Destination IP: 10.0.0.20 (Node2)                                │
├─────────────────────────────────────────────────────────────────────┤
│ UDP 头                                                               │
│   Source Port: 54321                                                │
│   Destination Port: 4789 (VXLAN)                                   │
├─────────────────────────────────────────────────────────────────────┤
│ VXLAN 头                                                             │
│   VNI: 4096                                                         │
├─────────────────────────────────────────────────────────────────────┤
│ 原始 IP 数据包                                                         │
│   Source IP: 192.168.1.10 (Pod A)                                 │
│   Destination IP: 192.168.2.10 (Pod B)                             │
└─────────────────────────────────────────────────────────────────────┘
```

#### 步骤 5：通过物理网络传输

```
位置：物理网络交换机
传输路径：
┌─────────┐      ┌─────────┐      ┌─────────┐
│ Node1   │ ──── │ Switch  │ ──── │ Node2   │
│ eth0    │      │ (L2)   │      │ eth0    │
└─────────┘      └─────────┘      └─────────┘
   10.0.0.10                   10.0.0.20
```

**数据包**：VXLAN 封装的完整数据包

**备注**：如果家里测试环境没有 L3 Switch，两个节点处于同一二层网络（通过普通交换机或直连），数据包会通过二层交换机转发，无需三层路由。此时交换机只做 MAC 地址学习，不修改 IP 报文。

#### 步骤 6：Node2 接收并解封装

```
位置：Node2 网络栈
执行命令：tcpdump -i eth0 udp port 4789 -n
```

**接收过程**：
1. 网卡 eth0 收到 UDP 数据包（端口 4789）
2. 识别为 VXLAN 数据包
3. 传递给 vxlan.calico 接口处理
4. 解封装 VXLAN 头、UDP 头、外层 IP 头
5. 取出原始数据包

**解封装后数据包**：
```
┌─────────────────────────────────┐
│ IP 头                            │
│   Source IP: 192.168.1.10      │
│   Destination IP: 192.168.2.10 │
└─────────────────────────────────┘
```

#### 步骤 7：Node2 路由表查找

```
位置：Node2 主机网络命名空间
执行命令：ip route get 192.168.2.10
输出：192.168.2.10 dev vxlan.calico src 192.168.2.1
```

**查找过程**：

1. **查询路由表**：`ip route get 192.168.2.10`
2. **匹配本地网段**：`192.168.2.10` 匹配本地网段 `192.168.2.0/26`
3. **确定出接口**：`dev vxlan.calico`（Pod 网络接口）
4. **确定交付方式**：`scope link`（本地链路直接交付）

**路由决策**：
```
匹配路由：192.168.2.0/26 dev vxlan.calico proto kernel scope link
出接口：vxlan.calico
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
Pod B → veth pair → Node2 路由查找 → VXLAN 封装 →
物理网络传输 → Node1 解封装 → Node1 路由查找 → veth pair → Pod A
```

**关键路由表**：
```bash
# Node2 到 Node1 的路由
192.168.1.0/26 dev vxlan.calico scope link onlink
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
# 输出：192.168.2.10 dev vxlan.calico scope link onlink

# 查看路由表详细信息
ip route show detail

# 查看所有路由规则（优先级）
ip rule list
```

### 6.2 VXLAN 接口命令

```bash
# 查看 VXLAN 接口
ip link show vxlan.calico

# 查看 VXLAN 详细配置
ip -d link show vxlan.calico

# 查看 VXLAN 转发表
bridge fdb show dev vxlan.calico

# 示例输出：
00:00:00:00:00:00 dev vxlan.calico dst 10.0.0.20 self permanent
00:00:00:00:00:00 dev vxlan.calico dst 10.0.0.30 self permanent
```

### 6.3 ARP 表命令

```bash
# 查看 ARP 缓存
ip neigh show

# 示例输出：
10.0.0.20 dev eth0 lladdr aa:bb:cc:dd:ee:22 REACHABLE
192.168.1.10 dev vxlan.calico lladdr aa:bb:cc:dd:ee:33 REACHABLE
```

### 6.4 抓包命令

```bash
# 抓取 VXLAN 数据包
tcpdump -i eth0 udp port 4789 -n

# 示例输出：
10:00:00.000000 IP 10.0.0.10.54321 > 10.0.0.20.4789: VXLAN, flags [I] (0x08), vni 4096
IP 192.168.1.10 > 192.168.2.10: ICMP echo request, id 1234, seq 1, length 64

# 抓取解封装后的数据包
tcpdump -i vxlan.calico -n

# 示例输出：

### 6.5 iptables 命令

```bash
# 查看 Calico 相关的 iptables 链
iptables -L | grep -E "CALI|cali"

# 查看 FORWARD 链规则
iptables -L FORWARD -n

# 查看 Calico 转发链规则
iptables -L cali-FORWARD -n

# 查看 PREROUTING 链规则（nat 表）
iptables -t nat -L PREROUTING -n

# 查看 Calico PREROUTING 链规则
iptables -t nat -L cali-PREROUTING -n

# 查看 Calico 策略相关规则
iptables -L | grep -A 10 -B 2 "cali-policy"

# 查看 iptables 规则的计数器
iptables -L cali-FORWARD -n -v
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
│     kernel > static > default                                │
│                                                             │
│  3. 度量值比较：相同协议路由比较度量值（metric）            │
│     值越小优先级越高                                         │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 VXLAN 模式路由类型

| 路由类型 | 说明 | 路由条目 |
|---------|------|----------|
| 本地 Pod 网段 | 本节点 Pod 网络 | `192.168.1.0/26 dev vxlan.calico proto kernel` |
| 远程 Pod 网段 | 其他节点 Pod 网络 | `192.168.2.0/26 dev vxlan.calico scope link onlink` |
| 默认路由 | 其他网络 | `default via 10.0.0.1 dev eth0` |

### 7.3 数据包转发流程图

```
┌─────────────────────────────────────────────────────────────┐
│                  VXLAN 模式数据包处理完整流程                 │
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
│    └── 匹配远程 Pod 网段 → 通过 vxlan.calico (VXLAN) 发送  │
│              │                                                │
│              ▼                                                │
│         VXLAN 封装 (UDP 4789)                              │
│              │                                                │
│              ▼                                                │
│         ARP 解析 (获取目标节点 MAC)                         │
│              │                                                │
│              ▼                                                │
│         二层封装 (Src=MAC, Dst=Node MAC)                     │
│              │                                                │
│              ▼                                                │
│         物理网络传输                                          │
│              │                                                │
│              ▼                                                │
│         目标节点                                              │
│              │                                                │
│              ▼                                                │
│         VXLAN 解封装                                         │
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
| 路由表 | 决定数据包下一跳 | `ip route` | `192.168.2.0/26 dev vxlan.calico` |
| ARP 表 | 解析 MAC 地址 | `ip neigh` | `10.0.0.20 lladdr aa:bb:cc:dd:ee:22` |
| 转发表 | VXLAN 目标映射 | `bridge fdb show dev vxlan.calico` | `dst 10.0.0.20 self` |

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
│  2. 检查 VXLAN 接口                                          │
│     ip -d link show vxlan.calico                           │
│     ↓                                                       │
│  3. 检查 VXLAN 转发表                                        │
│     bridge fdb show dev vxlan.calico                        │
│     ↓                                                       │
│  4. 检查 ARP 表                                             │
│     ip neigh show <目标NodeIP>                             │
│     ↓                                                       │
│  5. 检查 iptables 规则                                        │
│     iptables -L cali-FORWARD -n -v                         │
│     ↓                                                       │
│  6. 抓包分析                                                │
│     tcpdump -i eth0 udp port 4789 -n                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 常见问题及解决方法

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| VXLAN 接口未 UP | 配置错误 | 检查 Calico 配置 |
| 转发表缺失 | 节点发现失败 | 检查 Calico 节点状态 |
| 封装失败 | 内核模块未加载 | 检查 vxlan 内核模块 |
| 端口被防火墙阻止 | 4789 端口未开放 | 检查防火墙规则 |
| MTU 问题 | 封装后超过 MTU | 调整 VXLAN MTU |
| iptables 规则阻止 | Calico 策略限制 | 检查 NetworkPolicy 配置 |
| iptables 链异常 | Calico 组件故障 | 重启 Calico 组件 |

### 8.3 故障排查命令汇总

```bash
# 1. 检查路由
echo "=== 路由表 ==="
ip route get <目标PodIP>

# 2. 检查 VXLAN 接口
echo "=== VXLAN 接口 ==="
ip -d link show vxlan.calico

# 3. 检查 VXLAN 转发表
echo "=== VXLAN 转发表 ==="
bridge fdb show dev vxlan.calico

# 4. 检查 iptables 规则
echo "=== iptables 规则 ==="
iptables -L cali-FORWARD -n -v
iptables -t nat -L cali-PREROUTING -n

# 5. 检查 ARP 表
echo "=== ARP 表 ==="
ip neigh show <目标NodeIP>

# 6. 检查网络接口
echo "=== 网络接口 ==="
ip link show
ip addr show

# 7. 抓包分析
echo "=== 抓包 VXLAN 数据包 ==="
tcpdump -i eth0 udp port 4789 -n -c 10

# 8. 检查 Calico 状态
echo "=== Calico 状态 ==="
calicoctl node status
```


## 9. 最佳实践

### 9.1 故障排查建议

1. **分层排查**
   - 先检查物理网络连通性
   - 再检查 VXLAN 接口
   - 最后检查应用日志

2. **善用工具**
   - `ip route get` 定位路由问题
   - `ip -d link show` 检查 VXLAN 配置
   - `bridge fdb show` 检查转发表
   - `tcpdump` 抓包分析

3. **监控建议**
   - 监控 VXLAN 接口状态
   - 监控 4789 端口流量
   - 监控网络延迟和丢包

通过以上分析，可以清晰看到 Calico VXLAN 模式下 Pod 间跨节点通信时，数据包如何经过路由表查找、VXLAN 封装、物理网络传输、解封装等步骤，最终到达目标 Pod。
