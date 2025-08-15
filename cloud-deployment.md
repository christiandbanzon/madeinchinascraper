# Made-in-China Scraper - Cloud Deployment Guide

This guide will help you deploy the Made-in-China scraper in various cloud environments.

## 🚀 Quick Start

### Prerequisites
- Docker installed on your system
- Docker Compose installed
- Git (to clone the repository)

### Basic Deployment

1. **Clone or download the project files**
   ```bash
   # If using git
   git clone <repository-url>
   cd made-in-china
   
   # Or simply copy all project files to your server
   ```

2. **Run the deployment script**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

3. **Test the deployment**
   ```bash
   docker-compose run --rm made-in-china-scraper python main.py search "test"
   ```

## ☁️ Cloud Platform Specific Instructions

### AWS EC2

1. **Launch an EC2 instance**
   - Use Ubuntu 20.04 LTS or later
   - Minimum: t3.medium (2 vCPU, 4 GB RAM)
   - Recommended: t3.large (2 vCPU, 8 GB RAM) for better performance

2. **Connect to your instance**
   ```bash
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```

3. **Install Docker**
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker $USER
   # Logout and login again, or run: newgrp docker
   ```

4. **Deploy the scraper**
   ```bash
   # Upload your project files to the server
   # Then run:
   chmod +x deploy.sh
   ./deploy.sh
   ```

5. **Set up persistent storage (optional)**
   ```bash
   # Create an EBS volume and mount it
   sudo mkdir /mnt/scraper-data
   sudo mount /dev/xvdf /mnt/scraper-data
   
   # Update docker-compose.yml to use the mounted volume
   volumes:
     - /mnt/scraper-data:/app/data
   ```

### Google Cloud Platform (GCP)

1. **Create a Compute Engine instance**
   ```bash
   gcloud compute instances create scraper-instance \
     --zone=us-central1-a \
     --machine-type=e2-medium \
     --image-family=ubuntu-2004-lts \
     --image-project=ubuntu-os-cloud
   ```

2. **Connect to your instance**
   ```bash
   gcloud compute ssh scraper-instance --zone=us-central1-a
   ```

3. **Install Docker and deploy**
   ```bash
   # Same as AWS EC2 steps 3-4
   ```

### Azure

1. **Create a Virtual Machine**
   - Use Ubuntu Server 20.04 LTS
   - Size: Standard_B2s (2 vCPU, 4 GB RAM)

2. **Connect and deploy**
   ```bash
   # Same as AWS EC2 steps 3-4
   ```

### DigitalOcean

1. **Create a Droplet**
   - Ubuntu 20.04 LTS
   - Size: Basic (2 GB RAM, 1 vCPU)

2. **Connect and deploy**
   ```bash
   # Same as AWS EC2 steps 3-4
   ```

## 🔧 Usage Examples

### Basic Search
```bash
# Search for products
docker-compose run --rm made-in-china-scraper python main.py search "hair dryer"

# Search with specific page limit
docker-compose run --rm made-in-china-scraper python main.py search "hair dryer" --pages 5
```

### Export Data
```bash
# Export to JSON
docker-compose run --rm made-in-china-scraper python main.py export "hair dryer" --format json

# Export to CSV
docker-compose run --rm made-in-china-scraper python main.py export "hair dryer" --format csv
```

### View Statistics
```bash
# View database statistics
docker-compose run --rm made-in-china-scraper python main.py stats
```

### Automated Scheduling
```bash
# Run automated scraping every hour
docker-compose run --rm made-in-china-scraper python main.py schedule "hair dryer" --interval 3600

# Run daily at 2 AM
docker-compose run --rm made-in-china-scraper python main.py schedule "hair dryer" --interval 86400
```

## 📊 Monitoring and Logs

### View Logs
```bash
# View application logs
docker-compose logs made-in-china-scraper

# Follow logs in real-time
docker-compose logs -f made-in-china-scraper
```

### Check Data Directory
```bash
# List scraped data files
ls -la data/

# View latest CSV file
tail -f data/search_hair_dryer_*.csv
```

## 🔄 Cron Jobs for Automation

### Set up automated scraping with cron
```bash
# Edit crontab
crontab -e

# Add these lines for automated scraping:
# Run every 6 hours
0 */6 * * * cd /path/to/made-in-china && docker-compose run --rm made-in-china-scraper python main.py search "hair dryer" >> logs/cron.log 2>&1

# Run daily at 2 AM
0 2 * * * cd /path/to/made-in-china && docker-compose run --rm made-in-china-scraper python main.py search "electronics" >> logs/cron.log 2>&1
```

## 🛠️ Troubleshooting

### Common Issues

1. **Docker permission denied**
   ```bash
   sudo usermod -aG docker $USER
   # Logout and login again
   ```

2. **Selenium/Chrome issues**
   ```bash
   # Rebuild the container
   docker-compose build --no-cache
   ```

3. **Out of memory**
   ```bash
   # Increase swap space
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

4. **Network connectivity issues**
   ```bash
   # Check if the container can reach the internet
   docker-compose run --rm made-in-china-scraper ping google.com
   ```

### Performance Optimization

1. **Increase memory limit**
   ```bash
   # In docker-compose.yml, add:
   deploy:
     resources:
       limits:
         memory: 4G
   ```

2. **Use SSD storage** for better I/O performance

3. **Run multiple instances** for different keywords
   ```bash
   # Create separate compose files for different searches
   docker-compose -f docker-compose-hair-dryer.yml up -d
   docker-compose -f docker-compose-electronics.yml up -d
   ```

## 📈 Scaling Considerations

### For High-Volume Scraping

1. **Use a larger instance type** (t3.xlarge or equivalent)
2. **Implement rate limiting** to avoid being blocked
3. **Use proxy rotation** for multiple IP addresses
4. **Set up monitoring** with tools like Prometheus/Grafana
5. **Use a managed database** (RDS, Cloud SQL) instead of SQLite

### Load Balancing

```bash
# Run multiple containers for different keywords
docker-compose up -d --scale made-in-china-scraper=3
```

## 🔒 Security Considerations

1. **Use a dedicated user** for running the scraper
2. **Restrict network access** with security groups
3. **Regularly update** the base Docker image
4. **Monitor logs** for suspicious activity
5. **Backup data** regularly

## 📞 Support

If you encounter any issues:
1. Check the logs: `docker-compose logs made-in-china-scraper`
2. Verify the configuration in `config.py`
3. Test with a simple search first
4. Ensure your cloud instance has sufficient resources

---

**Happy Scraping! 🚀**







