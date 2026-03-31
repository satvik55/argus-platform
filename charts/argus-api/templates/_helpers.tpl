{{/*
Expand the name of the chart.
Used as a base for resource names.
*/}}
{{- define "argus-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name.
Uses release name + chart name, truncated to 63 chars (K8s label limit).
*/}}
{{- define "argus-api.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Standard labels applied to every resource.
Follows Kubernetes recommended label conventions.
*/}}
{{- define "argus-api.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "argus-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: argus-platform
{{- end }}

{{/*
Selector labels — used by Deployment.spec.selector and Service.spec.selector.
Must be a SUBSET of the full labels (K8s requires selectors to be immutable).
*/}}
{{- define "argus-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "argus-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
