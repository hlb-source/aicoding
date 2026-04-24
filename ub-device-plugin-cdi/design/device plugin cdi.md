# RFC: Kubernetes 设备直通 Device Plugin + CDI 解决方案

## 1. 摘要

本 RFC 文档描述了一种基于 Kubernetes Device Plugin 和 Container Device Interface (CDI) 机制的设备直通解决方案。该方案解决了物理机重启后设备名称变化导致容器无法正常访问设备的问题，通过设备唯一标识和稳定名称映射确保设备访问的可靠性。

## 2. 状态

- **当前状态**: 草稿
- **版本**: 1.0.1
- **最后更新**: 2026-04-22
- **作者**: hlb

## 3. 问题背景

### 3.1 问题描述

在 Kubernetes 集群中，设备的直通是高性能计算、AI 训练等场景的重要需求。然而，由于 Linux 内核设备枚举的不确定性，物理机重启后设备名称（如 `/dev/uburma/udma1`）可能发生变化，导致容器启动失败或无法访问预期设备。

### 3.2 问题根因

**核心根因**：kubelet checkpoint 机制存储的是**设备路径**而非**逻辑标识**

**问题链条**：
```
物理机重启 → 设备枚举顺序变化 → 设备路径改变
                                    ↓
kubelet 从 checkpoint 恢复容器 → 使用旧的设备路径挂载 → 设备不存在 → 挂载失败 → 容器 CrashLoopBackOff
```

**根因拆解**：

| 根因 | 说明 |
| ---- | ---- |
| 根因1 | kubelet checkpoint 存储的是设备路径（如 `/dev/uburma/udma1`），而非逻辑标识（如 `urma_1`） |
| 根因2 | 容器恢复时不会重新调用 Device Plugin Allocate 接口，无法获取最新的设备路径 |
| 根因3 | 设备路径在物理机重启后可能发生变化 |

**关键矛盾**：容器恢复流程依赖的是"静态的设备路径"，而实际环境是"动态的设备路径"

### 3.3 kubelet_internal_checkpoint 数据结构

```json
{
  "Data": {
    "PodDeviceEntries": [
      {
        "PodUID": "fjdsklf9gdf-gfgr-4e543fgddg-gfdgd342gdf32",
        "ContainerName": "ub-test",
        "ResourceName": "unifiedbus.com/ub_net_device",
        "DeviceIDs": {
          "-1": [
            "urma_1"
          ]
        },
        "AllocResp": "L2Rldi91YnVybWEvdWRtYTE7L2Rldi91YnVybWEvdWRtYTMxOy9kZXYvdWJ1cm1hL2JpbmRpbmdfZGV2XzE="
      }
    ],
  },
}
```

**字段说明**：
- `DeviceIDs`：设备逻辑标识列表，如 `["urma_1"]`
- `AllocResp`：Allocate 接口 Response 的 Base64 编码，包含设备路径映射
- **解码示例**：上述 Base64 字符串解码后为：
  ```
  /dev/uburma/udma1 /dev/uburma/udma1;/dev/uburma/udma31 /dev/uburma/udma31;/dev/uburma/binding_dev_1 /dev/uburma/udma1
  ```

### 3.4 物理机重启容器恢复流程

1. **物理机重启**：
   - 系统关机并重新启动
   - 设备枚举顺序可能发生变化
   - 设备路径可能改变（如 `/dev/uburma/udma1` → `/dev/uburma/udma2`）
2. **kubelet 启动**：
   - kubelet 进程启动
   - 读取 `/var/lib/kubelet/kubelet_internal_checkpoint` 目录中的检查点文件
   - 解析检查点中的容器配置
3. **容器恢复准备**：
   - kubelet 识别需要恢复的容器
   - 从检查点中提取容器配置，包括设备信息（从 AllocResp 字段解码获取）
   - 准备容器的运行环境
4. **设备挂载尝试**：
   - kubelet 尝试按照检查点中的设备路径挂载设备
   - 如果设备路径已变化，挂载失败（设备不存在时挂载失败）
   - 容器启动失败，进入 CrashLoopBackOff 状态

## 4. 解决方案概述

### 4.1 核心设计思路

**设计目标**：将容器与设备路径解耦，使用逻辑标识替代设备路径

本解决方案通过 Kubernetes Device Plugin + CDI (Container Device Interface) 机制解决设备名称变更问题，版本要求：
- **Kubernetes**: 1.31
- **containerd**: 2.0+

**问题根因与解决方案对应关系**：

| 问题根因 | 解决方案 |
| -------- | -------- |
| kubelet checkpoint 存储设备路径 | 使用 CDI 机制，checkpoint 只存储逻辑标识 |
| 容器恢复不调用 Allocate | 容器启动时通过 CDI 引用查找最新的设备路径 |
| 设备路径可能变化 | 设备插件启动时重新扫描并更新 CDI 文件 |

**核心设计思路**：

1. **逻辑标识替代设备路径**：
   - Device Plugin 分配逻辑标识（如 `urma_1`）而非设备路径
   - kubelet checkpoint 只存储逻辑标识，设备路径从 CDI 文件动态获取
   - 逻辑标识基于设备唯一标识生成，重启后保持稳定

2. **CDI 配置文件管理设备路径**：
   - 在 `/var/run/cdi` 目录存放 CDI 配置文件
   - CDI 文件记录逻辑标识与设备路径的映射关系
   - 设备插件启动时扫描设备并生成/更新 CDI 配置文件
   - 利用 `/var/run/cdi` 临时文件系统特性，重启后自动清空旧的 CDI 文件

3. **containerd 动态注入设备**：
   - containerd 根据 Pod spec 中的 CDI 引用（kind + name）查找 CDI 配置文件
   - 从 CDI 配置中获取最新的设备路径并注入容器
   - 无需重新调用 Device Plugin Allocate 接口

### 4.2 物理机重启容器恢复流程（CDI 方案）

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           物理机重启容器恢复流程                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                   │
│  │  物理机重启   │────▶│   kubelet    │────▶│   Device     │                   │
│  │              │     │    启动      │     │   Plugin     │                   │
│  └──────────────┘     └──────────────┘     │   启动       │                   │
│         │                    │               └──────┬───────┘                   │
│         │                    │                      │                           │
│         │                    │                      ▼                           │
│         │                    │              ┌──────────────┐                   │
│         │                    │              │  扫描设备    │                   │
│         │                    │              │  生成CDI文件 │                   │
│         │                    │              │  /var/run/cdi│                   │
│         │                    │              └──────┬───────┘                   │
│         │                    │                     │                           │
│         │                    ▼                     │                           │
│         │            ┌──────────────┐            │                           │
│         │            │  读取checkpoint │◀────────┘                           │
│         │            │  获取CDI引用    │                                     │
│         │            │  (kind+name)   │                                     │
│         │            └──────┬─────────┘                                     │
│         │                   │                                                │
│         │                   ▼                                                │
│         │            ┌──────────────┐                                       │
│         │            │  containerd  │                                       │
│         │            │  查找CDI文件  │◀───────── CDI文件已存在               │
│         │            │  获取设备路径 │                                     │
│         │            └──────┬─────────┘                                     │
│         │                   │                                                │
│         │                   ▼                                                │
│         │            ┌──────────────┐                                       │
│         │            │  挂载设备     │                                       │
│         │            │  启动容器     │                                       │
│         │            └──────────────┘                                       │
│         │                   │                                                │
│         │                   ▼                                                │
│         │            ┌──────────────┐                                       │
│         │            │  容器运行正常 │                                       │
│         │            └──────────────┘                                       │
│         │                                                                   │
│         │                                                                   │
└─────────┴───────────────────────────────────────────────────────────────────┘
```

**关键步骤说明**：

| 步骤 | 操作 | 说明 |
| ---- | ---- | ---- |
| 1 | kubelet 启动 | 读取 `/var/lib/kubelet/kubelet_internal_checkpoint` |
| 2 | Device Plugin 启动 | 扫描设备，生成 CDI 配置文件到 `/var/run/cdi` |
| 3 | 读取 checkpoint | 获取 CDI 引用（kind + name），而非设备路径 |
| 4 | containerd 查找 CDI | 根据 CDI 引用查找配置，获取**最新**设备路径 |
| 5 | 挂载并启动 | 使用最新设备路径挂载，容器正常运行 |

### 4.3 CDI 方案可行性分析

**与传统方案的对比**：

| 对比项 | 传统方案（无 CDI） | CDI 方案 |
| ------ | ------------------ | -------- |
| checkpoint 存储 | 设备路径（如 `/dev/uburma/udma1`） | CDI 引用（kind + name） |
| 容器恢复调用 Allocate | 否 | 否 |
| 获取设备路径 | 从 checkpoint 读取（旧的） | 从 CDI 文件读取（新的） |
| 设备路径变化影响 | 导致挂载失败 | 不影响（使用最新路径） |

**可行性结论**：

CDI 方案**可行**，原因如下：

1. **无需修改容器恢复流程**：容器恢复时不调用 Allocate 的行为不变
2. **checkpoint 存储 CDI 引用**：存储的是逻辑标识（kind + name），而非设备路径
3. **CDI 文件实时更新**：设备插件启动时重新扫描设备，生成最新的 CDI 配置文件
4. **containerd 动态查找**：容器启动时通过 CDI 引用查找 CDI 文件，获取最新的设备路径

**前提条件**：

| 条件 | 说明 |
| ---- | ---- |
| Device Plugin 先于容器启动 | DaemonSet 需配置适当优先级，确保设备插件就绪后再调度业务 Pod |
| CDI 文件及时生成 | 设备插件启动后立即扫描设备并生成 CDI 配置文件 |
| containerd 2.0+ | 支持通过 CRI CDIDevices 字段传递 CDI 设备引用 |

### 4.4 Device Plugin 晚于业务容器启动的影响性分析

**场景描述**：如果 Device Plugin 未就绪时，业务 Pod 被调度到该节点

**影响分析**：

| 影响项 | 具体影响 |
| ------ | -------- |
| Pod 状态 | Pod 处于 **Pending** 状态，等待 Device Plugin 就绪 |
| 容器启动 | **无法启动**，因为设备资源不可用 |
| CDI 文件 | 不存在，containerd 查找 CDI 文件失败 |

**失败流程**：

```
物理机重启 → kubelet 启动 → 业务 Pod 被调度 → containerd 查找 CDI 文件
                                                          │
                                                          ▼
                                               CDI 文件不存在（Device Plugin 未启动）
                                                          │
                                                          ▼
                                               containerd 返回错误
                                                          │
                                                          ▼
                                               Pod 启动失败，持续 Pending 或 Error
```

**与无 CDI 方案的区别**：

| 对比项 | 无 CDI 方案 | CDI 方案 |
| ------ | ----------- | -------- |
| 设备路径来源 | checkpoint 中的旧路径 | CDI 文件 |
| Pod 状态 | 可能启动成功（路径碰巧未变）或 CrashLoopBackOff | Pending（设备不可用）或 Error |
| 失败确定性 | 不确定（取决于设备路径是否变化） | 确定（Pod 不会错误启动） |

**CDI 方案的优势**：

| 优势 | 说明 |
| ---- | ---- |
| 失败可预测 | Pod 不会在设备不可用时错误启动 |
| 状态明确 | Pod 处于 Pending 状态，可通过 `kubectl describe` 明确看到原因 |
| 自动恢复 | Device Plugin 就绪后，Pod 自动调度并启动 |

**建议措施**：

| 措施 | 说明 |
| ---- | ---- |
| 配置 Pod 优先级 | 使用 `priorityClassName` 确保 Device Plugin Pod 优先调度 |
| 配置污点和容忍 | Device Plugin 使用污点，业务 Pod 配置相应容忍 |
| 配置资源依赖 | 使用 `resources.limits` 明确设备依赖，kubelet 会等待资源就绪 |
| 监控告警 | 监控 Device Plugin 状态，设置告警确保及时发现异常 |

## 5. 详细设计

### 5.1 CDI 配置格式

CDI 配置文件采用 YAML 格式，存储在 `/var/run/cdi` 目录。每个设备对应一个配置文件。

**文件命名规范**：`{resource-name}-{device-id}.yaml`

**配置示例**：

```yaml
cdiVersion: 0.5.0
kind: unifiedbus.com/ub_net_device
devices:
  - name: urma_1
    deviceNodes:
      - path: /dev/uburma/udma1
        containerPath: /dev/uburma/udma1
        permissions: rwm
  - name: urma_2
    deviceNodes:
      - path: /dev/uburma/udma31
        containerPath: /dev/uburma/udma31
        permissions: rwm
```

**字段说明**：

| 字段 | 说明 | 示例 |
| ---- | ---- | ---- |
| `cdiVersion` | CDI 规范版本 | 0.5.0 |
| `kind` | 设备类型标识（格式：`{domain}/{name}`） | unifiedbus.com/ub_net_device |
| `devices[].name` | 设备逻辑标识 | urma_1 |
| `devices[].deviceNodes[].path` | 宿主机设备路径 | /dev/uburma/udma1 |
| `devices[].deviceNodes[].containerPath` | 容器内设备路径 | /dev/uburma/udma1 |
| `devices[].deviceNodes[].permissions` | 设备权限 | rwm |

**文件示例**：`/var/run/cdi/ub-net-device-urma_1.yaml`

### 5.2 containerd 配置

**版本要求**：containerd 2.0+

**配置文件**：`/etc/containerd/config.toml`

**配置示例**：

```toml
[plugins."io.containerd.grpc.v1.cri"]
  device_plugins = true
  [plugins."io.containerd.grpc.v1.cri".containerd]
    [plugins."io.containerd.grpc.v1.cri".containerd.cdi]
      enabled = true
      spec_dirs = ["/var/run/cdi"]
```

**配置说明**：

| 配置项 | 说明 |
| ---- | ---- |
| `device_plugins` | 启用 Device Plugin 支持 |
| `cdi.enabled` | 启用 CDI 设备注入 |
| `cdi.spec_dirs` | CDI 配置文件目录 |

**重启 containerd**：
```bash
systemctl restart containerd
```

**验证配置**：
```bash
ctr cdi list
```

### 5.3 Device Plugin 关键实现

Device Plugin 是 CDI 方案的核心，需要实现以下功能：

#### 5.3.1 主要职责

| 职责 | 说明 |
| ---- | ---- |
| 设备扫描 | 发现系统中的设备，记录设备路径和唯一标识 |
| CDI 文件生成 | 将设备路径映射写入 `/var/run/cdi` 目录的 CDI 配置文件 |
| 设备分配 | 在 Allocate 响应中返回 CDI 设备引用（kind + name） |
| 状态上报 | 通过 ListAndWatch 上报设备状态 |

#### 5.3.2 关键代码实现

**1. 生成 CDI 配置文件**：

```go
func generateCDIConfig(devices map[string]*Device) error {
    spec := CDISpec{
        CDIVersion: "0.5.0",
        Kind:       "unifiedbus.com/ub_net_device",
        Devices:    make([]DeviceEntry, 0),
    }

    for _, dev := range devices {
        spec.Devices = append(spec.Devices, DeviceEntry{
            Name: dev.ID,
            DeviceNodes: []DeviceNode{
                {
                    Path:          dev.Path,
                    ContainerPath: dev.Path,
                    Permissions:   "rwm",
                },
            },
        })
    }

    data, _ := yaml.Marshal(spec)
    tempFile := "/var/run/cdi/ub-net-device.yaml.tmp" # 非常重要，避免containerd加载到不完整的cdi文件内容
    ioutil.WriteFile(tempFile, data, 0644)
    os.Rename(tempFile, "/var/run/cdi/ub-net-device.yaml")
    return nil
}
```

**2. 分配设备时返回 CDI 引用**：

```go
func Allocate(req *v1beta1.AllocateRequest) (*v1beta1.AllocateResponse, error) {
    resp := &v1beta1.AllocateResponse{}
    for _, id := range req.DevicesIDs {
        resp.ContainerResponses = append(resp.ContainerResponses, &v1beta1.ContainerAllocateResponse{
            CDIDevices: []*v1beta1.CDIDevice{
                {
                    Kind: "unifiedbus.com/ub_net_device",
                    Name: id,
                },
            },
        })
    }
    return resp, nil
}
```

**关键点说明**：

| 关键点 | 说明 |
| ---- | ---- |
| Allocate 响应 | 只返回 CDI 引用（kind + name），不返回具体设备路径 |
| 设备路径 | 存储在 CDI 配置文件中，containerd 根据 CDI 引用动态查找 |
| 原子更新 | 先写临时文件，再重命名，确保 CDI 文件一致性 |

#### 5.3.3 设备扫描逻辑

```go
func (dp *DevicePlugin) scanDevices() error {
    devices := make(map[string]*Device)

    // 扫描设备目录
    entries, err := os.ReadDir("/dev/uburma")
    if err != nil {
        return err
    }

    for _, entry := range entries {
        if entry.IsDir() {
            continue
        }

        // 获取设备路径
        devicePath := filepath.Join("/dev/uburma", entry.Name())

        // 获取设备唯一标识（基于设备属性生成）
        deviceID := getDeviceUniqueID(devicePath)

        devices[deviceID] = &Device{
            ID:   deviceID,
            Path: devicePath,
        }
    }

    // 生成 CDI 配置文件
    return generateCDIConfig(devices)
}
```

### 5.4 CDI 文件生命周期管理

#### 5.4.1 生命周期流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   创建   │───▶│   加载   │───▶│   使用   │───▶│   更新   │───▶│   删除   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
 设备插件        containerd      容器启动      设备路径       设备移除
 扫描设备        扫描目录        使用CDI      发生变化       节点重启
```

#### 5.4.2 各阶段说明

| 阶段 | 触发条件 | 操作 |
| ---- | -------- | ---- |
| **创建** | 设备插件启动或发现新设备 | 生成 CDI 配置文件到 `/var/run/cdi` |
| **加载** | containerd 启动或 CDI 目录变化 | containerd 扫描目录，解析配置，注册 CDI 设备 |
| **使用** | Pod 请求设备 | containerd 根据 CDI 引用查找配置，注入设备到容器 |
| **更新** | 设备路径变化 | 设备插件检测变化，原子替换 CDI 文件 |
| **删除** | 设备移除或节点重启 | 删除 CDI 配置文件，containerd 更新注册表 |

#### 5.4.3 节点重启处理

```
节点重启
    │
    ▼
┌─────────────────────────────────────┐
│ /var/run/cdi 目录自动清空            │
│ （tmpfs 文件系统特性）               │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 设备插件启动                          │
│   │                                  │
│   ├── 扫描设备                        │
│   ├── 重新生成 CDI 配置文件          │
│   └── 上报设备就绪                    │
└─────────────────────────────────────┘
    │
    ▼
容器启动 → 使用最新的 CDI 配置
```

## 6. 物理机重启容器恢复过程分析

### 6.1 传统方案 vs CDI 方案对比

| 对比项 | 传统方案 | CDI 方案 |
| ------ | -------- | -------- |
| **checkpoint 存储** | 设备路径（如 `/dev/uburma/udma1`） | CDI 引用（kind + name） |
| **容器恢复调用 Allocate** | 否 | 否 |
| **获取设备路径** | 从 checkpoint 读取（旧的） | 从 CDI 文件读取（最新的） |
| **设备路径变化影响** | 导致挂载失败 | 不影响（使用最新路径） |

### 6.2 CDI 方案容器恢复完整流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        物理机重启容器恢复完整流程                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ 阶段1：物理机重启                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. 系统关机并重新启动                                                           │
│  2. 设备枚举顺序可能发生变化                                                     │
│  3. 设备路径可能改变（如 /dev/uburma/udma1 → /dev/uburma/udma2）                │
│  4. /var/run/cdi 目录被清空（tmpfs 文件系统特性）                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 阶段2：kubelet 启动                                                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. kubelet 进程启动                                                            │
│  2. 读取 /var/lib/kubelet/kubelet_internal_checkpoint                          │
│  3. 解析 checkpoint 中的容器配置                                                │
│  4. checkpoint 中存储的信息：                                                   │
│     - PodUID: "xxx"                                                            │
│     - ContainerName: "ub-test"                                                 │
│     - ResourceName: "unifiedbus.com/ub_net_device"                            │
│     - DeviceIDs: {"-1": ["urma_1"]}  ← 逻辑标识                                 │
│     - CDIDevices: [{"kind": "unifiedbus.com/ub_net_device", "name": "urma_1"}]│
│       ↑ CDI 引用（CDI 方案新增字段）                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 阶段3：Device Plugin 启动（DaemonSet）                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. DaemonSet 调度 Device Plugin Pod                                           │
│  2. Device Plugin 初始化                                                        │
│  3. 扫描系统设备（如 /dev/uburma/）                                             │
│  4. 获取设备路径映射（如 udma1 → /dev/uburma/udma2）                            │
│  5. 生成 CDI 配置文件到 /var/run/cdi：                                         │
│     cdiVersion: 0.5.0                                                          │
│     kind: unifiedbus.com/ub_net_device                                        │
│     devices:                                                                   │
│       - name: urma_1                                                          │
│         deviceNodes:                                                           │
│           - path: /dev/uburma/udma2  ← 最新的设备路径                           │
│             containerPath: /dev/uburma/udma2                                 │
│             permissions: rwm                                                  │
│  6. 通过 ListAndWatch 上报设备就绪状态                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 阶段4：kubelet 调度 Pod                                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. kubelet 检查 Device Plugin 是否就绪                                         │
│  2. kubelet 检查节点资源是否满足 Pod 需求                                       │
│  3. Pod 资源就绪，调度到该节点                                                  │
│  4. kubelet 创建容器（不调用 Allocate）                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 阶段5：containerd 注入设备                                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. containerd 接收创建容器请求                                                 │
│  2. 从 Pod spec 中提取 CDI 引用：                                              │
│     - kind: "unifiedbus.com/ub_net_device"                                    │
│     - name: "urma_1"                                                          │
│  3. 扫描 /var/run/cdi 目录查找 CDI 配置文件                                    │
│  4. 找到匹配的 CDI 文件，提取最新的设备路径：                                   │
│     /dev/uburma/udma2  ← 设备路径已更新                                        │
│  5. 将设备路径注入到容器 OCI 配置中                                             │
│  6. 容器使用最新的设备路径启动                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 容器启动成功：使用最新的设备路径 /dev/uburma/udma2                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 checkpoint 数据结构变化

**传统方案 checkpoint**：
```json
{
  "Data": {
    "PodDeviceEntries": [{
      "DeviceIDs": {"-1": ["urma_1"]},
      "AllocResp": "/dev/uburma/udma1 /dev/uburma/udma1"  ← 设备路径（base64解码内容）
    }]
  }
}
```

**CDI 方案 checkpoint**：
```json
{
  "Data": {
    "PodDeviceEntries": [{
      "DeviceIDs": {"-1": ["urma_1"]},
      "CDIDevices": [{
        "kind": "unifiedbus.com/ub_net_device",
        "name": "urma_1"
      }]  ← CDI 引用
    }]
  }
}
```

### 6.4 关键差异分析

| 阶段 | 传统方案 | CDI 方案 |
| ---- | -------- | -------- |
| **checkpoint 读取** | 获取设备路径 `/dev/uburma/udma1`（旧） | 获取 CDI 引用（kind + name） |
| **设备路径获取** | 直接使用 checkpoint 中的路径 | 根据 CDI 引用查找 CDI 文件 |
| **路径更新** | 无（使用旧路径） | 有（从最新 CDI 文件获取） |
| **挂载结果** | 可能失败（设备不存在） | 成功（使用最新路径） |

### 6.5 CDI 方案优势总结

| 优势 | 说明 |
| ---- | ---- |
| **路径动态更新** | 容器启动时从 CDI 文件获取最新设备路径 |
| **无需修改恢复流程** | 容器恢复时不调用 Allocate 的行为不变 |
| **失败可预测** | CDI 文件缺失时 Pod 处于 Pending，而非错误启动 |
| **自动清理** | 使用 /var/run/cdi 目录，节点重启后自动清空旧配置 |

## 7. 使用方法

### 7.1 版本要求

| 组件 | 版本 | 说明 |
| ---- | ---- | ---- |
| Kubernetes | 1.31 | 最低要求 |
| containerd | 2.0+ | CDI 支持为 Stable |
| CDI 规范 | 0.5+ | 设备配置格式 |

### 7.2 containerd 配置

```bash
# 1. 编辑 containerd 配置
sudo vi /etc/containerd/config.toml

# 2. 添加 CDI 配置
[plugins."io.containerd.grpc.v1.cri".containerd.cdi]
  enabled = true
  spec_dirs = ["/var/run/cdi"]

# 3. 重启 containerd
sudo systemctl restart containerd

# 4. 验证配置
ctr cdi list
```

### 7.3 Pod 使用示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: rdma-test
spec:
  containers:
  - name: rdma-test
    image: ubuntu:22.04
    command: ["/bin/bash", "-c", "sleep infinity"]
    resources:
      requests:
        unifiedbus.com/ub_net_device: 1
      limits:
        unifiedbus.com/ub_net_device: 1
```

### 7.4 验证步骤

```bash
# 1. 查看 CDI 设备列表
ctr cdi list

# 2. 查看节点设备资源
kubectl get nodes -o jsonpath='{.items[*].status.allocatable}'

# 3. 查看 Device Plugin 状态
kubectl get pods -n kube-system -l k8s-app=device-plugin

# 4. 查看容器内设备
kubectl exec -it rdma-test -- ls -la /dev/uburma/
```

