# Variables del stack de bootstrap (PRD §13 paso 1).

variable "aws_region" {
  description = "Region AWS. Fijada por S-01 (disponibilidad de Titan V2, precio, ECR Public)."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Etiqueta Project obligatoria en todo recurso (§13)."
  type        = string
  default     = "aeronova-agent"
}

variable "environment" {
  description = "Etiqueta Environment obligatoria (§13)."
  type        = string
  default     = "eval"
}

variable "owner" {
  description = "Etiqueta Owner obligatoria: email del operador (§13)."
  type        = string
  default     = "jesusarredondo0498@gmail.com"
}

variable "name_prefix" {
  description = "Prefijo de nombres de recurso."
  type        = string
  default     = "aeronova"
}

variable "ecr_keep_last_images" {
  description = "Numero de imagenes a conservar en ECR; el resto se purga."
  type        = number
  default     = 5
}

variable "ssm_anthropic_key_name" {
  description = "Nombre del parametro SSM que guardara la clave de Anthropic. El VALOR se carga a mano (§13 paso 2), nunca por Terraform."
  type        = string
  default     = "/aeronova/anthropic_api_key"
}
