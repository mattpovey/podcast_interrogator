#!/bin/bash

# Create a directory for the exported volumes
export_dir="vol_export"
mkdir -p "$export_dir"

# Get the current date in YYYY-MM-DD format
current_date=$(date +%F)

# Define the volumes to export
volumes=("esdata" "pgdata" "chroma-data" "app_data")

# Loop through each volume and export it
for volume in "${volumes[@]}"; do
    echo "Exporting volume: $volume"
    docker run --rm -v "$volume:/volume" -v "$(pwd)/$export_dir:/backup" alpine \
        tar -czf "/backup/${volume}_${current_date}.tar.gz" -C /volume . 
done

echo "All specified volumes have been exported to $export_dir."