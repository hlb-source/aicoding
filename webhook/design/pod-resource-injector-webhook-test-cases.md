# Pod 资源限制自动注入 Webhook 测试用例

本文档基于 `design/pod-resource-injector-webhook.md` 中的设计，定义 Webhook 的测试用例。测试目标包括过滤逻辑、注入行为、高可用、性能和证书加载方案。

## 1. 目标

- 验证 Webhook 仅处理 Pod 创建请求
- 验证 `namespaceSelector` 和 `nodeSelector` 组合过滤逻辑
- 验证符合条件的 Pod 能正确注入 `unifiedbus.com/ub_net_device: 1`
- 验证不符合条件的 Pod 不被修改
- 验证 Webhook 部署 2 副本并支持负载分担
- 验证 TLS 证书不依赖 Kubernetes Secret
- 验证并发创建 100 个 Pod 的性能符合要求
- 验证 Webhook 服务异常时的处理策略（failurePolicy）

## 2. 测试环境准备

1. 部署 Webhook 服务，确保 `MutatingWebhookConfiguration` 只处理 `pods` 创建操作。
2. 配置 `failurePolicy: Fail`，确保 Webhook 服务异常时 Pod 创建会被拒绝。
3. 如果使用 `namespaceSelector`，配置为只匹配测试命名空间，例如 `webhook-test`。
4. 配置 Webhook 运行 2 个副本并通过 Service 暴露 8443 端口。
5. 配置 Pod 反亲和性，确保副本分布在不同节点。
6. 文件挂载：使用 hostPath 挂载主机的 `/etc/tls` 目录。

## 3. 测试用例

### 3.1 场景一：创建带有指定 NodeSelector 的 Pod

- **测试步骤**：创建一个带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod
- **预期结果**：Pod 被成功创建，并且 `resource.limits` 中包含 `unifiedbus.com/ub_net_device: 1` 配置
- **验证方法**：
  ```bash
  kubectl get pod <pod-name> -o yaml | grep -A 5 resources.limits
  ```
  确认输出中包含 `unifiedbus.com/ub_net_device: "1"`

### 3.2 场景二：创建不带有指定 NodeSelector 的 Pod

- **测试步骤**：创建一个不带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod
- **预期结果**：Pod 被成功创建，但 `resource.limits` 中不包含 `unifiedbus.com/ub_net_device: 1` 配置
- **验证方法**：
  ```bash
  kubectl get pod <pod-name> -o yaml | grep unifiedbus.com/ub_net_device
  ```
  确认输出为空

### 3.3 场景三：创建带有部分 NodeSelector 标签的 Pod

- **测试步骤**：创建一个带有部分 NodeSelector 标签但不包含 `topology.kubernetes.io/zone: supernode` 的 Pod
- **预期结果**：Pod 被成功创建，但 `resource.limits` 中不包含 `unifiedbus.com/ub_net_device: 1` 配置
- **验证方法**：
  ```bash
  kubectl get pod <pod-name> -o yaml | grep unifiedbus.com/ub_net_device
  ```
  确认输出为空

### 3.4 场景四：并发创建100个Pod的性能测试

- **测试步骤**：并发创建100个带有 `topology.kubernetes.io/zone: supernode` NodeSelector 的 Pod
- **预期结果**：所有 Pod 被成功创建，并且 Webhook 处理导致的时间增加不超过100ms
- **验证方法**：
  ```bash
  # 使用脚本并发创建100个Pod
  for i in {1..100}; do
    kubectl run test-pod-$i --image=nginx --overrides='{"spec":{"nodeSelector":{"topology.kubernetes.io/zone":"supernode"}}}' &
  done
  wait
  
  # 检查所有Pod是否创建成功
  kubectl get pods | grep test-pod | wc -l
  ```
  确认所有100个Pod都创建成功，且没有明显的延迟

### 3.5 场景五：Webhook 服务异常时的处理（failurePolicy: Fail）

- **测试步骤**：
  1. 配置 `failurePolicy: Fail`
  2. 停止或删除 Webhook 服务的所有副本
  3. 尝试创建一个新的 Pod
- **预期结果**：Pod 创建请求被拒绝，返回错误信息
- **验证方法**：
  ```bash
  # 停止 Webhook 服务
  kubectl scale deployment pod-resource-injector --replicas=0
  
  # 尝试创建 Pod
  kubectl run test-pod --image=nginx
  ```
  确认 Pod 创建失败，并显示与 Webhook 相关的错误信息

### 3.6 场景六：Webhook 只处理 Pod 创建请求

- **前提**：Webhook 配置 `operations: ["CREATE"]`。
- **步骤**：更新已存在 Pod（例如修改标签）并删除 Pod。
- **预期**：Webhook 不会拦截 Pod 更新或删除操作。
- **验证**：API Server 日志/AdmissionReview 请求中不存在更新或删除事件触发该 Webhook。

### 3.7 场景七：2 副本部署和负载分担验证

- **前提**：Webhook Deployment 运行 2 个副本，配置 Pod 反亲和性。
- **步骤**：连续创建多个符合条件的 Pod，并观察两个副本是否都接收到请求。
- **预期**：API Server 将请求分发到可用副本，且两个 Pod 副本均正常运行。
- **验证**：
  ```bash
  # 查看副本状态
  kubectl get pods -l app=pod-resource-injector -o wide
  
  # 查看副本日志
  kubectl logs -l app=pod-resource-injector --tail=100
  ```
  确认两个副本都正常运行，且都处理了请求

### 3.8 场景八：TLS 证书挂载验证

- **前提**：Webhook Pod 使用 hostPath 挂载主机的 `/etc/tls` 目录。
- **步骤**：
  1. 在主机的 `/etc/tls` 目录放置 TLS 证书（tls.crt 和 tls.key）
  2. 重启 Webhook Pod
  3. 确认 Pod 启动后能够读取证书并正常注册 Webhook
- **预期**：Webhook 服务启动成功且与 API Server 的 TLS 连接正常。
- **验证**：
  ```bash
  # 检查 Pod 日志
  kubectl logs -l app=pod-resource-injector
  
  # 检查 Webhook 配置状态
  kubectl get mutatingwebhookconfigurations pod-resource-injector
  ```

### 3.9 场景九：RBAC 权限验证

- **测试步骤**：
  1. 检查 ClusterRole 配置，确认只有 `pods` 资源的 `patch` 权限
  2. 验证 Webhook 服务可以正常运行，没有其他权限需求
- **预期结果**：Webhook 服务使用最小权限集运行，只有 `patch` pods 的权限
- **验证方法**：
  ```bash
  kubectl get clusterrole pod-resource-injector-role -o yaml
  ```
  确认 rules 中只有 `resources: ["pods"]` 和 `verbs: ["patch"]`

## 4. 边界测试

- 验证 Pod 中已有 `resources.limits` 内容时仍能正确合并 `unifiedbus.com/ub_net_device: 1`。
- 验证 Pod 不含 `spec.nodeSelector` 时，Webhook 不注入资源限制。
- 验证当一个副本故障时，另一个副本继续处理请求。
- 验证 InitContainers 也能正确注入资源限制。

## 5. 结果记录

建议为每个用例记录：

| 用例编号 | 描述 | 输入条件 | 预期结果 | 实际结果 | 是否通过 | 备注 |
|---------|------|---------|---------|---------|---------|------|
| TC-001 | 创建带有指定 NodeSelector 的 Pod | nodeSelector 包含 `topology.kubernetes.io/zone: supernode` | Pod 创建成功，注入资源限制 | | | |
| TC-002 | 创建不带有指定 NodeSelector 的 Pod | nodeSelector 不包含目标标签 | Pod 创建成功，不注入资源限制 | | | |
| TC-003 | 创建带有部分 NodeSelector 标签的 Pod | nodeSelector 包含其他标签 | Pod 创建成功，不注入资源限制 | | | |
| TC-004 | 并发创建100个Pod的性能测试 | 并发创建100个符合条件的 Pod | 所有 Pod 创建成功，延迟 < 100ms | | | |
| TC-005 | Webhook 服务异常时的处理 | failurePolicy: Fail，Webhook 服务停止 | Pod 创建被拒绝 | | | |
| TC-006 | Webhook 只处理 Pod 创建请求 | 更新和删除 Pod 操作 | Webhook 不拦截更新和删除 | | | |
| TC-007 | 2 副本部署和负载分担 | 创建多个 Pod | 请求分发到多个副本 | | | |
| TC-008 | TLS 证书挂载验证 | 使用 hostPath 挂载证书 | Webhook 正常启动和运行 | | | |
| TC-009 | RBAC 权限验证 | 检查 ClusterRole 配置 | 只有 pods patch 权限 | | | |
