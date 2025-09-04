# Use an official Python runtime as a parent image
FROM python:3.10-slim-bullseye

# Set the working directory in the container
WORKDIR /app

# --- Install System Dependencies ---
# Update package lists and install Tesseract OCR and other libraries needed by OpenCV.
# This is a critical step as pytesseract is just a wrapper for the Tesseract engine.
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# --- Install Python Dependencies ---
# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy Application Code ---
# Copy the rest of your application's code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run your application
CMD ["python", "app.py"]