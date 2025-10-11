{{/*
Expand the name of the chart.
*/}}
{{- define "openproject.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name. Mirrors the pattern in helm/openproject-mcp so
templates here can be diffed against the sibling chart easily.
*/}}
{{- define "openproject.fullname" -}}
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
Common labels.
*/}}
{{- define "openproject.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "openproject.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels. Match what the upstream opf/openproject subchart applies
to its web pod so service routing lands on the right backend.
*/}}
{{- define "openproject.selectorLabels" -}}
app.kubernetes.io/name: openproject
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend service hostname for our istio templates. The upstream subchart
names its web service `<release>-openproject-web` - we resolve it lazily
so a release rename doesn't break the VirtualService route.
*/}}
{{- define "openproject.backendService" -}}
{{- printf "%s-openproject-web" .Release.Name }}
{{- end }}
