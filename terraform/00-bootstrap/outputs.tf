# Salidas que consume `terraform/10-app` (F7) via terraform_remote_state,
# y que el operador necesita para los pasos 2 y 4 del runbook (§13).

output "aws_region" {
  description = "Region del despliegue."
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "URL del repositorio ECR. Destino de `scripts/build_and_push.sh` (paso 4)."
  value       = aws_ecr_repository.agent.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.agent.arn
}

output "dynamodb_memory_table" {
  description = "Tabla de memoria conversacional (PK session_id, SK sk, TTL expires_at)."
  value       = aws_dynamodb_table.memory.name
}

output "dynamodb_memory_table_arn" {
  value = aws_dynamodb_table.memory.arn
}

output "dynamodb_flights_table" {
  value = aws_dynamodb_table.flights.name
}

output "dynamodb_flights_table_arn" {
  value = aws_dynamodb_table.flights.arn
}

output "dynamodb_reservations_table" {
  value = aws_dynamodb_table.reservations.name
}

output "dynamodb_reservations_table_arn" {
  value = aws_dynamodb_table.reservations.arn
}

output "s3_lake_bucket" {
  description = "Bucket del lago medallion (bronze/silver/quarantine/gold)."
  value       = aws_s3_bucket.lake.bucket
}

output "s3_lake_bucket_arn" {
  value = aws_s3_bucket.lake.arn
}

output "s3_ui_bucket" {
  description = "Bucket de la UI estatica (servido via CloudFront+OAC en F7)."
  value       = aws_s3_bucket.ui.bucket
}

output "s3_ui_bucket_arn" {
  value = aws_s3_bucket.ui.arn
}

output "ssm_anthropic_key_param" {
  description = "Nombre del parametro SSM. Cargar el valor con: aws ssm put-parameter --name <esto> --type SecureString --value <clave> --overwrite"
  value       = aws_ssm_parameter.anthropic_api_key.name
}

output "ssm_anthropic_key_param_arn" {
  value = aws_ssm_parameter.anthropic_api_key.arn
}
