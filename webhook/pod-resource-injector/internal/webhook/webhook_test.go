package webhook

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	admissionv1 "k8s.io/api/admission/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

func TestMatchesNodeSelector(t *testing.T) {
	tests := []struct {
		name         string
		nodeSelector map[string]string
		labels       map[string]string
		expected     bool
	}{
		{
			name: "Pod with matching nodeSelector",
			nodeSelector: map[string]string{
				"topology.kubernetes.io/zone": "supernode",
			},
			labels:     nil,
			expected: true,
		},
		{
			name: "Pod with non-matching nodeSelector",
			nodeSelector: map[string]string{
				"topology.kubernetes.io/zone": "other-zone",
			},
			labels:     nil,
			expected: false,
		},
		{
			name:         "Pod with no nodeSelector and no labels",
			nodeSelector: nil,
			labels:       nil,
			expected:     false,
		},
		{
			name: "Pod with partial nodeSelector",
			nodeSelector: map[string]string{
				"other-label": "true",
			},
			labels:     nil,
			expected: false,
		},
		{
			name:         "Pod with matching labels (from Deployment)",
			nodeSelector: nil,
			labels: map[string]string{
				"topology.kubernetes.io/zone": "supernode",
			},
			expected: true,
		},
		{
			name:         "Pod with non-matching labels",
			nodeSelector: nil,
			labels: map[string]string{
				"topology.kubernetes.io/zone": "other-zone",
			},
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pod := &corev1.Pod{
				ObjectMeta: metav1.ObjectMeta{
					Labels: tt.labels,
				},
				Spec: corev1.PodSpec{
					NodeSelector: tt.nodeSelector,
				},
			}

			result := matchesNodeSelector(pod)
			if result != tt.expected {
				t.Errorf("matchesNodeSelector() = %v, want %v", result, tt.expected)
			}
		})
	}
}

func TestGeneratePatchOperations(t *testing.T) {
	tests := []struct {
		name        string
		containers  []corev1.Container
		expectedOps int
	}{
		{
			name: "Container with no resources",
			containers: []corev1.Container{
				{
					Name:  "test-container",
					Image: "nginx",
				},
			},
			expectedOps: 1,
		},
		{
			name: "Container with resources but no ub_net_device",
			containers: []corev1.Container{
				{
					Name:  "test-container",
					Image: "nginx",
					Resources: corev1.ResourceRequirements{
						Limits: corev1.ResourceList{
							"cpu": resource.MustParse("1"),
						},
					},
				},
			},
			expectedOps: 1,
		},
		{
			name: "Container with ub_net_device already set",
			containers: []corev1.Container{
				{
					Name:  "test-container",
					Image: "nginx",
					Resources: corev1.ResourceRequirements{
						Limits: corev1.ResourceList{
							"unifiedbus.com/ub_net_device": resource.MustParse("1"),
						},
					},
				},
			},
			expectedOps: 0,
		},
		{
			name: "Multiple containers",
			containers: []corev1.Container{
				{
					Name:  "container1",
					Image: "nginx",
				},
				{
					Name:  "container2",
					Image: "redis",
					Resources: corev1.ResourceRequirements{
						Limits: corev1.ResourceList{
							"cpu": resource.MustParse("1"),
						},
					},
				},
				{
					Name:  "container3",
					Image: "mysql",
					Resources: corev1.ResourceRequirements{
						Limits: corev1.ResourceList{
							"unifiedbus.com/ub_net_device": resource.MustParse("1"),
						},
					},
				},
			},
			expectedOps: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pod := &corev1.Pod{
				Spec: corev1.PodSpec{
					Containers: tt.containers,
				},
			}

			ops := generatePatchOperations(pod)
			if len(ops) != tt.expectedOps {
				t.Errorf("generatePatchOperations() returned %d operations, want %d", len(ops), tt.expectedOps)
			}
		})
	}
}

func TestGetRequiredNodeSelector(t *testing.T) {
	// 保存原始环境变量
	originalKey := os.Getenv("NODE_SELECTOR_KEY")
	originalValue := os.Getenv("NODE_SELECTOR_VALUE")
	defer func() {
		// 恢复原始环境变量
		if originalKey != "" {
			os.Setenv("NODE_SELECTOR_KEY", originalKey)
		} else {
			os.Unsetenv("NODE_SELECTOR_KEY")
		}
		if originalValue != "" {
			os.Setenv("NODE_SELECTOR_VALUE", originalValue)
		} else {
			os.Unsetenv("NODE_SELECTOR_VALUE")
		}
	}()

	tests := []struct {
		name          string
		keyEnv        string
		valueEnv      string
		expectedKey   string
		expectedValue string
	}{
		{
			name:          "Default values when no environment variables",
			keyEnv:        "",
			valueEnv:      "",
			expectedKey:   "topology.kubernetes.io/zone",
			expectedValue: "supernode",
		},
		{
			name:          "Custom values from environment variables",
			keyEnv:        "custom-key",
			valueEnv:      "custom-value",
			expectedKey:   "custom-key",
			expectedValue: "custom-value",
		},
		{
			name:          "Only key from environment variable",
			keyEnv:        "custom-key",
			valueEnv:      "",
			expectedKey:   "custom-key",
			expectedValue: "supernode",
		},
		{
			name:          "Only value from environment variable",
			keyEnv:        "",
			valueEnv:      "custom-value",
			expectedKey:   "topology.kubernetes.io/zone",
			expectedValue: "custom-value",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// 设置环境变量
			if tt.keyEnv != "" {
				os.Setenv("NODE_SELECTOR_KEY", tt.keyEnv)
			} else {
				os.Unsetenv("NODE_SELECTOR_KEY")
			}
			if tt.valueEnv != "" {
				os.Setenv("NODE_SELECTOR_VALUE", tt.valueEnv)
			} else {
				os.Unsetenv("NODE_SELECTOR_VALUE")
			}

			result := getRequiredNodeSelector()
			if len(result) != 1 {
				t.Errorf("Expected 1 key-value pair, got %d", len(result))
			}

			value, exists := result[tt.expectedKey]
			if !exists {
				t.Errorf("Expected key %s not found in result", tt.expectedKey)
			}
			if value != tt.expectedValue {
				t.Errorf("Expected value %s for key %s, got %s", tt.expectedValue, tt.expectedKey, value)
			}
		})
	}
}

func TestHandleMutatePods(t *testing.T) {
	// 测试用例：带有匹配 nodeSelector 的 Pod
	t.Run("Pod with matching nodeSelector", func(t *testing.T) {
		pod := &corev1.Pod{
			Spec: corev1.PodSpec{
				NodeSelector: map[string]string{
					"topology.kubernetes.io/zone": "supernode",
				},
				Containers: []corev1.Container{
					{
						Name:  "test-container",
						Image: "nginx",
					},
				},
			},
		}

		// 构建 AdmissionReview 请求
		podBytes, err := json.Marshal(pod)
		if err != nil {
			t.Fatalf("Failed to marshal pod: %v", err)
		}

		review := admissionv1.AdmissionReview{
			Request: &admissionv1.AdmissionRequest{
				UID: "test-uid",
				Kind: metav1.GroupVersionKind{
					Kind: "Pod",
				},
				Namespace: "test-namespace",
				Name:      "test-pod",
				Object: runtime.RawExtension{
					Raw: podBytes,
				},
			},
		}

		reviewBytes, err := json.Marshal(review)
		if err != nil {
			t.Fatalf("Failed to marshal review: %v", err)
		}

		// 创建请求和响应记录器
		req, err := http.NewRequest("POST", "/mutate-pods", bytes.NewReader(reviewBytes))
		if err != nil {
			t.Fatalf("Failed to create request: %v", err)
		}

		w := httptest.NewRecorder()

		// 调用 HandleMutatePods
		HandleMutatePods(w, req)

		// 验证响应
		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}

		var response admissionv1.AdmissionReview
		if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
			t.Fatalf("Failed to unmarshal response: %v", err)
		}

		if !response.Response.Allowed {
			t.Error("Expected response to be allowed")
		}

		if response.Response.Patch == nil {
			t.Error("Expected response to have patch")
		}
	})

	// 测试用例：不带有匹配 nodeSelector 的 Pod
	t.Run("Pod without matching nodeSelector", func(t *testing.T) {
		pod := &corev1.Pod{
			Spec: corev1.PodSpec{
				NodeSelector: map[string]string{
					"other-label": "true",
				},
				Containers: []corev1.Container{
					{
						Name:  "test-container",
						Image: "nginx",
					},
				},
			},
		}

		// 构建 AdmissionReview 请求
		podBytes, err := json.Marshal(pod)
		if err != nil {
			t.Fatalf("Failed to marshal pod: %v", err)
		}

		review := admissionv1.AdmissionReview{
			Request: &admissionv1.AdmissionRequest{
				UID: "test-uid",
				Kind: metav1.GroupVersionKind{
					Kind: "Pod",
				},
				Namespace: "test-namespace",
				Name:      "test-pod",
				Object: runtime.RawExtension{
					Raw: podBytes,
				},
			},
		}

		reviewBytes, err := json.Marshal(review)
		if err != nil {
			t.Fatalf("Failed to marshal review: %v", err)
		}

		// 创建请求和响应记录器
		req, err := http.NewRequest("POST", "/mutate-pods", bytes.NewReader(reviewBytes))
		if err != nil {
			t.Fatalf("Failed to create request: %v", err)
		}

		w := httptest.NewRecorder()

		// 调用 HandleMutatePods
		HandleMutatePods(w, req)

		// 验证响应
		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}

		var response admissionv1.AdmissionReview
		if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
			t.Fatalf("Failed to unmarshal response: %v", err)
		}

		if !response.Response.Allowed {
			t.Error("Expected response to be allowed")
		}

		if response.Response.Patch != nil {
			t.Error("Expected response to not have patch")
		}
	})

	// 测试用例：无效的 JSON 请求
	t.Run("Invalid JSON request", func(t *testing.T) {
		// 创建无效的 JSON 请求
		req, err := http.NewRequest("POST", "/mutate-pods", strings.NewReader("invalid json"))
		if err != nil {
			t.Fatalf("Failed to create request: %v", err)
		}

		w := httptest.NewRecorder()

		// 调用 HandleMutatePods
		HandleMutatePods(w, req)

		// 验证响应
		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status 400, got %d", w.Code)
		}
	})

	// 测试用例：nil 请求
	t.Run("Nil request", func(t *testing.T) {
		// 创建空的 AdmissionReview 请求
		review := admissionv1.AdmissionReview{
			Request: nil, // nil request
		}

		reviewBytes, err := json.Marshal(review)
		if err != nil {
			t.Fatalf("Failed to marshal review: %v", err)
		}

		req, err := http.NewRequest("POST", "/mutate-pods", bytes.NewReader(reviewBytes))
		if err != nil {
			t.Fatalf("Failed to create request: %v", err)
		}

		w := httptest.NewRecorder()

		// 调用 HandleMutatePods
		HandleMutatePods(w, req)

		// 验证响应
		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status 400, got %d", w.Code)
		}
	})

	// 测试用例：无效的 JSON 请求体
	t.Run("Invalid JSON request body", func(t *testing.T) {
		// 创建一个包含无效 JSON 的请求体
		// 这里直接发送一个包含无效 JSON 的请求，而不是通过 AdmissionReview
		req, err := http.NewRequest("POST", "/mutate-pods", strings.NewReader("invalid json data"))
		if err != nil {
			t.Fatalf("Failed to create request: %v", err)
		}

		w := httptest.NewRecorder()

		// 调用 HandleMutatePods
		HandleMutatePods(w, req)

		// 验证响应
		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status 400, got %d", w.Code)
		}
	})

	// 测试用例：所有容器都已有资源限制
	t.Run("Pod with all containers having ub_net_device", func(t *testing.T) {
		pod := &corev1.Pod{
			Spec: corev1.PodSpec{
				NodeSelector: map[string]string{
					"topology.kubernetes.io/zone": "supernode",
				},
				Containers: []corev1.Container{
					{
						Name:  "test-container",
						Image: "nginx",
						Resources: corev1.ResourceRequirements{
							Limits: corev1.ResourceList{
								"unifiedbus.com/ub_net_device": resource.MustParse("1"),
							},
						},
					},
				},
			},
		}

		// 构建 AdmissionReview 请求
		podBytes, err := json.Marshal(pod)
		if err != nil {
			t.Fatalf("Failed to marshal pod: %v", err)
		}

		review := admissionv1.AdmissionReview{
			Request: &admissionv1.AdmissionRequest{
				UID: "test-uid",
				Kind: metav1.GroupVersionKind{
					Kind: "Pod",
				},
				Namespace: "test-namespace",
				Name:      "test-pod",
				Object: runtime.RawExtension{
					Raw: podBytes,
				},
			},
		}

		reviewBytes, err := json.Marshal(review)
		if err != nil {
			t.Fatalf("Failed to marshal review: %v", err)
		}

		// 创建请求和响应记录器
		req, err := http.NewRequest("POST", "/mutate-pods", bytes.NewReader(reviewBytes))
		if err != nil {
			t.Fatalf("Failed to create request: %v", err)
		}

		w := httptest.NewRecorder()

		// 调用 HandleMutatePods
		HandleMutatePods(w, req)

		// 验证响应
		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}

		var response admissionv1.AdmissionReview
		if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
			t.Fatalf("Failed to unmarshal response: %v", err)
		}

		if !response.Response.Allowed {
			t.Error("Expected response to be allowed")
		}

		if response.Response.Patch != nil {
			t.Error("Expected response to not have patch")
		}
	})
}

func TestGenerateContainerPatchOps(t *testing.T) {
	tests := []struct {
		name        string
		container   corev1.Container
		basePath    string
		expectedOps int
	}{
		{
			name: "Container with no resources at all",
			container: corev1.Container{
				Name:  "test-container",
				Image: "nginx",
				// 完全没有 Resources 字段
			},
			basePath:    "/spec/containers/0",
			expectedOps: 1,
		},
		{
			name: "Container with requests but no limits",
			container: corev1.Container{
				Name:  "test-container",
				Image: "nginx",
				Resources: corev1.ResourceRequirements{
					Requests: corev1.ResourceList{
						"cpu": resource.MustParse("1"),
					},
					// 没有 Limits
				},
			},
			basePath:    "/spec/containers/0",
			expectedOps: 1,
		},
		{
			name: "Container with limits including ub_net_device",
			container: corev1.Container{
				Name:  "test-container",
				Image: "nginx",
				Resources: corev1.ResourceRequirements{
					Limits: corev1.ResourceList{
						"cpu":                          resource.MustParse("1"),
						"unifiedbus.com/ub_net_device": resource.MustParse("1"),
					},
				},
			},
			basePath:    "/spec/containers/0",
			expectedOps: 0,
		},
		{
			name: "Container with limits but no ub_net_device",
			container: corev1.Container{
				Name:  "test-container",
				Image: "nginx",
				Resources: corev1.ResourceRequirements{
					Limits: corev1.ResourceList{
						"cpu":    resource.MustParse("1"),
						"memory": resource.MustParse("1Gi"),
					},
				},
			},
			basePath:    "/spec/containers/0",
			expectedOps: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ops := generateContainerPatchOps(tt.container, tt.basePath)
			if len(ops) != tt.expectedOps {
				t.Errorf("generateContainerPatchOps() returned %d operations, want %d", len(ops), tt.expectedOps)
			}
		})
	}
}
