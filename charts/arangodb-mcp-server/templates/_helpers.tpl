{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "template.name" -}}
{{- lower (printf "%s" .Chart.Name | trunc 63 | trimSuffix "-") -}}
{{- end -}}

{{/*
Expand the name of the release.
*/}}
{{- define "template.releaseName" -}}
{{- lower (printf "%s" .Release.Name | trunc 63 | trimSuffix "-") -}}
{{- end -}}
