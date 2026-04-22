# RFC: Kubernetes RDMA 网卡直通 Device Plugin + CDI 解决方案

## 1. 摘要

本 RFC 文档描述了一种基于 Kubernetes Device Plugin 和 Container Device Interface (CDI) 机制的 RDMA 网卡直通解决方案。该方案解决了物理机重启后设备名称变化导致容器无法正常访问设备的问题，通过设备唯一标识和稳定名称映射确保设备访问的可靠性。

## 2. 状态

- **当前状态**: 草稿
- **版本**: 1.0.0
- **最后更新**: 2026-04-22
- **作者**: hlb

## 3. 介绍

在 Kubernetes 集群中，设备的直通是高性能计算、AI 训练等场景的重要需求。然而，由于 Linux 内核设备枚举的不确定性，物理机重启后 设备名称（如 `/dev/infiniband/mlx5_0`）可能发生变化，导致容器启动失败或无法访问预期设备。

本方案通过结合 Kubernetes Device Plugin 和 CDI 机制，实现了：

- 基于设备唯一标识的稳定设备名称映射
- 自动化的设备发现和注册
- 标准化的设备配置和注入
- 支持设备热插拔和动态分配

## 4. 解决方案概述

### 4.1 核心设计思路

本解决方案通过k8s高版本的 Device Plugin + CDI 机制解决设备名称变更问题，核心设计思路如下：

1. **设备信息解耦**：
   - 将真实的设备信息（路径 + 名称）与 kubelet 解耦，kubelet_internal_checkpoint文件中不在存储设备信息
   - Device Plugin 不直接返回设备路径，而是返回逻辑标识
   - 通过 CDI 配置文件管理实际设备路径

2. **逻辑标识分配**：
   - Device Plugin 的 Allocate 方法只分配逻辑标识（如 `mlx5_0`）
   - 逻辑标识基于设备唯一标识生成
   - 逻辑标识在设备重启后保持稳定
3. ** 基于/var/run/cdi存放cdi文件**
   - 物理机重启cdi文件全部清空，相当于重新分配设备
  

## 5. 详细设计

### 5.1 设备名称映射

- **映射表**：使用配置文件定义设备唯一标识到稳定名称的映射
- **动态更新**：设备状态变化时自动更新映射
- **持久化**：映射信息持久化存储，重启后恢复

### 5.2 CDI 配置

- **配置文件**：在 `/var/run/cdi` 目录创建标准化的设备配置
  - **设计说明**：使用 `/var/run/cdi` 目录而非 `/etc/cdi`，利用其临时文件系统特性，确保节点重启后 CDI 文件自动删除
  - **优势**：避免旧的 CDI 配置文件残留，确保每次启动都使用最新的设备路径
- **设备规范**：定义设备路径、权限和环境变量
- **生命周期钩子**：支持设备初始化和清理
- **containerd 配置**：
  - **版本要求**：containerd 1.6+ 版本
  - **配置文件**：`/etc/containerd/config.toml`
  - **配置示例**：
    ```toml
    [plugins."io.containerd.grpc.v1.cri"]
      device_plugins = true
      [plugins."io.containerd.grpc.v1.cri".containerd]
        [plugins."io.containerd.grpc.v1.cri".containerd.cdi]
          enabled = true
          # 自定义 CDI 配置目录
          spec_dirs = ["/var/run/cdi"]
    ```
  - **重启 containerd**：
    ```bash
    systemctl restart containerd
    ```
  - **验证配置**：
    ```bash
    ctr cdi list
    ```

### 5.3 CDI 文件生命周期管理

CDI 配置文件的生命周期管理是确保设备配置一致性和可靠性的关键环节，具体流程如下：

#### 5.3.1 创建阶段

- **触发条件**：设备插件发现新设备或设备状态变化
- **操作**：
  - 生成包含设备唯一标识、稳定名称、设备路径等信息的 CDI 配置文件
  - 写入到 `/var/run/cdi` 目录
  - 设置正确的文件权限（通常为 644）
- **示例**：`/var/run/cdi/ub-rdma-mlx5-0.yaml`

#### 5.3.2 加载阶段

- **触发条件**：
  - containerd 启动
  - CDI 目录变化
  - 手动触发
- **操作**：
  - containerd 扫描 `/var/run/cdi` 目录
  - 解析配置文件语法
  - 验证设备路径存在性
  - 注册到 CDI 注册表

#### 5.3.3 使用阶段

- **触发条件**：Pod 创建请求设备
- **操作**：
  - kubelet 通过 Device Plugin 分配设备
  - **容器关联 CDI 文件**：
    1. **设备分配响应**：Device Plugin 在 Allocate 响应中返回 CDI 设备引用
    2. **Pod 注解**：通过 `cdi.k8s.io/device` 注解指定 CDI 设备
    3. **containerd 处理**：containerd 解析 Pod 规范中的 CDI 引用
    4. **CDI 配置查找**：根据 `kind` 和 `name` 查找对应的 CDI 配置文件
    5. **配置应用**：将 CDI 配置中的设备、环境变量、挂载点等应用到容器
  - containerd 根据 CDI 配置注入设备
  - 应用生命周期钩子
  - 容器获得设备访问权限

#### 5.3.4 更新阶段

- **触发条件**：
  - 设备路径变化
  - 设备属性更新
  - 配置参数修改
- **操作**：
  - 设备插件检测到变化
  - 生成新的 CDI 配置文件
  - 原子替换旧文件（先写临时文件，再重命名）
  - containerd 自动重新加载配置

#### 5.3.5 删除阶段

- **触发条件**：
  - 设备移除
  - 设备插件停止
  - 节点重启
- **操作**：
  - 设备插件检测到设备移除
  - 删除对应的 CDI 配置文件
  - containerd 检测到文件删除并更新注册表
  - 清理相关资源
- **节点重启处理**：
  - 由于使用 `/var/run/cdi` 目录，节点重启后 CDI 文件会自动删除
  - 设备插件启动时会重新生成所有 CDI 配置文件
  - 确保使用最新的设备路径配置

## 6. 物理机重启场景分析

### 6.1 问题分析

**问题**：容器已分配 RDMA 设备，物理机重启后，容器启动时不会重新执行 Allocate 分配过程，是否会加载过时的 CDI 文件？

**答案**：会加载 CDI 文件，但需要确保 CDI 文件在重启后已更新。

### 6.2 重启流程分析

1. **重启前状态**：
   - 容器已分配 RDMA 设备
   - CDI 配置文件存在于 `/var/run/cdi` 目录
   - Pod 规范中包含 CDI 设备引用

2. **物理机重启**：
   - 设备枚举顺序可能变化，设备路径可能改变（如 `/dev/infiniband/mlx5_0` → `/dev/infiniband/mlx5_1`）
   - `/var/run/cdi` 目录被清空，CDI 配置文件自动删除

3. **容器重启**：
   - 不会重新执行 Allocate 分配过程
   - containerd 仍会根据 Pod 规范中的 CDI 引用查找配置文件
   - **关键问题**：如果 CDI 文件未重新生成，会导致设备访问失败

### 6.3 保证机制

1. **设备插件启动流程**：
   - 设备插件启动后立即扫描系统中的 RDMA 设备
   - 基于设备唯一标识（逻辑标识）识别设备
   - 检测设备路径变化，生成新的 CDI 配置文件到 `/var/run/cdi` 目录
   - 使用原子操作更新 CDI 配置（先写临时文件，再重命名）


### 6.4 业务流程

1. **设备插件启动流程**：
   - 节点启动 → kubelet 启动 → DaemonSet 调度
   - 设备插件初始化 → 扫描设备 → 生成 CDI 配置到 `/var/run/cdi`
   - 标记为就绪 → 允许容器调度
   - 容器启动 → 加载最新 CDI 配置

## 7. 基于 Kubernetes 1.31 + containerd 1.9 的使用方法

### 7.1 版本兼容性

| 组件 | 版本 | 状态 |
|------|------|------|
| Kubernetes | 1.31 | 完全支持 |
| containerd | 1.9 | 完全支持 |
| CDI 规范 | 0.5+ | 完全支持 |

### 7.2 CDI 配置与 Device Plugin 配合

**1. 配置 CDI**：
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

**2. Device Plugin 关键代码**：
```go
// 生成 CDI 配置
func generateCDIConfig(devices map[string]*Device) error {
    spec := CDISpec{
        CDIVersion: "0.5.0",
        Kind:       "ub.com/rdma",
        Devices:    make([]DeviceEntry, 0),
    }

    for _, dev := range devices {
        spec.Devices = append(spec.Devices, DeviceEntry{
            Name: dev.ID,
            DeviceNodes: []DeviceNode{
                {
                    Path:     dev.Path,
                    ContainerPath: dev.Path,
                    Permissions:   "rwm",
                },
            },
        })
    }

    data, _ := json.MarshalIndent(spec, "", "  ")
    tempFile := "/var/run/cdi/ub-rdma.yaml.tmp"
    ioutil.WriteFile(tempFile, data, 0644)
    os.Rename(tempFile, "/var/run/cdi/ub-rdma.yaml")
    return nil
}

// 分配设备时返回 CDI 引用
func Allocate(req *v1beta1.AllocateRequest) (*v1beta1.AllocateResponse, error) {
    resp := &v1beta1.AllocateResponse{}
    for _, id := range req.DevicesIDs {
        resp.ContainerResponses = append(resp.ContainerResponses, &v1beta1.ContainerAllocateResponse{
            CDIDevices: []*v1beta1.CDIDevice{
                {
                    Kind: "ub.com/rdma",
                    Name: id,
                },
            },
        })
    }
    return resp, nil
}
```

**3. Pod 使用示例**：
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
        ub.com/rdma: 1
      limits:
        ub.com/rdma: 1
```

