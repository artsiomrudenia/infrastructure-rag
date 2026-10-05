{{- define "infrastructure-rag.fullname" -}}
{{- default "infrastructure-rag" .Release.Name -}}
{{- end -}}
