# Variables del stack de aplicacion (PRD §13 paso 5).

variable "aws_region" {
  type    = string
  default = "us-east-1" # S-01
}

variable "project" {
  type    = string
  default = "aeronova-agent"
}

variable "environment" {
  type    = string
  default = "eval"
}

variable "owner" {
  type    = string
  default = "jesusarredondo0498@gmail.com"
}

variable "name_prefix" {
  type    = string
  default = "aeronova"
}

variable "image_tag" {
  description = "SHA corto de Git de la imagen en ECR. NUNCA 'latest' (§13, hallazgo 8)."
  type        = string
}

variable "enable_provisioned_concurrency" {
  description = "Concurrencia aprovisionada (§2.2). Por si sola supera el techo de 20 USD/mes: desactivada."
  type        = bool
  default     = false
}

variable "reserved_concurrency" {
  description = <<-EOT
    Ejecuciones concurrentes reservadas para la Lambda (§2.2: valor del PRD = 20,
    techo de gasto en rafaga). -1 = sin reservar.
    ACU-005: la cuenta arranca con un limite global de 10; Service Quotas lo
    subio a 1000 y se restauro a 20. Subido temporalmente a 40 para los hard
    tests de cierre (ACU-005 nota 2026-09-01); volver a 20 al terminar.
  EOT
  type        = number
  default     = 40
}

variable "enable_langsmith" {
  description = "Trazado en LangSmith (§11). La clave se carga a mano en SSM, nunca por .tfvars."
  type        = bool
  default     = true
}

variable "alarm_email" {
  description = "Destino de las notificaciones de las 10 alarmas de CloudWatch (§11). Vacio = sin notificacion."
  type        = string
  default     = "jesusarredondo0498@gmail.com"
}

# --- valores exactos de §2.7 / §2.2, no se ajustan sin decision ---
variable "max_tool_rounds" {
  type    = number
  default = 3
}
variable "max_output_tokens" {
  type    = number
  default = 1024
}
variable "history_window_messages" {
  type    = number
  default = 8
}
variable "memory_ttl_hours" {
  type    = number
  default = 24
}
variable "rag_top_k" {
  type    = number
  default = 4
}
variable "usage_plan_quota" {
  description = "Cuota MENSUAL del Usage Plan (§2.3, I-01). Elevada a 50000 por el sponsor (ACU-008, nota 2026-09-01): las rondas de hard testing del cierre consumen miles de peticiones. G-1 ya no es el control de coste vinculante; el techo real es el AWS Budget de 20 USD (G-3) y el limite del workspace de Anthropic (G-2)."
  type        = number
  default     = 50000
}
