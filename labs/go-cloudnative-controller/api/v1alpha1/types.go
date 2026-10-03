// Package v1alpha1 defines the deliberately small teaching API.
// +kubebuilder:object:generate=true
// +groupName=lab.wiki.example
package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
)

var GroupVersion = schema.GroupVersion{Group: "lab.wiki.example", Version: "v1alpha1"}
var SchemeBuilder = runtime.NewSchemeBuilder(func(s *runtime.Scheme) error {
	s.AddKnownTypes(GroupVersion, &AppService{}, &AppServiceList{})
	metav1.AddToGroupVersion(s, GroupVersion)
	return nil
})
var AddToScheme = SchemeBuilder.AddToScheme

type AppServiceSpec struct {
	// Image names the locally loaded teaching operand. No arbitrary image execution is offered as a service.
	// +kubebuilder:validation:MinLength=1
	// +kubebuilder:validation:MaxLength=256
	Image string `json:"image"`
	// +kubebuilder:default=1
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=3
	// +optional
	Replicas *int32 `json:"replicas,omitempty"`
}
type AppServiceStatus struct {
	// ObservedGeneration is the generation considered by this status observation, not a promise of readiness.
	// +optional
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`
	// +listType=map
	// +listMapKey=type
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// +kubebuilder:object:root=true
// Child Service uses the same name, so reject names outside the portable Service DNS-label contract.
// +kubebuilder:validation:XValidation:rule="self.metadata.name.matches('^[a-z]([-a-z0-9]*[a-z0-9])?$') && size(self.metadata.name) <= 63",message="metadata.name must be a DNS label of at most 63 characters starting with a letter"
// +kubebuilder:subresource:status
// +kubebuilder:resource:scope=Namespaced,shortName=asvc
// +kubebuilder:printcolumn:name="Ready",type=string,JSONPath=`.status.conditions[?(@.type=="Ready")].status`
type AppService struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              AppServiceSpec   `json:"spec"`
	Status            AppServiceStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
type AppServiceList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []AppService `json:"items"`
}
