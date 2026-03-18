FROM python:3.13-alpine

# Install packages
RUN apk add --no-cache tzdata curl

ENV TZ=UTC
WORKDIR /app

# Create virtualenv
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Copy and make script executable
COPY scripts/oac.sh /app/scripts/oac.sh
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /app/scripts/oac.sh /entrypoint.sh

# Default loop: 24 hours
ENV LOOP_HOUR=24

# Run our simple entrypoint
ENTRYPOINT ["/entrypoint.sh"]