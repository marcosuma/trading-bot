#!/bin/bash
#
# Update SSH Firewall Rule with New IP
# Run this when your home IP address changes
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Update SSH Firewall Rule${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get current IP
NEW_IP=$(curl -s ifconfig.me)
if [ -z "$NEW_IP" ]; then
    echo -e "${RED}Could not detect your IP address${NC}"
    read -p "Enter your IP manually: " NEW_IP
fi

echo "Your current IP: $NEW_IP"
echo ""

# Get current firewall rule IP
CURRENT_RULE=$(gcloud compute firewall-rules describe allow-ssh-from-home --format="value(sourceRanges)" 2>/dev/null || echo "not found")

if [ "$CURRENT_RULE" == "not found" ]; then
    echo -e "${RED}Firewall rule 'allow-ssh-from-home' not found.${NC}"
    echo "Run gcp-setup.sh first to create the instance and firewall rules."
    exit 1
fi

echo "Current allowed IP: $CURRENT_RULE"
echo ""

if [ "$CURRENT_RULE" == "$NEW_IP/32" ]; then
    echo -e "${GREEN}IP is already up to date. No changes needed.${NC}"
    exit 0
fi

read -p "Update firewall rule to allow $NEW_IP? [Y/n]: " CONFIRM
CONFIRM=${CONFIRM:-Y}

if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${GREEN}Updating firewall rule...${NC}"
    gcloud compute firewall-rules update allow-ssh-from-home \
        --source-ranges="$NEW_IP/32"
    
    echo ""
    echo -e "${GREEN}Done! SSH is now allowed from: $NEW_IP${NC}"
else
    echo "Cancelled."
fi
