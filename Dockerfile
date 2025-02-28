# Use the official Python 3.13 base image
FROM python:3.13-bullseye

# Set the working directory inside the container
WORKDIR /app

# Copy only the required files first (improves build cache efficiency)
COPY requirements.txt .

# Update package lists and install dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    gcc \
    libpq-dev \
    curl \
    unzip \
    postgresql-client \      
    redis-tools \            
    awscli \                 
    vim \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Expose port 8000 for the FastAPI app
EXPOSE 8000

# Run the application
CMD ["python", "src/main.py"]