---
id: ACU-004
titulo: El despliegue usa el usuario IAM aeronova-terraform (perfil AWS "aeronova"), no root
tipo: decision
estado: vigente
fase: F2
prd_ref: ["§13", "§16", "S-03"]
aprobado_por: usuario
fecha: 2026-08-27
---

**Qué se acordó.** La cuenta AWS 542035163358 tenia las claves de acceso **de root**
activas y la sesion local de `aws login` usa `login_session` en `~/.aws/config`, formato
que el SDK de Terraform no entiende. Ademas las credenciales temporales de AWS topan en
12 h (1 h como root), insuficiente para un ciclo de desarrollo de varios dias.

Se creo un usuario IAM dedicado **`aeronova-terraform`** con `AdministratorAccess` y una
clave de acceso de larga duracion, guardada como perfil **`aeronova`** en
`~/.aws/credentials` (fuera de Git). Todo `terraform` y los scripts de F2b-F9 usan
`AWS_PROFILE=aeronova` (con `region = us-east-1` en `~/.aws/config`).

**Por qué.** Terraform necesita un origen de credenciales que su SDK reconozca (variables
de entorno o un perfil en `~/.aws/credentials`). Un usuario IAM con clave estatica no
caduca, evita re-autenticar a diario, y es mejor postura que operar con las claves de root
(recomendacion de AWS). Es coherente con S-03 (un solo operador).

**Cómo se aplica.**

- `terraform` de ambos stacks y los scripts de datos se ejecutan con `AWS_PROFILE=aeronova`.
- El estado de Terraform sigue siendo **local** (S-03); `f2.tfplan` es un artefacto
  temporal, no se versiona.
- El `terraform apply` lo ejecuta el usuario en su terminal: el clasificador de permisos de
  Claude Code bloquea `terraform apply`, `aws iam *` y `aws ssm put-parameter` en modo
  automatico. El agente escribe el codigo, hace `plan`, y verifica por API de solo lectura.

**Obligacion de teardown (§13 paso 7, §16 «ningun secreto en Git ni credencial huerfana»).**
Al cerrar el proyecto, ademas de `terraform destroy` de los dos stacks:

```
aws iam detach-user-policy --user-name aeronova-terraform --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam list-access-keys --user-name aeronova-terraform   # borrar cada AccessKeyId
aws iam delete-access-key --user-name aeronova-terraform --access-key-id <id>
aws iam delete-user --user-name aeronova-terraform
```

Y considerar desactivar/rotar las claves de acceso de **root**, que no deberian estar
activas.

Ademas, `terraform destroy` de `10-app` deja **un rol IAM huerfano** creado por F7 para
que API Gateway pueda escribir logs de ejecucion en CloudWatch (ajuste de ambito de
cuenta, `aws_api_gateway_account`). Borrarlo a mano:

```
aws iam detach-role-policy --role-name aeronova-agent-apigw-logs \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs
aws iam delete-role --role-name aeronova-agent-apigw-logs
```

**Qué invalida este acuerdo.** Que el usuario decida acotar los permisos del usuario IAM a
una politica a medida (ECR/DynamoDB/S3/SSM/Lambda/APIGW/CloudFront/IAM/EventBridge/Budgets/
CloudWatch), o migrar a un rol asumible.
