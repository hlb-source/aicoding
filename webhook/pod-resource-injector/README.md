# Pod 资源限制自动注入 Webhook

## 项目简介

本项目实现了一个 Kubernetes 准入 Webhook，用于自动拦截 Pod 创建请求，并在符合特定节点选择条件的 Pod 中注入 `unifiedbus.com/ub_net_device: 1` 资源限制配置。该 Webhook 支持根据 NodeSelector 过滤，确保只对特定节点上的 Pod 进行处理，避免对所有 Pod 创建请求造成不必要的处理开销。

## 功能特性

- **自动注入**：自动为符合条件的 Pod 注入 `unifiedbus.com/ub_net_device: 1` 资源限制配置
- **精准过滤**：支持 namespaceSelector 和 NodeSelector 双层过滤机制
- **可配置性**：通过环境变量动态配置过滤条件，无需重新编译
- **安全性**：使用 TLS 证书确保与 Kubernetes API 服务器之间的通信安全
- **高可用性**：支持多副本部署，配备健康检查和就绪探针
- **可观测性**：完善的日志记录，便于问题排查和性能监控
- **性能优化**：优化处理逻辑，确保并发创建100个Pod时，时间增加不超过100ms
- **最小权限**：使用专用 ServiceAccount 和 RBAC，遵循最小权限原则

## 技术栈

- **语言**：Go 1.20+
- **框架**：标准库 net/http
- **依赖**：
  - k8s.io/api v0.19.9
  - k8s.io/apimachinery v0.19.9
  - sigs.k8s.io/controller-runtime v0.10.0

## 目录结构

```
pod-resource-injector/
├── cmd/              # 命令行入口
│   └── main.go       # 主程序
├── internal/         # 内部包
│   └── webhook/      # Webhook 实现
│       ├── webhook.go        # Webhook 核心逻辑
│       └── webhook_test.go   # 测试代码
├── deploy/           # 部署配置
│   ├── deployment.yaml       # 服务部署
│   ├── rbac.yaml             # RBAC 配置
│   └── webhook.yaml          # Webhook 配置
├── go.mod            # Go 模块文件
└── README.md         # 项目说明
```

## 部署步骤

### 1. 构建镜像

```bash
# 构建镜像
docker build -t pod-resource-injector:latest .

# 推送镜像到镜像仓库（如果需要）
docker push pod-resource-injector:latest
```

### 2. 准备 TLS 证书

使用 openssl 命令生成 TLS 证书：

```bash
# 创建证书目录
mkdir -p certs

# 生成 CA 证书
openssl genrsa -out certs/ca.key 2048
openssl req -x509 -new -nodes -key certs/ca.key -subj "/CN=pod-resource-injector-ca" -days 365 -out certs/ca.crt

# 生成服务器证书
openssl genrsa -out certs/server.key 2048
openssl req -new -key certs/server.key -subj "/CN=pod-resource-injector.default.svc" -out certs/server.csr
openssl x509 -req -in certs/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial -out certs/server.crt -days 365

# 复制证书到主机目录
mkdir -p /etc/tls
cp certs/server.crt /etc/tls/
cp certs/server.key /etc/tls/

# 提取 CA 证书内容用于 webhook 配置
CA_BUNDLE=$(cat certs/ca.crt | base64 | tr -d '\n')
```

### 3. 部署服务

```bash
# 部署 RBAC
kubectl apply -f deploy/rbac.yaml

# 部署服务
kubectl apply -f deploy/deployment.yaml

# 更新 webhook 配置中的 CA_BUNDLE
sed -i "s/<CA_BUNDLE>/$CA_BUNDLE/g" deploy/webhook.yaml

# 部署 webhook 配置
kubectl apply -f deploy/webhook.yaml
```

### 4. 验证部署

```bash
# 检查 Pod 状态
kubectl get pods -l app=pod-resource-injector

# 检查健康状态
kubectl exec -it <pod-name> -- curl -k https://localhost:8443/healthz

# 检查就绪状态
kubectl exec -it <pod-name> -- curl -k https://localhost:8443/readyz

# 查看日志
kubectl logs -l app=pod-resource-injector
```

## 测试

### 运行单元测试

```bash
go test ./internal/webhook/...
```

### 功能测试

1. **测试场景一**：创建带有指定 NodeSelector 的 Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: test-pod-with-node-selector
  namespace: kube-system  # 必须在 kube-system 或 ub-system 命名空间
  labels:
    app: test
spec:
  nodeSelector:
    topology.kubernetes.io/zone: "supernode"
  containers:
  - name: nginx
    image: nginx:latest
```

2. **测试场景二**：创建不带有指定 NodeSelector 的 Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: test-pod-without-node-selector
  namespace: kube-system  # 必须在 kube-system 或 ub-system 命名空间
  labels:
    app: test
spec:
  containers:
  - name: nginx
    image: nginx:latest
```

3. **测试场景三**：并发创建100个Pod的性能测试

使用脚本并发创建100个带有 NodeSelector 的 Pod，验证 Webhook 处理导致的时间增加是否在100ms以内：

```bash
# 使用脚本并发创建100个Pod
for i in {1..100}; do
  kubectl run test-pod-$i --image=nginx --namespace=kube-system --overrides='{"spec":{"nodeSelector":{"topology.kubernetes.io/zone":"supernode"}}}' &
done
wait

# 检查所有Pod是否创建成功
kubectl get pods -n kube-system | grep test-pod | wc -l
```

## 维护

- **监控**：监控 Webhook 服务的运行状态和响应时间
- **日志**：配置适当的日志记录，便于问题排查
- **更新**：定期更新 Webhook 服务版本和依赖
- **备份**：备份 Webhook 配置和 TLS 证书
- **证书管理**：建立证书过期提醒机制，手动更新即将过期的证书

## 风险评估

- **性能风险**：Webhook 处理时间过长可能影响 Pod 创建速度
- **可用性风险**：Webhook 服务故障可能导致 Pod 创建失败
- **安全风险**：TLS 证书过期或泄露可能导致安全问题

## 风险缓解措施

- **性能优化**：优化 Webhook 处理逻辑，确保并发创建100个Pod时，时间增加不超过100ms
- **高可用部署**：部署多个副本，配置 Pod 反亲和性，确保服务可用性
- **证书管理**：建立证书过期提醒机制，手动更新即将过期的证书
- **错误处理**：实现完善的错误处理机制，确保即使 Webhook 故障也能给出明确的错误信息

## 配置说明

### 环境变量配置

Webhook 支持通过环境变量自定义 NodeSelector 过滤条件，这些变量在 `deploy/deployment.yaml` 中直接配置：

- `NODE_SELECTOR_KEY`: NodeSelector 的键名（默认：`topology.kubernetes.io/zone`）
- `NODE_SELECTOR_VALUE`: NodeSelector 的值（默认：`supernode`）

如需修改这些值，直接编辑 `deploy/deployment.yaml` 中的 env 部分：

```yaml
env:
- name: NODE_SELECTOR_KEY
  value: "your-custom-key"
- name: NODE_SELECTOR_VALUE
  value: "your-custom-value"
```

修改后重新应用部署即可生效：

```bash
kubectl apply -f deploy/deployment.yaml
```

### Webhook 配置

`deploy/webhook.yaml` 中的关键配置项：

- `namespaceSelector`: 限制 webhook 只在 `kube-system` 和 `ub-system` 命名空间触发
- `failurePolicy: Fail`: webhook 失败时阻止 Pod 创建
- `timeoutSeconds: 5`: webhook 超时时间
- `rules`: 只处理 Pod 的 CREATE 操作
- `scope: "Namespaced"`: 仅匹配命名空间级资源

### 命名空间限制

Webhook 仅处理以下命名空间中的 Pod 创建请求：
- `kube-system`
- `ub-system`

其他命名空间的 Pod 创建请求不会被 Webhook 处理。

### 节点选择限制

Webhook 仅为带有以下 NodeSelector 的 Pod 注入资源限制：
- `topology.kubernetes.io/zone: supernode`

其他 Pod 不会被修改。
