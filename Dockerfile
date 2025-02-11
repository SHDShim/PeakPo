# Step 1: Start from a lightweight base image
FROM continuumio/miniconda3:latest

# Step 2: Copy the environment.yml file into the container
COPY environment.yml /tmp/environment.yml

# Step 3: Install dependencies via conda
RUN conda env create -f /tmp/environment.yml

# Step 4: Activate the environment by default
RUN echo "conda activate pkpo2022fbs" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

# Step 5: Set the working directory for the app
WORKDIR /app

# Step 6: Copy your app's files into the container
COPY ./peakpo /app

# Step 7: Expose a port if needed (optional)
EXPOSE 8000  

# Step 8: Run the app (replace this with the appropriate command)
CMD ["python", "-m", "peakpo.py"]  # Replace 'app.py' with your entry script
