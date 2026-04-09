package webhook

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	admissionv1 "k8s.io/api/admission/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
)

const (
	// DefaultNodeSelectorKey 默认的节点选择器键
	DefaultNodeSelectorKey = "topology.kubernetes.io/zone"
	// DefaultNodeSelectorValue 默认的节点选择器值
	DefaultNodeSelectorValue = "supernode"
	// ResourceName 要注入的资源名称
	ResourceName = "unifiedbus.com/ub_net_device"
	// ResourceValue 要注入的资源值
	ResourceValue = "1"
)

// 从环境变量读取需要匹配的nodeSelector标签,支持动态配置
func getRequiredNodeSelector() map[string]string {
	key := os.Getenv("NODE_SELECTOR_KEY")
	if key == "" {
		key = DefaultNodeSelectorKey
	}

	value := os.Getenv("NODE_SELECTOR_VALUE")
	if value == "" {
		value = DefaultNodeSelectorValue
	}

	return map[string]string{key: value}
}

// 检查Pod的nodeSelector是否匹配
func matchesNodeSelector(pod *corev1.Pod) bool {
	requiredSelector := getRequiredNodeSelector()

	if pod.Spec.NodeSelector == nil {
		return false
	}

	for key, value := range requiredSelector {
		if pod.Spec.NodeSelector[key] != value {
			return false
		}
	}

	return true
}

// 生成patch操作
func generatePatchOperations(pod *corev1.Pod) []map[string]interface{} {
	var patchOps []map[string]interface{}

	// 处理 Containers
	for i, container := range pod.Spec.Containers {
		patchOps = append(patchOps, generateContainerPatchOps(container, fmt.Sprintf("/spec/containers/%d", i))...)
	}

	// 不处理 InitContainers，只处理常规容器
	// 根据设计要求，只对常规容器注入资源限制，不修改初始化容器

	return patchOps
}

// 为单个容器生成patch操作
func generateContainerPatchOps(container corev1.Container, basePath string) []map[string]interface{} {
	var patchOps []map[string]interface{}

	resourceValue := resource.MustParse(ResourceValue)

	if container.Resources.Limits == nil {
		if container.Resources.Requests == nil {
			// Resources 为空，添加整个 resources
			patchOps = append(patchOps, map[string]interface{}{
				"op":   "add",
				"path": basePath + "/resources",
				"value": corev1.ResourceRequirements{
					Limits: corev1.ResourceList{
						corev1.ResourceName(ResourceName): resourceValue,
					},
				},
			})
		} else {
			// Resources 存在但 Limits 为空，添加 limits
			patchOps = append(patchOps, map[string]interface{}{
				"op":   "add",
				"path": basePath + "/resources/limits",
				"value": corev1.ResourceList{
					corev1.ResourceName(ResourceName): resourceValue,
				},
			})
		}
	} else if _, exists := container.Resources.Limits[corev1.ResourceName(ResourceName)]; !exists {
		// Limits 存在但没有该资源，添加键
		escapedName := strings.Replace(ResourceName, "/", "~1", -1)
		patchOps = append(patchOps, map[string]interface{}{
			"op":    "add",
			"path":  basePath + "/resources/limits/" + escapedName,
			"value": resourceValue,
		})
	}

	return patchOps
}

// HandleMutatePods 处理Pod创建请求
func HandleMutatePods(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()

	var admissionReview admissionv1.AdmissionReview
	if err := json.NewDecoder(r.Body).Decode(&admissionReview); err != nil {
		log.Printf("ERROR: Failed to decode request: %v", err)
		http.Error(w, fmt.Sprintf("Failed to decode request: %v", err), http.StatusBadRequest)
		return
	}

	if admissionReview.Request == nil {
		log.Printf("ERROR: AdmissionReview request is nil")
		http.Error(w, "AdmissionReview request is nil", http.StatusBadRequest)
		return
	}

	log.Printf("Processing AdmissionReview UID: %s, Kind: %s, Namespace: %s, Name: %s",
		admissionReview.Request.UID,
		admissionReview.Request.Kind.Kind,
		admissionReview.Request.Namespace,
		admissionReview.Request.Name)

	// 解析Pod对象
	pod := &corev1.Pod{}
	if err := json.Unmarshal(admissionReview.Request.Object.Raw, pod); err != nil {
		log.Printf("ERROR: Failed to unmarshal Pod: %v", err)
		http.Error(w, fmt.Sprintf("Failed to unmarshal Pod: %v", err), http.StatusBadRequest)
		return
	}

	log.Printf("Pod %s/%s - NodeSelector: %v", pod.Namespace, pod.Name, pod.Spec.NodeSelector)

	// 检查nodeSelector是否匹配
	if !matchesNodeSelector(pod) {
		log.Printf("Pod %s/%s does not match nodeSelector, allowing without modification", pod.Namespace, pod.Name)
		// 不匹配，直接通过
		admissionReview.Response = &admissionv1.AdmissionResponse{
			UID:     admissionReview.Request.UID,
			Allowed: true,
		}
		if err := json.NewEncoder(w).Encode(admissionReview); err != nil {
			log.Printf("ERROR: Failed to encode response: %v", err)
			http.Error(w, fmt.Sprintf("Failed to encode response: %v", err), http.StatusInternalServerError)
		}
		log.Printf("Completed processing Pod %s/%s in %v (no modification)", pod.Namespace, pod.Name, time.Since(startTime))
		return
	}

	log.Printf("Pod %s/%s matches nodeSelector, generating patch operations", pod.Namespace, pod.Name)

	// 生成patch操作
	patchOps := generatePatchOperations(pod)

	// 如果没有需要修改的，直接通过
	if len(patchOps) == 0 {
		log.Printf("Pod %s/%s has no containers requiring modification", pod.Namespace, pod.Name)
		admissionReview.Response = &admissionv1.AdmissionResponse{
			UID:     admissionReview.Request.UID,
			Allowed: true,
		}
		if err := json.NewEncoder(w).Encode(admissionReview); err != nil {
			log.Printf("ERROR: Failed to encode response: %v", err)
			http.Error(w, fmt.Sprintf("Failed to encode response: %v", err), http.StatusInternalServerError)
		}
		log.Printf("Completed processing Pod %s/%s in %v (no patch needed)", pod.Namespace, pod.Name, time.Since(startTime))
		return
	}

	log.Printf("Generated %d patch operations for Pod %s/%s", len(patchOps), pod.Namespace, pod.Name)

	// 生成patch
	patchBytes, err := json.Marshal(patchOps)
	if err != nil {
		log.Printf("ERROR: Failed to marshal patch: %v", err)
		http.Error(w, fmt.Sprintf("Failed to marshal patch: %v", err), http.StatusInternalServerError)
		return
	}

	// 构建响应
	admissionReview.Response = &admissionv1.AdmissionResponse{
		UID:     admissionReview.Request.UID,
		Allowed: true,
		Patch:   patchBytes,
		PatchType: func() *admissionv1.PatchType {
			pt := admissionv1.PatchTypeJSONPatch
			return &pt
		}(),
	}

	// 发送响应
	if err := json.NewEncoder(w).Encode(admissionReview); err != nil {
		log.Printf("ERROR: Failed to encode response: %v", err)
		http.Error(w, fmt.Sprintf("Failed to encode response: %v", err), http.StatusInternalServerError)
		return
	}

	log.Printf("Successfully processed Pod %s/%s in %v with %d patch operations",
		pod.Namespace, pod.Name, time.Since(startTime), len(patchOps))
}
