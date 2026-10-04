package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"testing"
)

func TestDeepCopyAndScheme(t *testing.T) {
	s := runtime.NewScheme()
	if err := AddToScheme(s); err != nil {
		t.Fatal(err)
	}
	if _, err := s.New(GroupVersion.WithKind("AppService")); err != nil {
		t.Fatal(err)
	}
	n := int32(1)
	a := &AppService{ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"x": "original"}}, Spec: AppServiceSpec{Replicas: &n}, Status: AppServiceStatus{Conditions: []metav1.Condition{{Type: "Ready", Message: "original"}}}}
	b := a.DeepCopy()
	*b.Spec.Replicas = 2
	b.Labels["x"] = "copy"
	b.Status.Conditions[0].Message = "copy"
	if *a.Spec.Replicas != 1 || a.Labels["x"] != "original" || a.Status.Conditions[0].Message != "original" {
		t.Fatal("copy aliases source")
	}
}
