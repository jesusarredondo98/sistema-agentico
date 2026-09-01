# ---------------------------------------------------------------------------
# terraform/00-bootstrap  --  Apply #1 del runbook (PRD §13 paso 1).
#
# Crea todo lo que NO depende de la imagen de la Lambda: ECR, las 3 tablas
# DynamoDB, los 2 buckets S3 del lago/UI y el parametro SSM de la clave.
# `terraform/10-app` (F7) lee las salidas de aqui con terraform_remote_state.
#
# Estado LOCAL (S-03): un solo operador. La migracion a backend S3+DynamoDB
# para multi-operador se documenta pero no se implementa.
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Etiquetado obligatorio en TODO recurso (§13).
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = var.owner
    }
  }
}

# Sufijo para unicidad global de nombres de bucket (§2.4).
resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  suffix      = random_id.suffix.hex
  lake_bucket = "${var.name_prefix}-lake-${local.suffix}"
  ui_bucket   = "${var.name_prefix}-ui-${local.suffix}"
}

# ---------------------------------------------------------------------------
# ECR  --  repositorio de la imagen de la Lambda
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "agent" {
  name                 = "${var.name_prefix}-agent"
  image_tag_mutability = "IMMUTABLE" # la etiqueta es el SHA de Git, nunca se reescribe
  force_delete         = true        # cuenta de evaluacion: teardown limpio (§13 paso 7)

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las ultimas ${var.ecr_keep_last_images} imagenes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_keep_last_images
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# DynamoDB  --  3 tablas, PAY_PER_REQUEST, PITR desactivado por coste (§2.4)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "memory" {
  name         = "${var.name_prefix}-memory"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false
  }
}

resource "aws_dynamodb_table" "flights" {
  name         = "${var.name_prefix}-flights"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "codigo_vuelo"

  attribute {
    name = "codigo_vuelo"
    type = "S"
  }
  # Para la tool `vuelos_por_ciudad` (ACU-006). GSIs por origen y por destino.
  attribute {
    name = "origen"
    type = "S"
  }
  attribute {
    name = "destino"
    type = "S"
  }

  global_secondary_index {
    name            = "origen-index"
    hash_key        = "origen"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "destino-index"
    hash_key        = "destino"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }
}

resource "aws_dynamodb_table" "reservations" {
  name         = "${var.name_prefix}-reservations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pnr"

  attribute {
    name = "pnr"
    type = "S"
  }
  # Para `pasajeros_de_vuelo` y `mascotas_por_vuelo` (ACU-006).
  attribute {
    name = "codigo_vuelo"
    type = "S"
  }

  global_secondary_index {
    name            = "codigo_vuelo-index"
    hash_key        = "codigo_vuelo"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }
}

# ---------------------------------------------------------------------------
# S3  --  lago medallion + bucket de UI. Privados, BPA completo, SSE-S3,
#         versionado (§2.4).
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "lake" {
  bucket        = local.lake_bucket
  force_destroy = true # teardown de evaluacion (§13 paso 7)
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3, sin coste de KMS
    }
  }
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Ciclo de vida (§2.4): bronze/ y quarantine/ a Glacier IR a 30 dias;
# gold/rag/ conserva 3 versiones de objeto. El podado de las carpetas
# `v=<ts>/` antiguas lo hace el pipeline en F4 (rollback_rag.py), porque
# S3 Lifecycle no cuenta versiones basadas en prefijo.
resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket     = aws_s3_bucket.lake.id
  depends_on = [aws_s3_bucket_versioning.lake]

  rule {
    id     = "bronze-a-glacier-ir"
    status = "Enabled"
    filter {
      prefix = "bronze/"
    }
    transition {
      days          = 30
      storage_class = "GLACIER_IR"
    }
  }

  rule {
    id     = "quarantine-a-glacier-ir"
    status = "Enabled"
    filter {
      prefix = "quarantine/"
    }
    transition {
      days          = 30
      storage_class = "GLACIER_IR"
    }
  }

  rule {
    id     = "gold-rag-conserva-3-versiones"
    status = "Enabled"
    filter {
      prefix = "gold/rag/"
    }
    noncurrent_version_expiration {
      newer_noncurrent_versions = 3
      noncurrent_days           = 1
    }
  }
}

resource "aws_s3_bucket" "ui" {
  bucket        = local.ui_bucket
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "ui" {
  bucket                  = aws_s3_bucket.ui.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ui" {
  bucket = aws_s3_bucket.ui.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "ui" {
  bucket = aws_s3_bucket.ui.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ---------------------------------------------------------------------------
# SSM  --  contenedor del secreto. El VALOR lo carga el operador con
#          `aws ssm put-parameter --type SecureString` (§13 paso 2).
#          NUNCA por Terraform ni por .tfvars.
# ---------------------------------------------------------------------------
resource "aws_ssm_parameter" "anthropic_api_key" {
  name  = var.ssm_anthropic_key_name
  type  = "SecureString"
  value = "PENDIENTE_cargar_con_aws_ssm_put-parameter" # placeholder; se sobrescribe fuera de Terraform

  lifecycle {
    ignore_changes = [value] # el operador es la fuente de verdad del valor
  }
}
