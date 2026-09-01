# ---------------------------------------------------------------------------
# terraform/10-app  --  Apply #2 del runbook (PRD §13 paso 5).
#
# Lambda (imagen arm64), API Gateway REST + Usage Plan MENSUAL, IAM por ARN,
# CloudFront+OAC para la UI, EventBridge de calentamiento, AWS Budgets y las
# 10 alarmas de §11. Lee las salidas de `00-bootstrap` con terraform_remote_state.
# Estado LOCAL (S-03).
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = var.owner
    }
  }
}

data "aws_caller_identity" "me" {}

data "terraform_remote_state" "bootstrap" {
  backend = "local"
  config  = { path = "${path.module}/../00-bootstrap/terraform.tfstate" }
}

locals {
  bs        = data.terraform_remote_state.bootstrap.outputs
  acct      = data.aws_caller_identity.me.account_id
  fn_name   = "${var.name_prefix}-agent"
  image_uri = "${local.bs.ecr_repository_url}:${var.image_tag}"

  ssm_anthropic_arn  = "arn:aws:ssm:${var.aws_region}:${local.acct}:parameter/aeronova/anthropic_api_key"
  ssm_langsmith_name = "/aeronova/langsmith_api_key"
  ssm_langsmith_arn  = "arn:aws:ssm:${var.aws_region}:${local.acct}:parameter/aeronova/langsmith_api_key"
  log_group_arn      = "arn:aws:logs:${var.aws_region}:${local.acct}:log-group:/aws/lambda/${local.fn_name}:*"

  lambda_env = {
    ANTHROPIC_API_KEY_PARAM  = "/aeronova/anthropic_api_key"
    ANTHROPIC_MODEL          = "claude-sonnet-5"
    MEMORY_TABLE             = local.bs.dynamodb_memory_table
    FLIGHTS_TABLE            = local.bs.dynamodb_flights_table
    RESERVATIONS_TABLE       = local.bs.dynamodb_reservations_table
    S3_BUCKET_LAKE           = local.bs.s3_lake_bucket
    RAG_CURRENT_POINTER      = "gold/rag/CURRENT"
    RAG_CONTRACT_VERSION_MIN = "1.0.0"
    BEDROCK_EMBED_MODEL      = "amazon.titan-embed-text-v2:0"
    MAX_TOOL_ROUNDS          = tostring(var.max_tool_rounds)
    MAX_OUTPUT_TOKENS        = tostring(var.max_output_tokens)
    HISTORY_WINDOW_MESSAGES  = tostring(var.history_window_messages)
    MEMORY_TTL_HOURS         = tostring(var.memory_ttl_hours)
    RAG_TOP_K                = tostring(var.rag_top_k)
    LOG_LEVEL                = "INFO"
    LANGCHAIN_TRACING_V2     = var.enable_langsmith ? "true" : "false"
    LANGCHAIN_PROJECT        = var.project
    LANGSMITH_API_KEY_PARAM  = local.ssm_langsmith_name
    # Origen de la UI para la cabecera CORS de la respuesta real (§2.3, A-105).
    # El preflight OPTIONS lo fija API Gateway; la respuesta del POST la fija la
    # Lambda (integración proxy) y también DEBE llevar Allow-Origin, nunca "*".
    UI_ORIGIN = "https://${aws_cloudfront_distribution.ui.domain_name}"
    # ACU-006: cortacircuitos de coste por sesión subido para la demo (PRD = 0.25).
    SESSION_COST_LIMIT_USD = "0.75"
  }
}

# ---------------------------------------------------------------------------
# SSM  --  la clave de LangSmith (SecureString `/aeronova/langsmith_api_key`) la
#          crea y mantiene el OPERADOR con `aws ssm put-parameter` (S-04).
#          Terraform NO la gestiona: solo la referencia por ARN para el permiso
#          IAM y por nombre para la variable de entorno de la Lambda.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# IAM  --  rol de ejecucion. Explicito, por ARN, SIN comodines de servicio (§2.5).
# ---------------------------------------------------------------------------
resource "aws_iam_role" "lambda" {
  name = "${local.fn_name}-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.fn_name}-policy"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = local.log_group_arn
      },
      {
        Sid      = "MemoryTableRW"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"]
        Resource = local.bs.dynamodb_memory_table_arn
      },
      {
        Sid      = "FlightsReservationsRead"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:BatchGetItem"]
        Resource = [local.bs.dynamodb_flights_table_arn, local.bs.dynamodb_reservations_table_arn]
      },
      {
        # `dynamodb:Query` SOLO sobre los GSIs (ACU-006): vuelos_por_ciudad,
        # pasajeros_de_vuelo, mascotas_por_vuelo. Solo lectura, sin Scan.
        Sid    = "FlightsReservationsIndexQuery"
        Effect = "Allow"
        Action = ["dynamodb:Query"]
        Resource = [
          "${local.bs.dynamodb_flights_table_arn}/index/*",
          "${local.bs.dynamodb_reservations_table_arn}/index/*",
        ]
      },
      {
        Sid      = "LakeGoldRagRead"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${local.bs.s3_lake_bucket_arn}/gold/rag/*"
      },
      {
        Sid       = "LakeGoldRagList"
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = local.bs.s3_lake_bucket_arn
        Condition = { StringLike = { "s3:prefix" = "gold/rag/*" } }
      },
      {
        Sid      = "BedrockTitanV2"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
      },
      {
        Sid      = "SsmSecrets"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = [local.ssm_anthropic_arn, local.ssm_langsmith_arn]
      },
      {
        Sid      = "KmsDecryptSsm"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "arn:aws:kms:${var.aws_region}:${local.acct}:alias/aws/ssm"
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Lambda  --  imagen arm64, los 8 parametros exactos de §2.2. SIN SnapStart.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.fn_name}"
  retention_in_days = 14 # §2.2
}

resource "aws_lambda_function" "agent" {
  function_name = local.fn_name
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["arm64"]
  timeout       = 29   # §2.2: API Gateway REST corta a los 29 s
  memory_size   = 2048 # §2.2

  ephemeral_storage {
    size = 2048 # §2.2: el indice LanceDB desborda los 512 MB por defecto
  }

  # §2.2: techo de gasto en rafaga. Valor del PRD = 20 (default de la variable).
  # ACU-005: hasta que Service Quotas suba el limite global de la cuenta (10 -> 1000)
  # se despliega con -var="reserved_concurrency=-1" (sin reservar).
  reserved_concurrent_executions = var.reserved_concurrency

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }

  environment {
    variables = local.lambda_env
  }

  depends_on = [aws_iam_role_policy.lambda, aws_cloudwatch_log_group.lambda]
}

# Concurrencia aprovisionada: documentada, DESACTIVADA por defecto (§2.2).
resource "aws_lambda_alias" "live" {
  count            = var.enable_provisioned_concurrency ? 1 : 0
  name             = "live"
  function_name    = aws_lambda_function.agent.function_name
  function_version = aws_lambda_function.agent.version
}

resource "aws_lambda_provisioned_concurrency_config" "pc" {
  count                             = var.enable_provisioned_concurrency ? 1 : 0
  function_name                     = aws_lambda_function.agent.function_name
  provisioned_concurrent_executions = 1
  qualifier                         = aws_lambda_alias.live[0].name
}

# ---------------------------------------------------------------------------
# API Gateway REST  --  POST /v1/chat, x-api-key, Usage Plan MENSUAL (§2.3, I-01)
# ---------------------------------------------------------------------------
resource "aws_api_gateway_rest_api" "api" {
  name = "${var.name_prefix}-agent-api"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "v1"
}

resource "aws_api_gateway_resource" "chat" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "chat"
}

resource "aws_api_gateway_method" "post_chat" {
  rest_api_id      = aws_api_gateway_rest_api.api.id
  resource_id      = aws_api_gateway_resource.chat.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true # falta de x-api-key -> 403 nativo (§2.3)
}

resource "aws_api_gateway_integration" "post_chat" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.chat.id
  http_method             = aws_api_gateway_method.post_chat.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.agent.invoke_arn
}

# --- CORS: OPTIONS con Allow-Origin restringido al dominio de CloudFront (§2.3) ---
resource "aws_api_gateway_method" "options_chat" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_chat" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.options_chat.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_chat" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.options_chat.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_chat" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.options_chat.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'content-type,x-api-key'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'https://${aws_cloudfront_distribution.ui.domain_name}'"
  }
  depends_on = [aws_api_gateway_integration.options_chat]
}

# Las respuestas que genera API Gateway por su cuenta (403 sin api-key, 429 de
# cuota/throttle, 504 de timeout de la Lambda, 500...) NO llevan CORS por
# defecto. Sin estas cabeceras, el navegador no puede leer el cuerpo y el
# `fetch` de la UI falla con un error de red genérico en vez de mostrar el
# motivo. Origen restringido al dominio de CloudFront, nunca "*" (§2.3, A-105).
locals {
  cors_gateway_headers = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'https://${aws_cloudfront_distribution.ui.domain_name}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'content-type,x-api-key'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
  }
}

resource "aws_api_gateway_gateway_response" "cors" {
  # DEFAULT_4XX/5XX cubren la mayoría; los tipos específicos de api-key y de
  # cuota/throttle tienen precedencia sobre DEFAULT_4XX, así que se declaran
  # aparte para que el navegador también pueda leer esos errores.
  for_each = toset([
    "DEFAULT_4XX",
    "DEFAULT_5XX",
    "MISSING_AUTHENTICATION_TOKEN",
    "ACCESS_DENIED",
    "INVALID_API_KEY",
    "QUOTA_EXCEEDED",
    "THROTTLED",
    "INTEGRATION_TIMEOUT",
    "INTEGRATION_FAILURE",
  ])
  rest_api_id         = aws_api_gateway_rest_api.api.id
  response_type       = each.key
  response_parameters = local.cors_gateway_headers
  # API Gateway autocompleta plantilla y (en los tipos especificos) el status_code;
  # declarar la primera e ignorar el segundo evita un diff perpetuo.
  response_templates = {
    "application/json" = "{\"message\":$context.error.messageString}"
  }
  lifecycle {
    ignore_changes = [status_code]
  }
}

resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  triggers = {
    # Las gateway responses solo surten efecto tras un redeploy del stage.
    redeploy = sha1(jsonencode([
      aws_api_gateway_resource.chat.id,
      aws_api_gateway_method.post_chat.id,
      aws_api_gateway_integration.post_chat.id,
      aws_api_gateway_integration.options_chat.id,
      aws_api_gateway_integration_response.options_chat.response_parameters,
      [for k, v in aws_api_gateway_gateway_response.cors : v.id],
    ]))
  }
  lifecycle {
    create_before_destroy = true
  }
  depends_on = [aws_api_gateway_integration.post_chat, aws_api_gateway_integration.options_chat]
}

# API Gateway solo puede escribir logs de ejecucion en CloudWatch si la cuenta
# tiene un rol asociado (requisito de `logging_level != OFF`). Es un ajuste de
# AMBITO DE CUENTA por region; lo gestiona este stack porque es el unico operador
# (S-03). En el teardown queda un rol huerfano: borrarlo a mano (§16).
resource "aws_iam_role" "apigw_cloudwatch" {
  name = "${var.name_prefix}-agent-apigw-logs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "apigateway.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apigw_cloudwatch" {
  role       = aws_iam_role.apigw_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "this" {
  cloudwatch_role_arn = aws_iam_role.apigw_cloudwatch.arn
  depends_on          = [aws_iam_role_policy_attachment.apigw_cloudwatch]
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id          = aws_api_gateway_rest_api.api.id
  deployment_id        = aws_api_gateway_deployment.api.id
  stage_name           = "prod"
  xray_tracing_enabled = false
}

resource "aws_api_gateway_method_settings" "prod" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"
  settings {
    metrics_enabled        = true
    logging_level          = "ERROR"
    throttling_rate_limit  = 10
    throttling_burst_limit = 20
  }
  depends_on = [aws_api_gateway_account.this]
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agent.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# --- API key + Usage Plan MENSUAL (§2.3, hallazgo 38, I-01) ---
resource "aws_api_gateway_api_key" "key" {
  name = "${var.name_prefix}-agent-key"
}

resource "aws_api_gateway_usage_plan" "plan" {
  name = "${var.name_prefix}-agent-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  throttle_settings {
    rate_limit  = 10
    burst_limit = 20
  }

  quota_settings {
    limit  = var.usage_plan_quota
    period = "MONTH" # NUNCA DAY (I-01, hallazgo 38): con DAY seria ~26x el techo
  }
}

resource "aws_api_gateway_usage_plan_key" "plan_key" {
  key_id        = aws_api_gateway_api_key.key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.plan.id
}

# ---------------------------------------------------------------------------
# CloudFront + OAC  --  sirve la UI estatica del bucket privado (§2.4, D-04)
# ---------------------------------------------------------------------------
resource "aws_cloudfront_origin_access_control" "ui" {
  name                              = "${var.name_prefix}-ui-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "ui" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # nivel gratuito (§2.4)
  comment             = "AeroNova agent UI"

  origin {
    domain_name              = "${local.bs.s3_ui_bucket}.s3.${var.aws_region}.amazonaws.com"
    origin_id                = "ui-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.ui.id
  }

  default_cache_behavior {
    target_origin_id       = "ui-s3"
    viewer_protocol_policy = "redirect-to-https" # §2.4
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 3600
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

resource "aws_s3_bucket_policy" "ui" {
  bucket = local.bs.s3_ui_bucket
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontOAC"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${local.bs.s3_ui_bucket_arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.ui.arn }
      }
    }]
  })
}

# ---------------------------------------------------------------------------
# EventBridge  --  ping de calentamiento cada 5 min (§2.2)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "warmup" {
  name                = "${var.name_prefix}-agent-warmup"
  schedule_expression = "rate(5 minutes)"
  state               = "ENABLED" # se puede desactivar a mano en pausas; el apply lo restaura
}

resource "aws_cloudwatch_event_target" "warmup" {
  rule  = aws_cloudwatch_event_rule.warmup.name
  arn   = aws_lambda_function.agent.arn
  input = jsonencode({ warmup = true })
}

resource "aws_lambda_permission" "warmup" {
  statement_id  = "AllowEventBridgeWarmup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agent.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.warmup.arn
}

# ---------------------------------------------------------------------------
# Notificacion de alarmas  --  SNS + suscripcion por email (§11)
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alarms" {
  count = var.alarm_email == "" ? 0 : 1
  name  = "${var.name_prefix}-agent-alarms"
}

resource "aws_sns_topic_subscription" "alarms_email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  alarm_actions = var.alarm_email == "" ? [] : [aws_sns_topic.alarms[0].arn]
}

# ---------------------------------------------------------------------------
# AWS Budgets  --  20 USD con alertas al 50/80/100 % (G-3, §9.5)
# ---------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  name         = "${var.name_prefix}-agent-monthly"
  budget_type  = "COST"
  limit_amount = "20"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = var.alarm_email == "" ? [] : [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }
}

# ---------------------------------------------------------------------------
# Alarmas de CloudWatch (§11) -- las 10
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.fn_name}-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 300
  threshold           = 5
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  dimensions          = { FunctionName = local.fn_name }
  alarm_actions       = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "lambda_p95" {
  alarm_name          = "${local.fn_name}-duration-p95"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 300
  threshold           = 20000
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  extended_statistic  = "p95"
  dimensions          = { FunctionName = local.fn_name }
  alarm_actions       = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.fn_name}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 300
  threshold           = 0
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  dimensions          = { FunctionName = local.fn_name }
  alarm_actions       = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "cost_daily" {
  alarm_name          = "${var.name_prefix}-agent-cost-daily"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 86400
  threshold           = 30
  namespace           = "AeroNova/Agent"
  metric_name         = "CostUSD"
  statistic           = "Sum"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "quarantine_rate" {
  alarm_name          = "${var.name_prefix}-data-quarantine-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 86400
  threshold           = 2
  namespace           = "AeroNova/Data"
  metric_name         = "QuarantineRate"
  statistic           = "Maximum"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "rag_current_age" {
  alarm_name          = "${var.name_prefix}-rag-current-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 3600
  threshold           = 720 # CONTRACT_SLA_HOURS del corpus (§6A.3)
  namespace           = "AeroNova/Agent"
  metric_name         = "RagCurrentAgeHours"
  statistic           = "Maximum"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "output_filter" {
  alarm_name          = "${var.name_prefix}-agent-output-filter"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 300
  threshold           = 0
  namespace           = "AeroNova/Agent"
  metric_name         = "OutputFilterTriggered"
  statistic           = "Sum"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "injection_suspected" {
  alarm_name          = "${var.name_prefix}-agent-injection-suspected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 3600
  threshold           = 5
  namespace           = "AeroNova/Agent"
  metric_name         = "InjectionSuspected"
  statistic           = "Sum"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "session_cost_p99" {
  alarm_name          = "${var.name_prefix}-agent-session-cost-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 3600
  threshold           = 0.20
  namespace           = "AeroNova/Agent"
  metric_name         = "SessionCostUSD"
  extended_statistic  = "p99"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "prompt_truncations" {
  alarm_name          = "${var.name_prefix}-agent-prompt-truncations"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 3600
  threshold           = 10
  namespace           = "AeroNova/Agent"
  metric_name         = "PromptBudgetTruncations"
  statistic           = "Sum"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"
}
