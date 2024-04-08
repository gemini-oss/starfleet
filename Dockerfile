# Sample Starfleet Dockerfile for building ECR Lambda functions
FROM public.ecr.aws/lambda/python:3.12

ENV LAMBDA_TASK_ROOT=/var/runtime

# Copy Starfleet over:
COPY ./ ${LAMBDA_TASK_ROOT}/starfleet

# Perform cleanup of things the Docker doens't need:
RUN rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/tests && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/.tox && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/.pytest_cache && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/deploy && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/site && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/.kubelr && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/build && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/.coverage && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/*.ini && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/*.yaml && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/*.md && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/sample_samconfig.toml && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/Dockerfile && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/venv && \
    rm -Rf ${LAMBDA_TASK_ROOT}/starfleet/env

# Install the specified packages:
RUN cd ${LAMBDA_TASK_ROOT}/starfleet && \
  pip install . && \
  rm -Rf ${LAMBDA_TASK_ROOT}/boto*  # Remove the lambda provided boto since it interferes with starfleet

# The CMD is passed in as ImageConfig in the SAM template
