# Salidas de verificacion del runbook (§13 paso 6).

output "api_url" {
  description = "Endpoint POST del agente."
  value       = "${aws_api_gateway_stage.prod.invoke_url}/v1/chat"
}

output "api_key" {
  description = "Valor de la x-api-key para el Usage Plan. Se pega en el navegador (S-05)."
  value       = aws_api_gateway_api_key.key.value
  sensitive   = true
}

output "ui_url" {
  description = "URL de CloudFront de la UI. Da 403/404 hasta que F8 sube ui/."
  value       = "https://${aws_cloudfront_distribution.ui.domain_name}"
}

output "lambda_function_name" {
  value = aws_lambda_function.agent.function_name
}

output "cloudfront_distribution_id" {
  description = "Para invalidar la cache tras subir la UI en F8."
  value       = aws_cloudfront_distribution.ui.id
}

output "ssm_langsmith_param" {
  description = "Parametro SSM de la clave de LangSmith (lo gestiona el operador, no Terraform)."
  value       = local.ssm_langsmith_name
}
