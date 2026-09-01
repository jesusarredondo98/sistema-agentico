# Contrato de construcción de la Lambda de contenedor (PRD §2.6).
# DEBE compilarse con:  docker build --platform linux/arm64 -t aeronova-agent .
# Omitir --platform en x86 produce "exec format error" en ejecucion, no en el build (hallazgo 8).
FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD [ "handler.lambda_handler" ]
