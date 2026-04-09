# RFC: Pod 资源限制自动注入 Webhook 设计

## 1. 摘要

本文档定义了一个 Kubernetes 准入 Webhook 的设计方案，用于自动拦截 Pod 创建请求，并在符合特定节点选择条件的 Pod 中注入 `unifiedbus.com/ub_net_device: 1` 资源限制配置。该 Webhook 支持根据 NodeSelector 过滤，确保只对特定节点上的 Pod 进行处理，避免对所有 Pod 创建请求造成不必要的处理开销。

## 2. 动机

在 Kubernetes 集群中，某些特定节点可能需要 Pod 配置特定的网络设备资源限制。手动为每个 Pod 添加这些配置既繁琐又容易出错，因此需要一个自动化机制来处理这个问题。

本设计旨在通过准入 Webhook 实现自动注入资源限制配置，同时通过 NodeSelector 过滤确保只对特定节点上的 Pod 进行处理，避免对所有 Pod 创建请求造成不必要的处理开销。

### 2.1 用户场景

1. **集群管理员**：作为集群管理员，我希望确保调度到具有特定网络设备的节点上的 Pod 自动获得所需的资源限制，而无需手动干预。
2. **应用开发者**：作为应用开发者，我希望我的 Pod 在调度到适当节点时自动获得必要的网络设备资源限制，而不需要修改我的 Pod 清单。
3. **集群管理员**：作为集群管理员，我希望 Webhook 处理过程不会显著增加 Pod 创建时间，确保集群的整体性能不受影响。

## 3. 目标

- **自动化**：自动为符合条件的 Pod 注入 `unifiedbus.com/ub_net_device: 1` 资源限制配置
- **精准过滤**：只处理带有特定 NodeSelector 的 Pod 创建请求
- **安全性**：确保 Webhook 与 Kubernetes API 服务器之间的通信安全
- **高可用性**：确保 Webhook 服务的高可用性
- **性能**：并发创建100个Pod时，Webhook处理导致的时间增加应在100ms以内

## 4. 非目标

- **修改现有 Pod**：Webhook 仅处理 Pod 创建请求，不修改现有 Pod
- **支持其他资源类型**：Webhook 专门设计用于 Pod 资源
- **动态配置更新**：Webhook 配置不会在运行时动态更新

## 4.1 约束与限制

### 4.1.1 高可用性约束

**Webhook 服务异常时的影响**：
- 配置 `failurePolicy: Fail` 时，如果 Webhook 服务异常或不可用，所有 Pod 创建请求将被拒绝
- 这意味着 Webhook 服务成为集群的关键依赖组件，必须确保其高可用性
- 建议部署多个副本，并配置 Pod 反亲和性，确保服务持续可用

**缓解措施**：
- 部署 2 个以上副本，确保单点故障不影响服务
- 配置 Pod 反亲和性，避免所有副本部署在同一节点
- 配置适当的资源限制和监控告警，及时发现并处理服务异常

### 4.1.2 资源范围约束

**命名空间限制**：
- Webhook 仅处理 `kube-system` 和 `ub-system` 命名空间中的 Pod 创建请求
- 其他命名空间的 Pod 创建请求不会被 Webhook 处理

**操作限制**：
- Webhook 仅监听 Pod 的 `CREATE` 操作，不处理更新或删除操作
- 只有在创建新 Pod 时才会触发 Webhook 调用

**资源类型限制**：
- Webhook 专门设计用于 Pod 资源，不处理其他资源类型
- 配置 `scope: "Namespaced"`，仅匹配命名空间级资源

**节点选择限制**：
- 只有带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod 才会被注入资源限制
- 其他 Pod 不会被修改

### 4.1.3 版本兼容性约束

**Kubernetes 版本**：
- Webhook 设计和测试基于 Kubernetes 1.19.9 版本
- 使用对应版本的 Kubernetes SDK (`k8s.io/api v0.19.9`、`k8s.io/apimachinery v0.19.9`)
- 在其他 Kubernetes 版本上可能需要调整配置或代码

**Go 版本**：
- 开发和测试使用 Go 1.20 版本
- 建议使用相同或兼容的 Go 版本进行构建

## 5. 提案

### 5.1 概述

提议的解决方案是一个 MutatingAdmissionWebhook，它拦截 Pod 创建请求，检查 Pod 是否具有特定的节点选择器标签，如果满足条件，则注入所需的资源限制配置。

### 5.2 设计细节

#### 5.2.1 Webhook 配置

**MutatingWebhookConfiguration**

- **名称**：pod-resource-injector
- **规则**：只处理 Pod 创建请求
- **服务**：指向 Webhook 服务的端点
- **namespaceSelector**：可选地限制到特定命名空间集合，减少无关 Pod 的触发范围
- **CA 证书**：用于验证 Webhook 服务的 TLS 证书

#### 5.2.2 Webhook 服务

**核心功能**

- **请求处理**：接收和处理 AdmissionReview 请求
- **Pod 解析**：从请求中解析 Pod 对象
- **过滤逻辑**：检查 Pod 的 `nodeSelector` 是否包含指定的标签
- **资源注入**：在符合条件的 Pod 中添加资源限制配置
- **响应生成**：生成包含修改的 AdmissionReview 响应

#### 5.2.3 过滤机制

- **namespaceSelector 过滤**：在 Webhook 配置层可选地限制到特定命名空间集合，减少无关 Pod 的触发范围。
- **NodeSelector 过滤**：在 Webhook 处理逻辑中检查 Pod 的 `nodeSelector` 字段是否包含特定的标签。
- **默认配置**：默认检查 `topology.kubernetes.io/zone: supernode` 标签
- **可配置性**：支持通过环境变量或配置文件调整过滤条件
- **实现方式**：
  1. 若配置了 `namespaceSelector`，首先由 API Server 在触发阶段过滤命名空间；
  2. Webhook 接收到 Pod 创建请求后，解析 `spec.nodeSelector` 字段，与配置条件比较；
  3. 只有当 Pod 的 namespace 和 NodeSelector 都满足要求时，才会注入资源限制。
- **性能优化**：前置 `namespaceSelector` 过滤减少不必要的触发，后续 `nodeSelector` 过滤在 Pod 解析后立即执行，对于不符合条件的 Pod直接返回允许通过的响应，避免不必要的处理开销。

#### 5.2.4 部署配置

**服务部署**

- **部署方式**：使用 Kubernetes Deployment
- **副本数**：2 个副本确保高可用性
- **负载模式**：Webhook 服务采用业务处理负载分担模式，多个副本共享请求流量，避免单点处理瓶颈
- **请求分发**：通过 Kubernetes Service 或 API Server 内部负载均衡将 Admission 请求分发给可用副本
- **端口**：8443（TLS）
- **TLS 配置**：使用 Pod 内部挂载的证书文件或外部证书管理方案，不使用 Kubernetes Secret 存储证书

**TLS 证书**

- **生成方式**：手动使用 openssl 命令生成或通过外部证书管理器生成
- **证书加载**：通过镜像、initContainer 或 CSI 驱动将证书文件注入到 Pod 中
- **更新策略**：手动更新证书文件或由证书管理系统自动更新

**业务处理模式**

- **无状态处理**：Webhook 实例设计为无状态服务，任何副本均可独立处理 AdmissionReview 请求。
- **负载分担**：采用 Kubernetes Service / API Server 负载分发机制，实现请求在副本间均衡分担。
- **高可用**：当一个副本故障时，其他副本继续处理请求，保证业务可用性。

### 5.3 实现细节

#### 5.3.1 技术栈

- **语言**：Go 1.20+
- **框架**：sigs.k8s.io/controller-runtime
- **依赖**：
  - k8s.io/api
  - k8s.io/apimachinery
  - k8s.io/client-go

#### 5.3.2 核心逻辑

**请求处理流程**
1. 接收 AdmissionReview 请求
2. 解析 Pod 对象
3. 检查 NodeSelector：验证 Pod 的 `nodeSelector` 是否包含所有指定的标签
4. 过滤处理：对于不符合 NodeSelector 条件的 Pod，直接生成允许通过的响应，不进行后续处理
5. 注入资源限制：对于符合条件的 Pod，在其 `resource.limits` 中添加 `unifiedbus.com/ub_net_device: 1` 配置
6. 生成响应：返回包含修改的 AdmissionReview 响应

**资源注入逻辑**

- 遍历 Pod 中的所有容器
- 检查每个容器的 `resources.limits` 是否存在
- 如果不存在，创建一个新的资源限制对象
- 添加 `unifiedbus.com/ub_net_device: 1` 配置

#### 5.3.3 安全考虑

**TLS 加密**

- Webhook 服务使用 TLS 证书确保与 API 服务器的通信安全
- 证书通过 openssl 命令手动生成和管理

**权限控制**

- Webhook 服务使用 ServiceAccount 运行
- **不需要 RBAC 权限**：Admission Webhook 通过 AdmissionReview 响应中的 Patch 字段实现修改，而不是直接调用 Kubernetes API

**权限说明**：
- Webhook 监听 Pod 创建事件：由 Kubernetes API 服务器主动推送 AdmissionReview 请求
- Webhook 修改 Pod 配置：通过在 AdmissionReview 响应中返回 Patch 操作来实现，不需要直接调用 Kubernetes API
- 最小权限原则：只使用 ServiceAccount 作为身份标识，不授予任何额外权限

**错误处理**

- 实现完善的错误处理机制
- 确保在处理请求时不会因为错误而影响整个 Pod 创建流程

## 6. 测试计划

### 6.1 测试场景

**场景一**：创建带有指定 NodeSelector 的 Pod
- **测试步骤**：创建一个带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod
- **预期结果**：Pod 被成功创建，并且 `resource.limits` 中包含 `unifiedbus.com/ub_net_device: 1` 配置

**场景二**：创建不带有指定 NodeSelector 的 Pod
- **测试步骤**：创建一个不带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod
- **预期结果**：Pod 被成功创建，但 `resource.limits` 中不包含 `unifiedbus.com/ub_net_device: 1` 配置

**场景三**：创建带有部分 NodeSelector 标签的 Pod
- **测试步骤**：创建一个带有部分 NodeSelector 标签但不包含 `topology.kubernetes.io/zone: supernode` 的 Pod
- **预期结果**：Pod 被成功创建，但 `resource.limits` 中不包含 `unifiedbus.com/ub_net_device: 1` 配置

**场景四**：并发创建100个Pod的性能测试
- **测试步骤**：并发创建100个带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod
- **预期结果**：所有 Pod 被成功创建，并且 Webhook 处理导致的时间增加不超过100ms

### 6.2 验证方法

- 使用 `kubectl describe pod` 命令查看 Pod 的资源限制配置
- 检查 Pod 事件日志，确认 Webhook 处理情况
- 使用 `kubectl get mutatingwebhookconfigurations` 命令检查 Webhook 配置

## 7. 部署与维护

### 7.1 部署步骤

1. **构建镜像**：构建 Webhook 服务镜像
2. **创建 TLS 证书**：使用 openssl 命令手动生成 TLS 证书，或通过外部证书管理系统生成
3. **证书注入**：将证书文件通过镜像、initContainer、或 CSI 驱动挂载到 Pod 中，不使用 Kubernetes Secret 存储
4. **部署服务**：部署 Webhook 服务和相关资源（包括 ServiceAccount）
5. **配置 Webhook**：创建 MutatingWebhookConfiguration

### 7.2 维护建议

- **监控**：监控 Webhook 服务的运行状态和响应时间
- **日志**：配置适当的日志记录，便于问题排查
- **更新**：定期更新 Webhook 服务版本和依赖
- **备份**：备份 Webhook 配置和 TLS 证书
- **证书管理**：建立证书过期提醒机制，手动更新即将过期的证书

## 8. 风险评估

### 8.1 潜在风险

- **性能风险**：Webhook 处理时间过长可能影响 Pod 创建速度
- **可用性风险**：Webhook 服务故障可能导致 Pod 创建失败
- **安全风险**：TLS 证书过期或泄露可能导致安全问题

### 8.2 风险缓解措施

- **性能优化**：优化 Webhook 处理逻辑，确保并发创建100个Pod时，时间增加不超过100ms
- **高可用部署**：部署多个副本，确保服务可用性
- **证书管理**：建立证书过期提醒机制，手动更新即将过期的证书
- **错误处理**：实现完善的错误处理机制，确保即使 Webhook 故障也不会影响 Pod 创建

## 9. 结论

本设计方案实现了一个功能完整的 Kubernetes 准入 Webhook，能够根据 NodeSelector 过滤 Pod 创建请求，并在符合条件的 Pod 中自动注入 `unifiedbus.com/ub_net_device: 1` 资源限制配置。该方案具有以下优点：

1. **精准过滤**：只处理带有特定 NodeSelector 的 Pod 请求，避免对所有 Pod 创建请求进行处理
2. **自动注入**：无需手动修改 Pod 配置，自动添加所需的资源限制
3. **安全可靠**：使用 TLS 加密确保通信安全，实现完善的错误处理
4. **高可用**：通过多副本部署确保服务可用性
5. **可配置**：支持通过配置调整过滤条件，适应不同部署环境

该方案可以有效简化集群管理，确保特定节点上的 Pod 都能正确配置所需的网络设备资源限制。

## 10. 参考资料

- [Kubernetes Admission Webhook 文档](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [sigs.k8s.io/controller-runtime 文档](https://pkg.go.dev/sigs.k8s.io/controller-runtime)

