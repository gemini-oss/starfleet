# Sample Starfleet Dockerfile for building ECR Lambda functions
FROM public.ecr.aws/lambda/python:3.12

ENV LAMBDA_TASK_ROOT=/var/runtime

# Copy Starfleet over (just a quick and dirty sample, not the cleanest):
COPY ./ ${LAMBDA_TASK_ROOT}/starfleet

# Install the specified packages:
RUN cd ${LAMBDA_TASK_ROOT}/starfleet && \
  pip install . && \
  rm -Rf ${LAMBDA_TASK_ROOT}/boto*  # Remove the lambda provided boto since it interferes with starfleet

# The CMD is passed in as ImageConfig in the SAM template
